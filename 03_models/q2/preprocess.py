"""Lightweight preprocessing utilities for Q2 trajectories."""

from __future__ import annotations

import numpy as np


def speed_outlier_mask(
    time: np.ndarray,
    xy: np.ndarray,
    z_threshold: float = 4.5,
) -> np.ndarray:
    """Return a boolean mask keeping points not involved in extreme speed jumps.

    A robust MAD z-score is applied to segment speeds.  The first point is
    always retained.  This is intentionally conservative: the purpose is to
    suppress catastrophic spikes before alignment, not to smooth the motion.
    """
    t = np.asarray(time, dtype=float).reshape(-1)
    p = np.asarray(xy, dtype=float)
    if p.shape != (t.size, 2):
        raise ValueError("xy must have shape (n, 2).")
    if t.size < 4:
        return np.ones(t.size, dtype=bool)
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("time must be strictly increasing.")

    speed = np.linalg.norm(np.diff(p, axis=0), axis=1) / dt
    med = np.median(speed)
    mad = np.median(np.abs(speed - med))
    if mad <= np.finfo(float).eps:
        return np.ones(t.size, dtype=bool)

    robust_z = 0.67448975 * np.abs(speed - med) / mad
    bad_segment = robust_z > z_threshold
    keep = np.ones(t.size, dtype=bool)
    # Flag the endpoint of a suspicious segment. This preserves more data than
    # deleting both endpoints and works well for isolated position spikes.
    keep[1:][bad_segment] = False
    return keep


def clean_stream(
    time: np.ndarray,
    xy: np.ndarray,
    remove_speed_outliers: bool = True,
    z_threshold: float = 4.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Sort, de-duplicate, validate, and optionally reject extreme jumps."""
    t = np.asarray(time, dtype=float).reshape(-1)
    p = np.asarray(xy, dtype=float)
    if p.shape != (t.size, 2):
        raise ValueError("xy must have shape (n, 2).")

    finite = np.isfinite(t) & np.all(np.isfinite(p), axis=1)
    t, p = t[finite], p[finite]
    order = np.argsort(t, kind="mergesort")
    t, p = t[order], p[order]

    unique_t, inverse = np.unique(t, return_inverse=True)
    if unique_t.size != t.size:
        sums = np.zeros((unique_t.size, 2), dtype=float)
        counts = np.zeros(unique_t.size, dtype=float)
        np.add.at(sums, inverse, p)
        np.add.at(counts, inverse, 1.0)
        t, p = unique_t, sums / counts[:, None]

    if t.size < 4:
        raise ValueError("Too few valid samples after cleaning.")
    if remove_speed_outliers:
        mask = speed_outlier_mask(t, p, z_threshold=z_threshold)
        t, p = t[mask], p[mask]
        if t.size < 4:
            raise ValueError("Too few samples after outlier removal.")
    return t, p
