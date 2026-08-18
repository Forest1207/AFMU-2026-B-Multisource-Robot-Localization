"""Photography feasibility and angle-aware candidate generation for Q4."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from candidate_generator import TaskCandidate, normalized_margin
from feasible_windows import PhotographyRules, photography_feasible_mask, true_segments
from target_geometry import TargetGeometry
from trajectory_state import TrajectoryState


def build_photography_candidates(
    state: TrajectoryState,
    geometry: TargetGeometry,
    fs: float = 10.0,
    rules: PhotographyRules = PhotographyRules(),
    require_full_lead_window: bool = True,
    angle_bin_deg: float = 10.0,
) -> tuple[list[TaskCandidate], object]:
    if geometry.target.task_type != "photo":
        raise ValueError("target is not a photography target")
    if angle_bin_deg <= 0:
        raise ValueError("angle_bin_deg must be positive")

    mask = photography_feasible_mask(
        geometry.distance,
        state.speed,
        state.acceleration,
        fs=fs,
        rules=rules,
        require_full_lead_window=require_full_lead_window,
    )

    selected: set[int] = set()
    for start, end in true_segments(mask):
        idx = np.arange(start, end + 1, dtype=int)
        selected.update([int(start), int(end)])
        bins: dict[int, list[int]] = defaultdict(list)
        for j in idx:
            bins[int(np.floor(geometry.bearing_deg[j] / angle_bin_deg))].append(int(j))
        for members in bins.values():
            best_idx = max(
                members,
                key=lambda j: normalized_margin(
                    geometry.distance[j], state.speed[j], state.acceleration[j],
                    rules.min_distance, rules.max_distance,
                    rules.max_speed, rules.max_acceleration,
                ),
            )
            selected.add(best_idx)

    candidates: list[TaskCandidate] = []
    for idx in sorted(selected):
        q = normalized_margin(
            geometry.distance[idx], state.speed[idx], state.acceleration[idx],
            rules.min_distance, rules.max_distance,
            rules.max_speed, rules.max_acceleration,
        )
        t = float(state.time[idx])
        candidates.append(TaskCandidate(
            uid=f"P:{geometry.target.target_id}:{idx}",
            target_id=geometry.target.target_id,
            task_type="photo",
            index=int(idx),
            time=t,
            distance=float(geometry.distance[idx]),
            speed=float(state.speed[idx]),
            acceleration=float(state.acceleration[idx]),
            bearing_deg=float(geometry.bearing_deg[idx]),
            quality=q,
            resource_start=t - rules.lead_time,
            resource_end=t,
        ))
    return candidates, mask
