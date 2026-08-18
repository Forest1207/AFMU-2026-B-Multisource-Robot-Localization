"""Asynchronous robust Kalman fusion and RTS smoothing for Q3.

The state uses a planar constant-acceleration model
[x, y, vx, vy, ax, ay]. When the bias test rejects H0, two additional
states [bx, by] are appended so that stream 2 is modeled as position + bias.
Raw 4 Hz / 5 Hz measurements are fused at their corrected event times; no
interpolated 10 Hz pseudo-measurements are introduced into the filter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2


@dataclass(frozen=True)
class FilterResult:
    time: np.ndarray
    sensor: np.ndarray
    measurement: np.ndarray
    predicted_state: np.ndarray
    predicted_cov: np.ndarray
    filtered_state: np.ndarray
    filtered_cov: np.ndarray
    transition_from_previous: np.ndarray
    innovation: np.ndarray
    pre_gate_innovation_cov: np.ndarray
    innovation_cov: np.ndarray
    pre_gate_nis: np.ndarray
    nis: np.ndarray
    r_scale: np.ndarray
    estimate_bias: bool


@dataclass(frozen=True)
class SmoothedResult:
    time: np.ndarray
    state: np.ndarray
    cov: np.ndarray
    estimate_bias: bool


def ca_transition(dt: float, estimate_bias: bool = False) -> np.ndarray:
    """Constant-acceleration transition for an arbitrary non-negative dt."""
    dt = float(dt)
    if dt < 0:
        raise ValueError("dt must be non-negative.")
    n = 8 if estimate_bias else 6
    F = np.eye(n, dtype=float)
    h = 0.5 * dt * dt
    F[0, 2] = dt
    F[0, 4] = h
    F[1, 3] = dt
    F[1, 5] = h
    F[2, 4] = dt
    F[3, 5] = dt
    return F


def ca_process_noise(
    dt: float,
    jerk_spectral_density: float = 0.5,
    estimate_bias: bool = False,
    bias_random_walk_var: float = 1e-8,
) -> np.ndarray:
    """Discrete process covariance for white jerk + optional bias random walk."""
    dt = float(dt)
    if dt < 0:
        raise ValueError("dt must be non-negative.")
    if jerk_spectral_density < 0 or bias_random_walk_var < 0:
        raise ValueError("Process-noise parameters must be non-negative.")

    n = 8 if estimate_bias else 6
    Q = np.zeros((n, n), dtype=float)
    q = float(jerk_spectral_density)
    block = q * np.array(
        [
            [dt**5 / 20.0, dt**4 / 8.0, dt**3 / 6.0],
            [dt**4 / 8.0, dt**3 / 3.0, dt**2 / 2.0],
            [dt**3 / 6.0, dt**2 / 2.0, dt],
        ],
        dtype=float,
    )
    for idx in ([0, 2, 4], [1, 3, 5]):
        Q[np.ix_(idx, idx)] = block
    if estimate_bias:
        Q[6, 6] = bias_random_walk_var * dt
        Q[7, 7] = bias_random_walk_var * dt
    return Q


def measurement_matrix(sensor: int, estimate_bias: bool) -> np.ndarray:
    """Return the 2-D position observation matrix for sensor 1 or 2."""
    if sensor not in (1, 2):
        raise ValueError("sensor must be 1 or 2.")
    n = 8 if estimate_bias else 6
    H = np.zeros((2, n), dtype=float)
    H[0, 0] = 1.0
    H[1, 1] = 1.0
    if estimate_bias and sensor == 2:
        H[0, 6] = 1.0
        H[1, 7] = 1.0
    return H


def symmetric_measurement_covariances(
    aligned_residual: np.ndarray,
    variance_floor: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate R1/R2 from corrected inter-sensor residuals.

    Without an external truth, the residual variance is split symmetrically
    between the two sensors. This is an identifiability convention.
    """
    r = np.asarray(aligned_residual, dtype=float)
    if r.ndim != 2 or r.shape[1] != 2 or r.shape[0] < 3:
        raise ValueError("aligned_residual must have shape (n, 2), n >= 3.")
    if np.any(~np.isfinite(r)):
        raise ValueError("aligned_residual contains non-finite values.")

    centered = r - np.median(r, axis=0, keepdims=True)
    mad = np.median(np.abs(centered), axis=0)
    robust_sigma = 1.4826 * mad
    classical_sigma = np.std(r, axis=0, ddof=1)
    sigma = np.where(robust_sigma > 1e-10, robust_sigma, classical_sigma)
    var = np.maximum(0.5 * sigma**2, variance_floor)
    R = np.diag(var)
    return R.copy(), R.copy()


