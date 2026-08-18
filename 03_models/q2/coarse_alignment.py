"""Cross-correlation based coarse time alignment for Q2."""

from __future__ import annotations

import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import correlate, correlation_lags


def _speed_feature(time: np.ndarray, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(time, dtype=float).reshape(-1)
    p = np.asarray(xy, dtype=float)
    if p.shape != (t.size, 2):
        raise ValueError("xy must have shape (n, 2).")
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("time must be strictly increasing.")
    mid = 0.5 * (t[:-1] + t[1:])
    speed = np.linalg.norm(np.diff(p, axis=0), axis=1) / dt
    return mid, speed


def estimate_coarse_offset(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    grid_dt: float = 0.02,
    max_abs_lag: float | None = None,
) -> float:
    """Estimate coarse dt by correlating speed magnitudes.

    Sign convention matches ``joint_alignment``: positive dt means stream 2
    is queried at ``t + dt`` when compared with stream 1.
    """
    if grid_dt <= 0:
        raise ValueError("grid_dt must be positive.")

    ts1, v1 = _speed_feature(t1, xy1)
    ts2, v2 = _speed_feature(t2, xy2)
    lo = max(ts1[0], ts2[0])
    hi = min(ts1[-1], ts2[-1])
    if hi - lo < 10 * grid_dt:
        raise ValueError("Insufficient temporal overlap for coarse alignment.")

    grid = np.arange(lo, hi + 0.5 * grid_dt, grid_dt)
    f1 = interp1d(ts1, v1, kind="linear", bounds_error=True)
    f2 = interp1d(ts2, v2, kind="linear", bounds_error=True)
    a = np.asarray(f1(grid), dtype=float)
    b = np.asarray(f2(grid), dtype=float)
    a = (a - np.mean(a)) / max(np.std(a), np.finfo(float).eps)
    b = (b - np.mean(b)) / max(np.std(b), np.finfo(float).eps)

    corr = correlate(a, b, mode="full", method="auto")
    lags = correlation_lags(a.size, b.size, mode="full")
    lag_seconds = lags.astype(float) * grid_dt

    if max_abs_lag is not None:
        mask = np.abs(lag_seconds) <= float(max_abs_lag)
        corr = corr[mask]
        lag_seconds = lag_seconds[mask]
        if corr.size == 0:
            raise ValueError("No lag candidates remain after max_abs_lag filtering.")

    # scipy correlate(a, b): if b must be shifted later to match a, the peak
    # lag is negative.  Negate it to obtain our convention query stream2 at t+dt.
    return float(-lag_seconds[int(np.argmax(corr))])
