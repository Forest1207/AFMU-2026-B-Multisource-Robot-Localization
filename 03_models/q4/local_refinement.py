"""Optional local time refinement around the discrete 10 Hz MILP solution."""

from __future__ import annotations

import numpy as np

from candidate_generator import TaskCandidate, normalized_margin, with_refined_values
from feasible_windows import PhotographyRules, ShootingRules
from target_geometry import Target, circular_angle_difference_deg
from trajectory_state import TrajectoryState


def _interp(state: TrajectoryState, values: np.ndarray, t: np.ndarray) -> np.ndarray:
    return np.interp(t, state.time, values)


def _evaluate(
    state: TrajectoryState,
    target: Target,
    task_type: str,
    time: float,
    dense_dt: float,
    shooting_rules: ShootingRules,
    photo_rules: PhotographyRules,
) -> tuple[bool, float, float, float, float, float]:
    rules = shooting_rules if task_type == "shoot" else photo_rules
    start = time - rules.lead_time
    if start < state.time[0] - 1e-12 or time > state.time[-1] + 1e-12:
        return False, 0, 0, 0, 0, 0
    grid = np.arange(start, time + 0.5 * dense_dt, dense_dt)
    grid = np.r_[grid[grid < time], time]
    x = _interp(state, state.x, grid)
    y = _interp(state, state.y, grid)
    speed = _interp(state, state.speed, grid)
    accel = _interp(state, state.acceleration, grid)
    dist = np.hypot(target.x - x, target.y - y)
    ok = bool(
        np.all(dist >= rules.min_distance)
        and np.all(dist <= rules.max_distance)
        and np.all(speed <= rules.max_speed)
        and np.all(accel <= rules.max_acceleration)
    )
    if not ok:
        return False, 0, 0, 0, 0, 0
    d = float(dist[-1])
    v = float(speed[-1])
    a = float(accel[-1])
    bearing = float(np.degrees(np.mod(np.arctan2(target.y - y[-1], target.x - x[-1]), 2*np.pi)))
    q = normalized_margin(
        d, v, a, rules.min_distance, rules.max_distance,
        rules.max_speed, rules.max_acceleration,
    )
    return True, d, v, a, bearing, q


def refine_candidate(
    candidate: TaskCandidate,
    state: TrajectoryState,
    target: Target,
    radius: float = 0.1,
    dense_dt: float = 0.01,
    shooting_rules: ShootingRules = ShootingRules(),
    photo_rules: PhotographyRules = PhotographyRules(),
) -> TaskCandidate:
    """Search locally for a feasible time with larger safety margin."""
    if radius <= 0 or dense_dt <= 0:
        return candidate
    lo = max(state.time[0], candidate.time - radius)
    hi = min(state.time[-1], candidate.time + radius)
    times = np.arange(lo, hi + 0.5 * dense_dt, dense_dt)
    best = candidate
    for t in times:
        ok, d, v, a, bearing, q = _evaluate(
            state, target, candidate.task_type, float(t), dense_dt,
            shooting_rules, photo_rules,
        )
        if ok and q > best.quality + 1e-12:
            idx = int(np.argmin(np.abs(state.time - t)))
            best = with_refined_values(
                candidate,
                index=idx,
                time=float(t),
                distance=d,
                speed=v,
                acceleration=a,
                bearing_deg=bearing,
                quality=q,
            )
    return best


def validate_photo_angle_separation(
    selected: list[TaskCandidate], min_angle_deg: float = 60.0
) -> bool:
    by_target: dict[str, list[TaskCandidate]] = {}
    for c in selected:
        if c.task_type == "photo":
            by_target.setdefault(c.target_id, []).append(c)
    for group in by_target.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if circular_angle_difference_deg(
                    group[i].bearing_deg, group[j].bearing_deg
                ) + 1e-9 < min_angle_deg:
                    return False
    return True
