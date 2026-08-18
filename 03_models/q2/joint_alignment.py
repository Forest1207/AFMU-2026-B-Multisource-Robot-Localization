"""Joint temporal and spatial alignment for Q2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator, CubicSpline, interp1d
from scipy.optimize import minimize_scalar

from bias_estimation import (
    estimate_constant_bias,
    huber_weights,
    residuals_after_bias,
)


@dataclass(frozen=True)
class AlignmentResult:
    dt: float
    bias: np.ndarray
    objective: float
    rmse: float
    n_overlap: int
    iterations: int


def _make_interpolator(t: np.ndarray, y: np.ndarray, method: str):
    if method == "linear":
        return interp1d(t, y, axis=0, bounds_error=True, assume_sorted=True)
    if method == "cubic":
        return CubicSpline(t, y, axis=0, extrapolate=False)
    if method == "pchip":
        return PchipInterpolator(t, y, axis=0, extrapolate=False)
    raise ValueError(f"Unknown interpolation method: {method}")


def _validate_stream(t: np.ndarray, xy: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(t, dtype=float).reshape(-1)
    xy = np.asarray(xy, dtype=float)
    if xy.shape != (t.size, 2):
        raise ValueError(f"{name}: xy must have shape (n, 2).")
    if t.size < 4:
        raise ValueError(f"{name}: at least four samples are required.")
    if np.any(~np.isfinite(t)) or np.any(~np.isfinite(xy)):
        raise ValueError(f"{name}: non-finite values found.")
    order = np.argsort(t, kind="mergesort")
    t, xy = t[order], xy[order]
    if np.any(np.diff(t) <= 0):
        raise ValueError(f"{name}: timestamps must be strictly increasing.")
    return t, xy


def aligned_samples(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    dt: float,
    sample_dt: float = 0.1,
    interpolation: str = "pchip",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample both streams on their physical overlap for a candidate dt.

    Convention: stream 2 is compared at device time ``t + dt`` against
    stream 1 at time ``t``.  Thus positive dt means stream-2 timestamps
    must be queried later to represent the same physical instant.
    """
    t1, xy1 = _validate_stream(t1, xy1, "stream1")
    t2, xy2 = _validate_stream(t2, xy2, "stream2")
    if sample_dt <= 0:
        raise ValueError("sample_dt must be positive.")

    lo = max(float(t1[0]), float(t2[0] - dt))
    hi = min(float(t1[-1]), float(t2[-1] - dt))
    if hi <= lo:
        raise ValueError("No temporal overlap for this candidate dt.")

    # Build the grid from an integer count and clip interpolation arguments.
    # Excel decimal timestamps can be one ulp outside the nominal endpoint;
    # strict interpolators would otherwise return NaN at a valid boundary.
    n_step = int(np.floor((hi - lo) / sample_dt + 1e-10))
    grid = lo + sample_dt * np.arange(n_step + 1, dtype=float)
    grid = np.clip(grid, lo, hi)
    if grid.size < 4:
        raise ValueError("Too few overlap samples for this candidate dt.")

    f1 = _make_interpolator(t1, xy1, interpolation)
    f2 = _make_interpolator(t2, xy2, interpolation)
    q1 = np.clip(grid, t1[0], t1[-1])
    q2 = np.clip(grid + dt, t2[0], t2[-1])
    return grid, np.asarray(f1(q1)), np.asarray(f2(q2))


