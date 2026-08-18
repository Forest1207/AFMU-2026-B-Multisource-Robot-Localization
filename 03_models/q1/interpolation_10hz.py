"""Merge aligned noiseless samples and reconstruct the 10 Hz Q1 trajectory."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from data_loader import TrajectorySamples
from interpolation_models import InterpolationMethod, build_trajectory


@dataclass(frozen=True)
class MergeDiagnostics:
    n_stream1: int
    n_stream2: int
    n_merged: int
    duplicate_groups: int
    max_duplicate_disagreement_m: float
    max_time_gap_s: float


def aligned_stream2(
    stream2: TrajectorySamples,
    delta_t: float,
) -> TrajectorySamples:
    """Apply t2_aligned = t2 + Δt."""
    aligned = TrajectorySamples(
        name=f"{stream2.name}-aligned",
        time=stream2.time + float(delta_t),
        xy=stream2.xy.copy(),
        nominal_rate_hz=stream2.nominal_rate_hz,
    )
    return aligned


def merge_aligned_samples(
    stream1: TrajectorySamples,
    stream2_aligned: TrajectorySamples,
    *,
    duplicate_time_tol: float = 1e-7,
    duplicate_position_tol_m: float = 1e-5,
) -> tuple[TrajectorySamples, MergeDiagnostics]:
    """Merge the two noiseless streams on one time axis."""
    t = np.concatenate([stream1.time, stream2_aligned.time])
    xy = np.vstack([stream1.xy, stream2_aligned.xy])
    order = np.argsort(t, kind="mergesort")
    t = t[order]
    xy = xy[order]

    merged_t: list[float] = []
    merged_xy: list[np.ndarray] = []
    duplicate_groups = 0
    max_disagreement = 0.0

    i = 0
    while i < t.size:
        j = i + 1
        while j < t.size and abs(t[j] - t[i]) <= duplicate_time_tol:
            j += 1

        group_t = t[i:j]
        group_xy = xy[i:j]
        if j - i > 1:
            duplicate_groups += 1
            center = np.mean(group_xy, axis=0)
            disagreement = float(np.max(np.linalg.norm(group_xy - center, axis=1)))
            max_disagreement = max(max_disagreement, disagreement)
            if disagreement > duplicate_position_tol_m:
                raise ValueError(
                    "Aligned streams disagree at an identical timestamp: "
                    f"t≈{np.mean(group_t):.9f}s, disagreement={disagreement:.3e}m"
                )

        merged_t.append(float(np.mean(group_t)))
        merged_xy.append(np.mean(group_xy, axis=0))
        i = j

    mt = np.asarray(merged_t, dtype=float)
    mxy = np.asarray(merged_xy, dtype=float)
    if np.any(np.diff(mt) <= 0):
        raise ValueError("Merged time axis is not strictly increasing.")

    diagnostics = MergeDiagnostics(
        n_stream1=stream1.n,
        n_stream2=stream2_aligned.n,
        n_merged=int(mt.size),
        duplicate_groups=duplicate_groups,
        max_duplicate_disagreement_m=max_disagreement,
        max_time_gap_s=float(np.max(np.diff(mt))),
    )

    merged = TrajectorySamples(
        name="Q1-aligned-merged",
        time=mt,
        xy=mxy,
        nominal_rate_hz=10.0,
    )
    return merged, diagnostics


def reconstruct_10hz(
    merged: TrajectorySamples,
    *,
    method: InterpolationMethod = "cubic",
    output_start: float | None = None,
    output_end: float | None = None,
    output_hz: float = 10.0,
) -> pd.DataFrame:
    """Reconstruct continuous trajectory and sample at exactly 10 Hz."""
    if output_hz <= 0:
        raise ValueError("output_hz must be positive.")

    trajectory = build_trajectory(merged, method=method)
    start = merged.start if output_start is None else float(output_start)
    end = merged.end if output_end is None else float(output_end)

    if start < merged.start - 1e-12 or end > merged.end + 1e-12 or start > end:
        raise ValueError("Requested output range is outside merged observation support.")

    dt = 1.0 / output_hz
    n = int(np.floor((end - start) / dt + 1e-10)) + 1
    t = start + np.arange(n, dtype=float) * dt
    t = t[t <= end + 1e-10]
    xy = trajectory.evaluate(t)

    return pd.DataFrame(
        {
            "time": t,
            "x": xy[:, 0],
            "y": xy[:, 1],
        }
    )
