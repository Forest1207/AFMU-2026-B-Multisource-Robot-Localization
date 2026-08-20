"""Synthetic tests for unrestricted Q4 target-coverage scheduling."""

from __future__ import annotations

import sys

from feasible_windows import Candidate
from scheduler import optimize_schedule


def candidate(index: int, target: str, task: str, start: float, end: float,
              angle: float, margin: float) -> Candidate:
    return Candidate(index, target, task, start, end, angle, margin,
                     12.0, 20.0, 0.8, 0.5)


def circular(a: float, b: float) -> float:
    raw = abs(a - b) % 360.0
    return min(raw, 360.0 - raw)


def main() -> None:
    candidates = [
        candidate(0, "S01", "射击", 0.0, 1.5, 0.0, 0.40),
        candidate(1, "S01", "射击", 0.1, 1.6, 0.0, 0.45),  # only one shot may count
        candidate(2, "S02", "射击", 0.2, 1.7, 0.0, 0.48),  # overlapping time is allowed
        candidate(3, "P01", "拍照", 2.0, 2.5, 0.0, 0.42),
        candidate(4, "P01", "拍照", 2.1, 2.6, 70.0, 0.43),
        candidate(5, "P01", "拍照", 2.2, 2.7, 40.0, 0.49),  # conflicts with 0 and 70
        candidate(6, "P02", "拍照", 2.3, 2.8, 210.0, 0.44),
    ]
    result = optimize_schedule(candidates)

    # Four feasible target-task groups: S01, S02, P01, P02.
    assert result.coverage_count == 4
    assert result.photo_count == 3  # P01 can contribute two separated views + P02 one.
    assert len(result.selected) == 5

    shots = [item.target_id for item in result.selected if item.task == "射击"]
    assert len(shots) == len(set(shots)) == 2

    p01 = [item.angle_deg for item in result.selected if item.target_id == "P01"]
    assert len(p01) == 2
    assert circular(p01[0], p01[1]) >= 60.0

    # S01 and S02 preparation intervals overlap, demonstrating that no
    # unstated time-resource mutex is present in the formal model.
    s01 = next(item for item in result.selected if item.target_id == "S01")
    s02 = next(item for item in result.selected if item.target_id == "S02")
    assert not (
        s01.execution_time_s <= s02.preparation_start_s
        or s02.execution_time_s <= s01.preparation_start_s
    )

    assert result.stage1_gap == 0.0
    assert result.stage2_gap == 0.0
    assert result.stage3_gap == 0.0
    print("Synthetic Q4 target-coverage scheduler test passed")
    print("selected:", [(item.target_id, item.task, item.execution_time_s)
                        for item in result.selected])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