def _samples_on_fixed_grid(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    dt: float,
    grid: np.ndarray,
    interpolation: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate a candidate offset on a grid valid for the whole search box."""
    f1 = _make_interpolator(t1, xy1, interpolation)
    f2 = _make_interpolator(t2, xy2, interpolation)
    q1 = np.clip(grid, t1[0], t1[-1])
    q2_raw = grid + float(dt)
    tol = 64.0 * np.finfo(float).eps * max(1.0, np.max(np.abs(t2)))
    if np.any(q2_raw < t2[0] - tol) or np.any(q2_raw > t2[-1] + tol):
        raise ValueError("Fixed evaluation grid leaves stream-2 support.")
    q2 = np.clip(q2_raw, t2[0], t2[-1])
    return np.asarray(f1(q1)), np.asarray(f2(q2))


def _profile_on_arrays(
    a: np.ndarray,
    b: np.ndarray,
    robust_iterations: int,
    robust_scale: np.ndarray | None = None,
    huber_c: float = 1.345,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Profile bias with OLS or the standard component-wise Huber loss."""
    difference = np.asarray(b) - np.asarray(a)
    if robust_iterations <= 0:
        bias = estimate_constant_bias(a, b)
        residual = residuals_after_bias(a, b, bias)
        return float(np.mean(np.sum(residual**2, axis=1))), bias, residual

    bias = np.median(difference, axis=0)
    if robust_scale is None:
        centered = difference - np.median(difference, axis=0, keepdims=True)
        scale = 1.4826 * np.median(np.abs(centered), axis=0)
        fallback = np.std(difference, axis=0, ddof=1)
        scale = np.where(scale > 1e-12, scale, fallback)
    else:
        scale = np.asarray(robust_scale, dtype=float).reshape(2)
    scale = np.maximum(scale, np.finfo(float).eps)
    for _ in range(max(1, robust_iterations)):
        residual = residuals_after_bias(a, b, bias)
        weights = huber_weights(residual, scale=scale, c=huber_c)
        bias = estimate_constant_bias(a, b, weights=weights)
    residual = residuals_after_bias(a, b, bias)
    u = np.abs(residual / scale)
    rho = np.where(u <= huber_c, 0.5 * u**2, huber_c * u - 0.5 * huber_c**2)
    # Multiplication by scale² restores squared-distance units while keeping
    # the scale fixed across all candidate offsets in one search.
    objective = float(np.mean(np.sum(2.0 * rho * scale**2, axis=1)))
    return objective, bias, residual


def objective_for_dt(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    dt: float,
    sample_dt: float = 0.1,
    interpolation: str = "pchip",
    robust_iterations: int = 0,
) -> tuple[float, np.ndarray, np.ndarray, int]:
    """Profile objective J(dt) after analytically estimating spatial bias."""
    _, a, b = aligned_samples(t1, xy1, t2, xy2, dt, sample_dt, interpolation)
    objective, bias, residual = _profile_on_arrays(a, b, robust_iterations)
    return objective, bias, residual, a.shape[0]


def profile_objective_scan(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    offsets: np.ndarray,
    sample_dt: float = 0.1,
    interpolation: str = "pchip",
    robust_iterations: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate profile objectives on one grid valid for all offsets.

    Returns the objective vector and the corresponding ``(n, 2)`` bias
    estimates.  This is the plotting/sensitivity counterpart of the fixed-grid
    objective used by :func:`estimate_joint_alignment`.
    """
    t1, xy1 = _validate_stream(t1, xy1, "stream1")
    t2, xy2 = _validate_stream(t2, xy2, "stream2")
    values = np.asarray(offsets, dtype=float).reshape(-1)
    if values.size < 1 or np.any(~np.isfinite(values)):
        raise ValueError("offsets must contain finite candidates.")
    lower, upper = float(np.min(values)), float(np.max(values))
    grid_lo = max(float(t1[0]), float(t2[0] - lower))
    grid_hi = min(float(t1[-1]), float(t2[-1] - upper))
    if grid_hi <= grid_lo:
        raise ValueError("No common overlap for the requested objective scan.")
    n_step = int(np.floor((grid_hi - grid_lo) / sample_dt + 1e-10))
    grid = grid_lo + sample_dt * np.arange(n_step + 1, dtype=float)
    grid = np.clip(grid, grid_lo, grid_hi)
    mid = float(np.median(values))
    a_mid, b_mid = _samples_on_fixed_grid(
        t1, xy1, t2, xy2, mid, grid, interpolation
    )
    mid_diff = b_mid - a_mid
    mid_centered = mid_diff - np.median(mid_diff, axis=0, keepdims=True)
    robust_scale = 1.4826 * np.median(np.abs(mid_centered), axis=0)
    robust_scale = np.where(
        robust_scale > 1e-12,
        robust_scale,
        np.std(mid_diff, axis=0, ddof=1),
    )
    objectives = np.empty(values.size, dtype=float)
    biases = np.empty((values.size, 2), dtype=float)
    for i, value in enumerate(values):
        a, b = _samples_on_fixed_grid(
            t1, xy1, t2, xy2, float(value), grid, interpolation
        )
        objectives[i], biases[i], _ = _profile_on_arrays(
            a, b, robust_iterations, robust_scale=robust_scale
        )
    return objectives, biases


def estimate_joint_alignment(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    dt_bounds: tuple[float, float],
    sample_dt: float = 0.1,
    interpolation: str = "pchip",
    robust_iterations: int = 2,
    xatol: float = 1e-5,
    scan_points: int = 401,
) -> AlignmentResult:
    """Estimate time offset and constant 2-D relative spatial bias.

    ``dt_bounds`` should preferably come from Q1/cross-correlation coarse
    alignment.  The optimizer is only one-dimensional because the spatial
    bias is solved analytically for every candidate dt.
    """
    lower, upper = map(float, dt_bounds)
    if not lower < upper:
        raise ValueError("dt_bounds must satisfy lower < upper.")

    t1, xy1 = _validate_stream(t1, xy1, "stream1")
    t2, xy2 = _validate_stream(t2, xy2, "stream2")
    if scan_points < 5:
        raise ValueError("scan_points must be at least 5.")

    # Use one common physical-time grid for every candidate.  Rebuilding the
    # overlap grid for each dt introduces a moving-sample objective and can
    # shift the numerical optimum even when the two tracks align perfectly.
    grid_lo = max(float(t1[0]), float(t2[0] - lower))
    grid_hi = min(float(t1[-1]), float(t2[-1] - upper))
    if grid_hi <= grid_lo:
        raise ValueError("No common overlap valid for the full dt search interval.")
    n_step = int(np.floor((grid_hi - grid_lo) / sample_dt + 1e-10))
    fixed_grid = grid_lo + sample_dt * np.arange(n_step + 1, dtype=float)
    fixed_grid = np.clip(fixed_grid, grid_lo, grid_hi)
    if fixed_grid.size < 4:
        raise ValueError("Too few common samples for joint alignment.")
    a_mid, b_mid = _samples_on_fixed_grid(
        t1, xy1, t2, xy2, 0.5 * (lower + upper), fixed_grid, interpolation
    )
    mid_diff = b_mid - a_mid
    mid_centered = mid_diff - np.median(mid_diff, axis=0, keepdims=True)
    robust_scale = 1.4826 * np.median(np.abs(mid_centered), axis=0)
    robust_scale = np.where(
        robust_scale > 1e-12,
        robust_scale,
        np.std(mid_diff, axis=0, ddof=1),
    )

    def fun(dt: float) -> float:
        try:
            a, b = _samples_on_fixed_grid(
                t1, xy1, t2, xy2, dt, fixed_grid, interpolation
            )
            value, _, _ = _profile_on_arrays(
                a, b, robust_iterations, robust_scale=robust_scale
            )
            return value
        except ValueError:
            return np.inf

    scan_dt = np.linspace(lower, upper, int(scan_points))
    scan_obj = np.asarray([fun(value) for value in scan_dt], dtype=float)
    if not np.any(np.isfinite(scan_obj)):
        raise RuntimeError("Joint alignment scan found no finite candidate.")
    best = int(np.nanargmin(scan_obj))
    left = scan_dt[max(0, best - 1)]
    right = scan_dt[min(scan_dt.size - 1, best + 1)]
    if not left < right:
        raise RuntimeError("Joint alignment scan could not form a local bracket.")
    opt = minimize_scalar(
        fun,
        bounds=(float(left), float(right)),
        method="bounded",
        options={"xatol": xatol},
    )
    if not opt.success or not np.isfinite(opt.fun):
        raise RuntimeError(f"Joint alignment failed: {opt.message}")

    a, b = _samples_on_fixed_grid(
        t1, xy1, t2, xy2, float(opt.x), fixed_grid, interpolation
    )
    objective, bias, residual = _profile_on_arrays(
        a, b, robust_iterations, robust_scale=robust_scale
    )
    n = fixed_grid.size
    rmse = float(np.sqrt(np.mean(np.sum(residual**2, axis=1))))
    return AlignmentResult(
        dt=float(opt.x),
        bias=np.asarray(bias, dtype=float),
        objective=objective,
        rmse=rmse,
        n_overlap=n,
        iterations=int(getattr(opt, "nfev", 0)),
    )
