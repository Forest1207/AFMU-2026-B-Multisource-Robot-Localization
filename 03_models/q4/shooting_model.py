"""Shooting feasibility and candidate generation for Q4."""

from __future__ import annotations

from candidate_generator import TaskCandidate, normalized_margin, representative_indices
from feasible_windows import ShootingRules, shooting_feasible_mask
from target_geometry import TargetGeometry
from trajectory_state import TrajectoryState


def build_shooting_candidates(
    state: TrajectoryState,
    geometry: TargetGeometry,
    fs: float = 10.0,
    rules: ShootingRules = ShootingRules(),
    max_per_segment: int = 5,
) -> tuple[list[TaskCandidate], object]:
    if geometry.target.task_type != "shoot":
        raise ValueError("target is not a shooting target")
    mask = shooting_feasible_mask(
        geometry.distance, state.speed, state.acceleration, fs=fs, rules=rules
    )
    indices = representative_indices(
        mask,
        geometry.distance,
        state.speed,
        state.acceleration,
        rules.min_distance,
        rules.max_distance,
        max_per_segment=max_per_segment,
    )
    candidates: list[TaskCandidate] = []
    for idx in indices:
        q = normalized_margin(
            geometry.distance[idx], state.speed[idx], state.acceleration[idx],
            rules.min_distance, rules.max_distance,
            rules.max_speed, rules.max_acceleration,
        )
        t = float(state.time[idx])
        candidates.append(TaskCandidate(
            uid=f"S:{geometry.target.target_id}:{idx}",
            target_id=geometry.target.target_id,
            task_type="shoot",
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


def hit_probability(number_of_shots: int, single_shot_probability: float = 0.85) -> float:
    """Probability of at least one hit under independent repeated shots."""
    if number_of_shots < 0:
        raise ValueError("number_of_shots must be non-negative")
    if not 0.0 <= single_shot_probability <= 1.0:
        raise ValueError("single_shot_probability must lie in [0, 1]")
    return 1.0 - (1.0 - single_shot_probability) ** number_of_shots
