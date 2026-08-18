"""Continuous interpolation models used by Q1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.interpolate import (
    Akima1DInterpolator,
    CubicSpline,
    PchipInterpolator,
    interp1d,
)

from data_loader import TrajectorySamples


InterpolationMethod = Literal["linear", "cubic", "pchip", "akima"]


@dataclass
class ContinuousTrajectory:
    """Continuous 2-D trajectory on one device time axis."""

    method: InterpolationMethod
    t_min: float
    t_max: float
    _fx: object
    _fy: object

    def evaluate(self, t: np.ndarray | float) -> np.ndarray:
        q = np.asarray(t, dtype=float)
        if np.any(q < self.t_min - 1e-12) or np.any(q > self.t_max + 1e-12):
            raise ValueError(
                f"Interpolation query outside [{self.t_min}, {self.t_max}]."
            )
        x = np.asarray(self._fx(q), dtype=float)
        y = np.asarray(self._fy(q), dtype=float)
        return np.stack((x, y), axis=-1)

    def sample_uniform(self, dt: float) -> tuple[np.ndarray, np.ndarray]:
        if dt <= 0:
            raise ValueError("dt must be positive.")
        t = np.arange(self.t_min, self.t_max + 0.5 * dt, dt)
        t = t[t <= self.t_max + 1e-12]
        return t, self.evaluate(t)


def build_trajectory(
    samples: TrajectorySamples,
    method: InterpolationMethod = "cubic",
) -> ContinuousTrajectory:
    """Build x(t), y(t) without extrapolation."""
    t = samples.time
    x = samples.xy[:, 0]
    y = samples.xy[:, 1]

    if method == "linear":
        fx = interp1d(t, x, kind="linear", bounds_error=True, assume_sorted=True)
        fy = interp1d(t, y, kind="linear", bounds_error=True, assume_sorted=True)
    elif method == "cubic":
        # not-a-knot is SciPy's default and is appropriate for interpolation here.
        fx = CubicSpline(t, x, extrapolate=False)
        fy = CubicSpline(t, y, extrapolate=False)
    elif method == "pchip":
        fx = PchipInterpolator(t, x, extrapolate=False)
        fy = PchipInterpolator(t, y, extrapolate=False)
    elif method == "akima":
        fx = Akima1DInterpolator(t, x, extrapolate=False)
        fy = Akima1DInterpolator(t, y, extrapolate=False)
    else:
        raise ValueError(f"Unknown interpolation method: {method}")

    return ContinuousTrajectory(
        method=method,
        t_min=float(t[0]),
        t_max=float(t[-1]),
        _fx=fx,
        _fy=fy,
    )
