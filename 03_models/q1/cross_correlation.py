"""Coarse time alignment using normalized cross-correlation.

The two streams have different sampling rates, so raw arrays must NOT be passed
directly to np.correlate. Each stream is first resampled on an elapsed-time grid
with the same step. Multiple correlation peaks are retained because a smooth or
approximately periodic robot trajectory can create false peaks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import correlate, correlation_lags, find_peaks

from data_loader import TrajectorySamples
from interpolation_models import ContinuousTrajectory


@dataclass(frozen=True)
class CorrelationPeak:
    rank: int
    lag_seconds: float
    offset_seconds: float
    score: float
    overlap_seconds: float


def _elapsed_feature(
    samples: TrajectorySamples,
    trajectory: ContinuousTrajectory,
    grid_dt: float,
    feature: str,
) -> np.ndarray:
    elapsed = np.arange(0.0, samples.duration + 0.5 * grid_dt, grid_dt)
    elapsed = elapsed[elapsed <= samples.duration + 1e-12]
    pos = trajectory.evaluate(samples.start + elapsed)

    if feature == "position":
        value = pos
    elif feature == "velocity":
        # Numerical derivative after common-rate resampling avoids differences
        # caused solely by the original 4 Hz / 5 Hz sampling rates.
        value = np.gradient(pos, grid_dt, axis=0, edge_order=2)
    elif feature == "displacement":
        value = np.diff(pos, axis=0, prepend=pos[[0]])
    else:
        raise ValueError("feature must be 'position', 'velocity', or 'displacement'")

    scale = np.std(value, axis=0)
    scale[scale < 1e-12] = 1.0
    return (value - np.mean(value, axis=0)) / scale


def coarse_offset_candidates(
    stream1: TrajectorySamples,
    stream2: TrajectorySamples,
    traj1: ContinuousTrajectory,
    traj2: ContinuousTrajectory,
    *,
    grid_dt: float = 0.1,
    feature: str = "velocity",
    min_overlap_seconds: float = 60.0,
    min_peak_separation_seconds: float = 5.0,
    top_k: int = 8,
    offset_bounds: tuple[float, float] | None = None,
) -> list[CorrelationPeak]:
    """Return multiple plausible time-offset candidates ranked by NCC score.

    Sign convention:
        t2_aligned = t2 + Δt

    If `correlate(feature1, feature2)` peaks at elapsed-time lag L, then

        Δt = stream1.start + L - stream2.start.

    A single NCC maximum is deliberately NOT trusted as the final answer.
    """
    if grid_dt <= 0:
        raise ValueError("grid_dt must be positive.")
    if top_k < 1:
        raise ValueError("top_k must be >= 1.")

    f1 = _elapsed_feature(stream1, traj1, grid_dt, feature)
    f2 = _elapsed_feature(stream2, traj2, grid_dt, feature)

    # Sum channel-wise correlations (x/y or vx/vy).
    corr = np.zeros(f1.shape[0] + f2.shape[0] - 1, dtype=float)
    for c in range(2):
        corr += correlate(f1[:, c], f2[:, c], mode="full", method="fft")

    overlap_count = correlate(
        np.ones(f1.shape[0]),
        np.ones(f2.shape[0]),
        mode="full",
        method="fft",
    )
    overlap_count = np.maximum(overlap_count, 1.0)

    # Normalize by number of overlapping samples and number of channels.
    score = corr / (2.0 * overlap_count)
    lags = correlation_lags(f1.shape[0], f2.shape[0], mode="full")
    lag_seconds = lags.astype(float) * grid_dt
    offsets = stream1.start + lag_seconds - stream2.start
    overlap_seconds = overlap_count * grid_dt

    valid = overlap_seconds >= min_overlap_seconds
    if offset_bounds is not None:
        lo, hi = offset_bounds
        valid &= (offsets >= lo) & (offsets <= hi)

    work = np.where(valid, score, -np.inf)
    if not np.any(np.isfinite(work)):
        raise ValueError(
            "No cross-correlation lag satisfies the overlap/bounds constraints."
        )

    min_distance = max(1, int(round(min_peak_separation_seconds / grid_dt)))
    finite_for_peaks = np.where(np.isfinite(work), work, -1e100)
    peak_idx, _ = find_peaks(finite_for_peaks, distance=min_distance)

    # A monotone score curve can have no local peak; retain the global maximum.
    global_idx = int(np.nanargmax(work))
    if peak_idx.size == 0 or global_idx not in peak_idx:
        peak_idx = np.append(peak_idx, global_idx)

    order = peak_idx[np.argsort(work[peak_idx])[::-1]]
    result: list[CorrelationPeak] = []
    for rank, i in enumerate(order[:top_k], start=1):
        result.append(
            CorrelationPeak(
                rank=rank,
                lag_seconds=float(lag_seconds[i]),
                offset_seconds=float(offsets[i]),
                score=float(work[i]),
                overlap_seconds=float(overlap_seconds[i]),
            )
        )
    return result
