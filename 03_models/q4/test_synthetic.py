"""Synthetic unit tests for Q4 feasibility and scheduling constraints."""

from __future__ import annotations

import sys

from feasible_windows import Candidate
from scheduler import optimize_schedule


def candidate(index: int, target: str, task: str, start: float, end: float,
              angle: float, margin: float) -> Candidate:
    return Candidate(index, target, task, start, end, angle, margin,
                     12.0, 20.0, 0.8, 0.5)


def main() -> None:
    candidates = [
        candidate(0, "S01", "射击", 0.0, 1.5, 0.0, 0.40),
        candidate(1, "S01", "射击", 3.0, 4.5, 0.0, 0.45),  # same shot target
        candidate(2, "P01", "拍照", 2.0, 2.5, 0.0, 0.42),
        candidate(3, "P01", "拍照", 5.0, 5.5, 70.0, 0.43),
        candidate(4, "P01", "拍照", 6.0, 6.5, 40.0, 0.49),  # angular conflict
        candidate(5, "P02", "拍照", 7.0, 7.5, 210.0, 0.44),
        candidate(6, "S02", "射击", 7.2, 8.7, 0.0, 0.48),  # temporal conflict
    ]
    result = optimize_schedule(candidates, capacity=4)
    assert result.maximum_task_count == 4
    assert len(result.selected) == 4
    shots = [item.target_id for item in result.selected if item.task == "射击"]
    assert len(shots) == len(set(shots))
    p01 = [item.angle_deg for item in result.selected if item.target_id == "P01"]
    if len(p01) == 2:
        separation = abs(p01[0] - p01[1]) % 360
        assert min(separation, 360 - separation) >= 60
    assert result.stage1_gap == 0.0
    assert result.stage2_gap == 0.0
    assert result.stage3_gap == 0.0
    print("Synthetic Q4 scheduler test passed")
    print("selected:", [(item.target_id, item.task, item.execution_time_s)
                        for item in result.selected])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