def corrected_event_times(
    t1: np.ndarray,
    t2: np.ndarray,
    time_offset: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Map timestamps to the stream-1 reference clock.

    The sign convention matches Q2 joint_alignment: stream 2 is queried at
    device time t + time_offset for stream-1 physical time t. Therefore an
    observed stream-2 timestamp maps to t2 - time_offset.
    """
    a = np.asarray(t1, dtype=float).reshape(-1)
    b = np.asarray(t2, dtype=float).reshape(-1)
    return a.copy(), b - float(time_offset)


def _validate_stream(
    time: np.ndarray,
    xy: np.ndarray,
    name: str,
) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(time, dtype=float).reshape(-1)
    p = np.asarray(xy, dtype=float)
    if p.shape != (t.size, 2):
        raise ValueError(f"{name}: xy must have shape (n, 2).")
    if t.size < 2 or np.any(~np.isfinite(t)) or np.any(~np.isfinite(p)):
        raise ValueError(f"{name}: invalid or insufficient data.")
    order = np.argsort(t, kind="mergesort")
    t, p = t[order], p[order]
    if np.any(np.diff(t) <= 0):
        raise ValueError(f"{name}: timestamps must be strictly increasing.")
    return t, p


def build_measurement_events(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    time_offset: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Combine corrected raw measurements into one chronological event stream."""
    t1, xy1 = _validate_stream(t1, xy1, "stream1")
    t2, xy2 = _validate_stream(t2, xy2, "stream2")
    tc1, tc2 = corrected_event_times(t1, t2, time_offset)

    time = np.concatenate([tc1, tc2])
    sensor = np.concatenate(
        [np.ones(tc1.size, dtype=int), np.full(tc2.size, 2, dtype=int)]
    )
    measurement = np.vstack([xy1, xy2])
    order = np.argsort(time, kind="mergesort")
    return time[order], sensor[order], measurement[order]


def _initial_state(
    sensor: int,
    measurement: np.ndarray,
    estimate_bias: bool,
    initial_bias: np.ndarray,
) -> np.ndarray:
    n = 8 if estimate_bias else 6
    x = np.zeros(n, dtype=float)
    z = np.asarray(measurement, dtype=float).reshape(2)
    b = np.asarray(initial_bias, dtype=float).reshape(2)
    if estimate_bias and sensor == 2:
        x[:2] = z - b
    else:
        x[:2] = z
    if estimate_bias:
        x[6:8] = b
    return x


def _initial_covariance(
    R1: np.ndarray,
    R2: np.ndarray,
    estimate_bias: bool,
    bias_prior_var: float,
) -> np.ndarray:
    n = 8 if estimate_bias else 6
    P = np.eye(n, dtype=float)
    pos_var = max(
        float(np.max(np.diag(R1))),
        float(np.max(np.diag(R2))),
        1e-4,
    )
    P[0, 0] = P[1, 1] = 10.0 * pos_var
    P[2, 2] = P[3, 3] = 4.0
    P[4, 4] = P[5, 5] = 4.0
    if estimate_bias:
        P[6, 6] = P[7, 7] = max(float(bias_prior_var), pos_var)
    return P


def asynchronous_robust_kf(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    time_offset: float,
    R1: np.ndarray,
    R2: np.ndarray,
    estimate_bias: bool,
    initial_bias: np.ndarray | None = None,
    jerk_spectral_density: float = 0.5,
    bias_random_walk_var: float = 1e-8,
    bias_prior_var: float = 0.1,
    gate_probability: float = 0.99,
    max_r_inflation: float = 100.0,
) -> FilterResult:
    """Fuse original asynchronous measurements with robust innovation weighting.

    Large innovations are not discarded. Their measurement covariance is
    inflated according to NIS / chi-square gate, reducing their Kalman gain.
    """
    R1 = np.asarray(R1, dtype=float).reshape(2, 2)
    R2 = np.asarray(R2, dtype=float).reshape(2, 2)
    if np.any(np.linalg.eigvalsh(R1) <= 0) or np.any(np.linalg.eigvalsh(R2) <= 0):
        raise ValueError("R1 and R2 must be positive definite.")
    if not 0.5 < gate_probability < 1.0:
        raise ValueError("gate_probability should lie in (0.5, 1).")

    time, sensor, measurement = build_measurement_events(
        t1, xy1, t2, xy2, time_offset
    )
    n_event = time.size
    n_state = 8 if estimate_bias else 6
    bias0 = (
        np.zeros(2)
        if initial_bias is None
        else np.asarray(initial_bias, dtype=float).reshape(2)
    )

    x = _initial_state(int(sensor[0]), measurement[0], estimate_bias, bias0)
    P = _initial_covariance(R1, R2, estimate_bias, bias_prior_var)

    predicted_state = np.empty((n_event, n_state), dtype=float)
    predicted_cov = np.empty((n_event, n_state, n_state), dtype=float)
    filtered_state = np.empty_like(predicted_state)
    filtered_cov = np.empty_like(predicted_cov)
    transitions = np.empty((n_event, n_state, n_state), dtype=float)
    innovations = np.empty((n_event, 2), dtype=float)
    pre_gate_innovation_cov = np.empty((n_event, 2, 2), dtype=float)
    innovation_cov = np.empty((n_event, 2, 2), dtype=float)
    pre_gate_nis = np.empty(n_event, dtype=float)
    nis = np.empty(n_event, dtype=float)
    r_scale = np.empty(n_event, dtype=float)

    gate = float(chi2.ppf(gate_probability, df=2))
    I = np.eye(n_state)
    prev_time = float(time[0])

    for k in range(n_event):
        dt = 0.0 if k == 0 else float(time[k] - prev_time)
        if dt < -1e-12:
            raise RuntimeError("Measurement events are not time ordered.")
        dt = max(dt, 0.0)
        F = ca_transition(dt, estimate_bias=estimate_bias)
        Q = ca_process_noise(
            dt,
            jerk_spectral_density=jerk_spectral_density,
            estimate_bias=estimate_bias,
            bias_random_walk_var=bias_random_walk_var,
        )
        if k > 0:
            x = F @ x
            P = F @ P @ F.T + Q
        transitions[k] = F
        predicted_state[k] = x
        predicted_cov[k] = P

        s = int(sensor[k])
        H = measurement_matrix(s, estimate_bias)
        R_base = R1 if s == 1 else R2
        z = measurement[k]
        innovation = z - H @ x
        S0 = H @ P @ H.T + R_base
        nis0 = float(
            innovation.T @ np.linalg.pinv(S0, hermitian=True) @ innovation
        )
        scale = min(float(max_r_inflation), max(1.0, nis0 / gate))
        R_eff = R_base * scale
        S = H @ P @ H.T + R_eff
        K = P @ H.T @ np.linalg.pinv(S, hermitian=True)
        x = x + K @ innovation
        IKH = I - K @ H
        P = IKH @ P @ IKH.T + K @ R_eff @ K.T
        P = 0.5 * (P + P.T)

        filtered_state[k] = x
        filtered_cov[k] = P
        innovations[k] = innovation
        pre_gate_innovation_cov[k] = S0
        innovation_cov[k] = S
        pre_gate_nis[k] = nis0
        nis[k] = float(
            innovation.T @ np.linalg.pinv(S, hermitian=True) @ innovation
        )
        r_scale[k] = scale
        prev_time = float(time[k])

    return FilterResult(
        time=time,
        sensor=sensor,
        measurement=measurement,
        predicted_state=predicted_state,
        predicted_cov=predicted_cov,
        filtered_state=filtered_state,
        filtered_cov=filtered_cov,
        transition_from_previous=transitions,
        innovation=innovations,
        pre_gate_innovation_cov=pre_gate_innovation_cov,
        innovation_cov=innovation_cov,
        pre_gate_nis=pre_gate_nis,
        nis=nis,
        r_scale=r_scale,
        estimate_bias=estimate_bias,
    )


def rts_smoother(result: FilterResult) -> SmoothedResult:
    """Run Rauch-Tung-Striebel backward smoothing over event-time states."""
    xs = result.filtered_state.copy()
    Ps = result.filtered_cov.copy()
    n = result.time.size

    for k in range(n - 2, -1, -1):
        F_next = result.transition_from_previous[k + 1]
        P_pred_next = result.predicted_cov[k + 1]
        C = (
            result.filtered_cov[k]
            @ F_next.T
            @ np.linalg.pinv(P_pred_next, hermitian=True)
        )
        xs[k] = result.filtered_state[k] + C @ (
            xs[k + 1] - result.predicted_state[k + 1]
        )
        Ps[k] = result.filtered_cov[k] + C @ (
            Ps[k + 1] - P_pred_next
        ) @ C.T
        Ps[k] = 0.5 * (Ps[k] + Ps[k].T)

    return SmoothedResult(
        time=result.time.copy(),
        state=xs,
        cov=Ps,
        estimate_bias=result.estimate_bias,
    )


def resample_smoothed_state(
    smoothed: SmoothedResult,
    sample_dt: float = 0.1,
    start_time: float | None = None,
    end_time: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a uniform state grid without introducing pseudo-observations."""
    if sample_dt <= 0:
        raise ValueError("sample_dt must be positive.")
    t = smoothed.time
    lo = float(t[0] if start_time is None else max(start_time, t[0]))
    hi = float(t[-1] if end_time is None else min(end_time, t[-1]))
    if hi < lo:
        raise ValueError("Requested output interval has no overlap.")

    grid = np.arange(lo, hi + 0.5 * sample_dt, sample_dt)
    grid = grid[grid <= hi + 1e-12]
    n_state = smoothed.state.shape[1]
    out = np.empty((grid.size, n_state), dtype=float)

    for i, tg in enumerate(grid):
        idx = int(np.searchsorted(t, tg, side="right") - 1)
        idx = max(0, min(idx, t.size - 1))
        dt = float(tg - t[idx])
        F = ca_transition(
            max(dt, 0.0),
            estimate_bias=smoothed.estimate_bias,
        )
        out[i] = F @ smoothed.state[idx]
    return grid, out


def resample_smoothed_covariance(
    smoothed: SmoothedResult,
    sample_dt: float = 0.1,
    start_time: float | None = None,
    end_time: float | None = None,
    jerk_spectral_density: float = 0.5,
    bias_random_walk_var: float = 1e-8,
) -> tuple[np.ndarray, np.ndarray]:
    """Propagate smoothed event covariances to the same uniform state grid."""
    if sample_dt <= 0:
        raise ValueError("sample_dt must be positive.")
    t = smoothed.time
    lo = float(t[0] if start_time is None else max(start_time, t[0]))
    hi = float(t[-1] if end_time is None else min(end_time, t[-1]))
    if hi < lo:
        raise ValueError("Requested output interval has no overlap.")
    grid = np.arange(lo, hi + 0.5 * sample_dt, sample_dt)
    grid = grid[grid <= hi + 1e-12]
    n_state = smoothed.state.shape[1]
    out = np.empty((grid.size, n_state, n_state), dtype=float)
    for i, tg in enumerate(grid):
        idx = int(np.searchsorted(t, tg, side="right") - 1)
        idx = max(0, min(idx, t.size - 1))
        dt = max(float(tg - t[idx]), 0.0)
        F = ca_transition(dt, estimate_bias=smoothed.estimate_bias)
        Q = ca_process_noise(
            dt,
            jerk_spectral_density=jerk_spectral_density,
            estimate_bias=smoothed.estimate_bias,
            bias_random_walk_var=bias_random_walk_var,
        )
        P = F @ smoothed.cov[idx] @ F.T + Q
        out[i] = 0.5 * (P + P.T)
    return grid, out


def state_kinematics(state: np.ndarray) -> dict[str, np.ndarray]:
    """Extract position, velocity and acceleration quantities from states."""
    x = np.asarray(state, dtype=float)
    if x.ndim != 2 or x.shape[1] not in (6, 8):
        raise ValueError("state must have shape (n, 6) or (n, 8).")
    speed = np.linalg.norm(x[:, 2:4], axis=1)
    acceleration = np.linalg.norm(x[:, 4:6], axis=1)
    out = {
        "x": x[:, 0],
        "y": x[:, 1],
        "vx": x[:, 2],
        "vy": x[:, 3],
        "speed": speed,
        "ax": x[:, 4],
        "ay": x[:, 5],
        "acceleration": acceleration,
    }
    if x.shape[1] == 8:
        out["bias_x"] = x[:, 6]
        out["bias_y"] = x[:, 7]
    return out
