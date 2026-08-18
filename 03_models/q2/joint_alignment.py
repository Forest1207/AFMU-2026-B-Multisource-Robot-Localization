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

    grid = np.arange(lo, hi + 0.5 * sample_dt, sample_dt)
    grid = grid[grid <= hi + 1e-12]
    if grid.size < 4:
        raise ValueError("Too few overlap samples for this candidate dt.")

    f1 = _make_interpolator(t1, xy1, interpolation)
    f2 = _make_interpolator(t2, xy2, interpolation)
    return grid, np.asarray(f1(grid)), np.asarray(f2(grid + dt))


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
    weights = None
    bias = estimate_constant_bias(a, b)

    for _ in range(max(0, robust_iterations)):
        residual = residuals_after_bias(a, b, bias)
        weights = huber_weights(residual)
        bias = estimate_constant_bias(a, b, weights=weights)

    residual = residuals_after_bias(a, b, bias)
    squared = np.sum(residual**2, axis=1)
    if weights is None:
        objective = float(np.mean(squared))
    else:
        objective = float(np.average(squared, weights=weights))
    return objective, bias, residual, a.shape[0]


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
) -> AlignmentResult:
    """Estimate time offset and constant 2-D relative spatial bias.

    ``dt_bounds`` should preferably come from Q1/cross-correlation coarse
    alignment.  The optimizer is only one-dimensional because the spatial
    bias is solved analytically for every candidate dt.
    """
    lower, upper = map(float, dt_bounds)
    if not lower < upper:
        raise ValueError("dt_bounds must satisfy lower < upper.")

    def fun(dt: float) -> float:
        try:
            value, _, _, _ = objective_for_dt(
                t1, xy1, t2, xy2, dt,
                sample_dt=sample_dt,
                interpolation=interpolation,
                robust_iterations=robust_iterations,
            )
            return value
        except ValueError:
            return np.inf

    opt = minimize_scalar(
        fun,
        bounds=(lower, upper),
        method="bounded",
        options={"xatol": xatol},
    )
    if not opt.success or not np.isfinite(opt.fun):
        raise RuntimeError(f"Joint alignment failed: {opt.message}")

    objective, bias, residual, n = objective_for_dt(
        t1, xy1, t2, xy2, float(opt.x),
        sample_dt=sample_dt,
        interpolation=interpolation,
        robust_iterations=robust_iterations,
    )
    rmse = float(np.sqrt(np.mean(np.sum(residual**2, axis=1))))
    return AlignmentResult(
        dt=float(opt.x),
        bias=np.asarray(bias, dtype=float),
        objective=objective,
        rmse=rmse,
        n_overlap=n,
        iterations=int(getattr(opt, "nfev", 0)),
    )
