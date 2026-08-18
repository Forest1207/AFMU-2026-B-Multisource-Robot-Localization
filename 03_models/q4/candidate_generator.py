"""Shared task-candidate structures and compression utilities for Q4."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from feasible_windows import true_segments


@dataclass(frozen=True)
class TaskCandidate:
    uid: str
    target_id: str
    task_type: str
    index: int
    time: float
    distance: float
    speed: float
    acceleration: float
    bearing_deg: float
    quality: float
    resource_start: float
    resource_end: float


def normalized_margin(
    distance: float,
    speed: float,
    acceleration: float,
    min_distance: float,
    max_distance: float,
    max_speed: float,
    max_acceleration: float,
) -> float:
    """Conservative [approximately 0, 1] margin to all hard constraints."""
    half_width = max((max_distance - min_distance) / 2.0, 1e-12)
    d_margin = min(distance - min_distance, max_distance - distance) / half_width
    v_margin = (max_speed - speed) / max(max_speed, 1e-12)
    a_margin = (max_acceleration - acceleration) / max(max_acceleration, 1e-12)
    return float(np.clip(min(d_margin, v_margin, a_margin), 0.0, 1.0))


def representative_indices(
    feasible_mask: np.ndarray,
    distance: np.ndarray,
    speed: np.ndarray,
    acceleration: np.ndarray,
    min_distance: float,
    max_distance: float,
    max_per_segment: int = 5,
) -> list[int]:
    """Compress each feasible segment while retaining physically meaningful points."""
    if max_per_segment < 1:
        raise ValueError("max_per_segment must be >= 1")
    out: list[int] = []
    center = 0.5 * (min_distance + max_distance)
    for start, end in true_segments(feasible_mask):
        idx = np.arange(start, end + 1)
        picks = {
            int(start),
            int(end),
            int(idx[np.argmin(np.abs(distance[idx] - center))]),
            int(idx[np.argmin(speed[idx])]),
            int(idx[np.argmin(acceleration[idx])]),
        }
        picks = sorted(picks)
        if len(picks) > max_per_segment:
            # Keep endpoints, then the most evenly distributed interior points.
            if max_per_segment == 1:
                picks = [picks[len(picks) // 2]]
            else:
                positions = np.linspace(0, len(picks) - 1, max_per_segment).round().astype(int)
                picks = sorted({picks[j] for j in positions})
        out.extend(picks)
    return sorted(set(out))


def with_refined_values(
    candidate: TaskCandidate,
    *,
    index: int,
    time: float,
    distance: float,
    speed: float,
    acceleration: float,
    bearing_deg: float,
    quality: float,
) -> TaskCandidate:
    duration = candidate.resource_end - candidate.resource_start
    return replace(
        candidate,
        index=index,
        time=time,
        distance=distance,
        speed=speed,
        acceleration=acceleration,
        bearing_deg=bearing_deg,
        quality=quality,
        resource_start=time - duration,
        resource_end=time,
    )
