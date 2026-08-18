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

    w = np.asarray(weights, dtype=float)
    if w.ndim == 1:
        w = np.repeat(w[:, None], 2, axis=1)
    if w.shape != a.shape:
        raise ValueError("weights must have shape (n,) or (n, 2).")
    if np.any(~np.isfinite(w)) or np.any(w < 0) or np.sum(w) <= 0:
        raise ValueError("weights must be finite, non-negative, and sum to > 0.")
    denom = np.sum(w, axis=0)
    if np.any(denom <= 0):
        raise ValueError("Each coordinate must have positive total weight.")
    return np.sum(w * diff, axis=0) / denom


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


def huber_weights(
    residuals: np.ndarray,
    scale: np.ndarray | None = None,
    c: float = 1.345,
) -> np.ndarray:
    """Return standard component-wise Huber IRLS weights.

    ``w=1`` for ``|r_j/s_j|<=c`` and ``w=c/|r_j/s_j|`` otherwise.  The
    result has shape ``(n, 2)``; small good residuals are never downweighted.
    """
    r = np.asarray(residuals, dtype=float)
    if r.ndim != 2 or r.shape[1] != 2:
        raise ValueError("residuals must have shape (n, 2).")
    if scale is None:
        centered = r - np.median(r, axis=0, keepdims=True)
        s = 1.4826 * np.median(np.abs(centered), axis=0)
        fallback = np.std(r, axis=0, ddof=1)
        s = np.where(s > 1e-12, s, fallback)
    else:
        s = np.asarray(scale, dtype=float).reshape(2)
    s = np.maximum(s, np.finfo(float).eps)
    u = np.abs(r / s)
    w = np.ones_like(u)
    mask = u > c
    w[mask] = c / u[mask]
    return w
