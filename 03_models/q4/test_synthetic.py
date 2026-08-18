"""Small dependency-light smoke tests for Q4 modules.

Run from this directory with: python test_synthetic.py
"""

from __future__ import annotations

import numpy as np

from candidate_generator import TaskCandidate
from conflict_builder import build_photo_angle_conflicts
from feasible_windows import lead_window_samples, rolling_all
from scheduler import solve_lexicographic
from target_geometry import circular_angle_difference_deg
from trajectory_state import reconstruct_state


def candidate(uid: str, target: str, task: str, bearing: float, q: float) -> TaskCandidate:
    return TaskCandidate(
        uid=uid,
        target_id=target,
        task_type=task,
        index=0,
        time=float(len(uid)),
        distance=20.0,
        speed=1.0,
        acceleration=0.5,
        bearing_deg=bearing,
        quality=q,
        resource_start=0.0,
        resource_end=1.0,
    )


def test_trajectory_state() -> None:
    t = np.arange(0.0, 5.01, 0.5)
    xy = np.column_stack([t, 0.5 * t])
    state = reconstruct_state(t, xy, fs=10.0, smoothing=0.0)
    assert np.allclose(state.speed[5:-5], np.hypot(1.0, 0.5), atol=1e-6)
    assert np.max(np.abs(state.acceleration[5:-5])) < 1e-5


def test_sliding_window() -> None:
    mask = np.array([1, 1, 1, 0, 1, 1], dtype=bool)
    assert lead_window_samples(0.5, 10.0) == 6
    out = rolling_all(mask, 3)
    assert out.tolist() == [False, False, True, False, False, False]


def test_angles_and_milp() -> None:
    assert abs(circular_angle_difference_deg(359, 1) - 2.0) < 1e-12
    cs = [
        candidate("p1", "P1", "photo", 10.0, 0.7),
        candidate("p2", "P1", "photo", 40.0, 0.9),  # conflicts with p1
        candidate("p3", "P1", "photo", 100.0, 0.8),
        candidate("s1", "S1", "shoot", 0.0, 0.6),
        candidate("s2", "S1", "shoot", 0.0, 0.9),
    ]
    conflicts = build_photo_angle_conflicts(cs, min_angle_deg=60.0)
    result = solve_lexicographic(cs, conflicts=conflicts, single_shot_per_target=True)
    assert result.covered_targets == 2
    assert result.photo_count == 2
    assert sum(c.task_type == "shoot" for c in result.selected) == 1
    assert any(c.uid == "p3" for c in result.selected)


if __name__ == "__main__":
    test_trajectory_state()
    test_sliding_window()
    test_angles_and_milp()
    print("Q4 synthetic smoke tests passed.")
