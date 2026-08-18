"""Noise estimation and variance-weighted multi-sensor fusion for Q2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FusionResult:
    fused_xy: np.ndarray
    weights1: np.ndarray
    weights2: np.ndarray
    var1: np.ndarray
    var2: np.ndarray


def estimate_axis_variances(
    xy1: np.ndarray,
    xy2: np.ndarray,
    floor: float = 1e-10,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate per-axis sensor variances from aligned observations.

    Without an external ground truth, the variance split is not uniquely
    identifiable.  This function uses a symmetric approximation by assigning
    half of the variance of the inter-sensor difference to each sensor.  If
    known device variances are available from the problem statement, pass
    those directly to ``variance_weighted_fusion`` instead.
    """
    a = np.asarray(xy1, dtype=float)
    b = np.asarray(xy2, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 2:
        raise ValueError("xy1 and xy2 must both have shape (n, 2).")
    if a.shape[0] < 2:
        raise ValueError("At least two samples are required.")

    diff_var = np.var(a - b, axis=0, ddof=1)
    var = np.maximum(0.5 * diff_var, floor)
    return var.copy(), var.copy()


def variance_weighted_fusion(
    xy1: np.ndarray,
    xy2: np.ndarray,
    var1: np.ndarray,
    var2: np.ndarray,
    floor: float = 1e-12,
) -> FusionResult:
    """Fuse two aligned 2-D tracks using inverse-variance weights per axis."""
    a = np.asarray(xy1, dtype=float)
    b = np.asarray(xy2, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 2:
        raise ValueError("xy1 and xy2 must both have shape (n, 2).")

    v1 = np.maximum(np.asarray(var1, dtype=float).reshape(2), floor)
    v2 = np.maximum(np.asarray(var2, dtype=float).reshape(2), floor)
    if np.any(~np.isfinite(v1)) or np.any(~np.isfinite(v2)):
        raise ValueError("Variances must be finite.")

    precision1 = 1.0 / v1
    precision2 = 1.0 / v2
    denom = precision1 + precision2
    w1 = precision1 / denom
    w2 = precision2 / denom
    fused = a * w1 + b * w2

    return FusionResult(
        fused_xy=fused,
        weights1=w1,
        weights2=w2,
        var1=v1,
        var2=v2,
    )
