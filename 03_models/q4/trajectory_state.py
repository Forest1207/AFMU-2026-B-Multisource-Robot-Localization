"""Trajectory resampling, smoothing and motion-state reconstruction for Q4."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import UnivariateSpline


@dataclass(frozen=True)
class TrajectoryState:
    time: np.ndarray
    x: np.ndarray
    y: np.ndarray
    vx: np.ndarray
    vy: np.ndarray
    ax: np.ndarray
    ay: np.ndarray
    speed: np.ndarray
    acceleration: np.ndarray

    def validate(self) -> None:
        arrays = [self.x, self.y, self.vx, self.vy, self.ax, self.ay,
                  self.speed, self.acceleration]
        n = self.time.size
        if self.time.ndim != 1 or n < 4:
            raise ValueError("time must be one-dimensional with at least 4 samples")
        if np.any(np.diff(self.time) <= 0):
            raise ValueError("timestamps must be strictly increasing")
        if any(a.shape != (n,) for a in arrays):
            raise ValueError("all state arrays must have the same one-dimensional shape")
        if any(np.any(~np.isfinite(a)) for a in [self.time, *arrays]):
            raise ValueError("trajectory state contains non-finite values")


def _prepare_samples(time: np.ndarray, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(time, dtype=float).reshape(-1)
    p = np.asarray(xy, dtype=float)
    if p.shape != (t.size, 2):
        raise ValueError("xy must have shape (n, 2)")
    ok = np.isfinite(t) & np.isfinite(p).all(axis=1)
    t, p = t[ok], p[ok]
    order = np.argsort(t, kind="mergesort")
    t, p = t[order], p[order]
    if t.size < 4:
        raise ValueError("at least four valid trajectory samples are required")

    # Average duplicate timestamps before fitting the spline.
    unique_t, inverse = np.unique(t, return_inverse=True)
    if unique_t.size != t.size:
        sums = np.zeros((unique_t.size, 2), dtype=float)
        counts = np.zeros(unique_t.size, dtype=float)
        np.add.at(sums, inverse, p)
        np.add.at(counts, inverse, 1.0)
        p = sums / counts[:, None]
        t = unique_t
    if t.size < 4:
        raise ValueError("at least four unique timestamps are required")
    return t, p


def reconstruct_state(
    time: np.ndarray,
    xy: np.ndarray,
    fs: float = 10.0,
    smoothing: float | None = None,
    spline_order: int = 3,
) -> TrajectoryState:
    """Fit smoothing splines and evaluate position/velocity/acceleration at ``fs``.

    Parameters
    ----------
    time, xy:
        Input fused trajectory from Q3.
    fs:
        Output sampling rate. Q4 uses 10 Hz by default.
    smoothing:
        ``UnivariateSpline`` smoothing factor ``s``. ``None`` means interpolation
        (s=0). For noisy Q3 output, provide a small positive value after residual
        diagnostics rather than differentiating raw positions twice.
    spline_order:
        Spline order, clipped to [1, 3] because second derivatives are required.
    """
    if fs <= 0:
        raise ValueError("fs must be positive")
    t, p = _prepare_samples(time, xy)
    k = int(np.clip(spline_order, 2, min(3, t.size - 1)))
    s = 0.0 if smoothing is None else float(smoothing)
    if s < 0:
        raise ValueError("smoothing must be non-negative")

    sx = UnivariateSpline(t, p[:, 0], k=k, s=s)
    sy = UnivariateSpline(t, p[:, 1], k=k, s=s)
    dt = 1.0 / fs
    grid = np.arange(t[0], t[-1] + 0.5 * dt, dt)
    grid = grid[grid <= t[-1] + 1e-12]

    x, y = sx(grid), sy(grid)
    vx, vy = sx.derivative(1)(grid), sy.derivative(1)(grid)
    ax, ay = sx.derivative(2)(grid), sy.derivative(2)(grid)
    state = TrajectoryState(
        time=grid,
        x=x,
        y=y,
        vx=vx,
        vy=vy,
        ax=ax,
        ay=ay,
        speed=np.hypot(vx, vy),
        acceleration=np.hypot(ax, ay),
    )
    state.validate()
    return state


def state_xy(state: TrajectoryState) -> np.ndarray:
    """Return position as an ``(n, 2)`` array."""
    return np.column_stack([state.x, state.y])
