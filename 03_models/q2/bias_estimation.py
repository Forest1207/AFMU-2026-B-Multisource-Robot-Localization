"""Spatial bias estimation for Q2.

For a fixed time offset, the least-squares optimum of the constant
relative spatial bias has a closed-form solution: the mean aligned
position difference between stream 2 and stream 1.
"""

from __future__ import annotations

import numpy as np


def estimate_constant_bias(
    xy1: np.ndarray,
    xy2_aligned: np.ndarray,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Estimate b = stream2 - stream1 for already time-aligned samples.

    Parameters
    ----------
    xy1, xy2_aligned:
        Arrays of shape (n, 2), sampled at the same physical times.
    weights:
        Optional non-negative observation weights of shape (n,).

    Returns
    -------
    np.ndarray, shape (2,)
        Estimated constant bias [b_x, b_y].  Correct stream 2 by
        ``xy2_corrected = xy2_aligned - bias``.
    """
    a = np.asarray(xy1, dtype=float)
    b = np.asarray(xy2_aligned, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 2:
        raise ValueError("xy1 and xy2_aligned must both have shape (n, 2).")
    if a.shape[0] == 0:
        raise ValueError("At least one aligned sample is required.")

    diff = b - a
    if weights is None:
        return np.mean(diff, axis=0)

    w = np.asarray(weights, dtype=float).reshape(-1)
    if w.shape[0] != a.shape[0]:
        raise ValueError("weights must have shape (n,).")
    if np.any(~np.isfinite(w)) or np.any(w < 0) or np.sum(w) <= 0:
        raise ValueError("weights must be finite, non-negative, and sum to > 0.")
    return np.average(diff, axis=0, weights=w)


def residuals_after_bias(
    xy1: np.ndarray,
    xy2_aligned: np.ndarray,
    bias: np.ndarray,
) -> np.ndarray:
    """Return residuals stream1 - (stream2 - bias)."""
    a = np.asarray(xy1, dtype=float)
    b = np.asarray(xy2_aligned, dtype=float)
    beta = np.asarray(bias, dtype=float).reshape(2)
    return a - (b - beta)


def huber_weights(residuals: np.ndarray, c: float = 1.345) -> np.ndarray:
    """Compute robust Huber weights from 2-D residual magnitudes.

    The robust scale is estimated by MAD.  These weights can be used in
    an iteratively reweighted least-squares refinement.
    """
    r = np.asarray(residuals, dtype=float)
    if r.ndim != 2 or r.shape[1] != 2:
        raise ValueError("residuals must have shape (n, 2).")
    mag = np.linalg.norm(r, axis=1)
    med = np.median(mag)
    mad = np.median(np.abs(mag - med))
    scale = 1.4826 * mad
    if scale <= np.finfo(float).eps:
        return np.ones_like(mag)

    u = np.abs(mag - med) / scale
    w = np.ones_like(u)
    mask = u > c
    w[mask] = c / u[mask]
    return w
