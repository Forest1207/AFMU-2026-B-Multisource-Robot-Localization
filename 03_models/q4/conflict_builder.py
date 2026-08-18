"""Conflict graph construction for Q4 candidate tasks."""

from __future__ import annotations

from itertools import combinations

from candidate_generator import TaskCandidate
from target_geometry import circular_angle_difference_deg


def build_photo_angle_conflicts(
    candidates: list[TaskCandidate],
    min_angle_deg: float = 60.0,
    atol: float = 1e-9,
) -> set[tuple[int, int]]:
    """Return candidate-index pairs that violate photo angle separation."""
    if min_angle_deg < 0 or min_angle_deg > 180:
        raise ValueError("min_angle_deg must lie in [0, 180]")
    conflicts: set[tuple[int, int]] = set()
    by_target: dict[str, list[int]] = {}
    for i, c in enumerate(candidates):
        if c.task_type == "photo":
            by_target.setdefault(c.target_id, []).append(i)
    for indices in by_target.values():
        for i, j in combinations(indices, 2):
            delta = circular_angle_difference_deg(
                candidates[i].bearing_deg, candidates[j].bearing_deg
            )
            if delta + atol < min_angle_deg:
                conflicts.add((min(i, j), max(i, j)))
    return conflicts


def build_resource_conflicts(
    candidates: list[TaskCandidate],
    atol: float = 1e-9,
) -> set[tuple[int, int]]:
    """Optional conflicts if preparation windows are modeled as exclusive resources.

    This is an engineering extension, not a hard constraint unless supported by
    the final interpretation of the problem statement.
    """
    conflicts: set[tuple[int, int]] = set()
    for i, j in combinations(range(len(candidates)), 2):
        a, b = candidates[i], candidates[j]
        overlap = max(a.resource_start, b.resource_start) < min(
            a.resource_end, b.resource_end
        ) - atol
        same_end = abs(a.resource_end - b.resource_end) <= atol
        if overlap or same_end:
            conflicts.add((i, j))
    return conflicts


def merge_conflicts(*sets_: set[tuple[int, int]]) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for pairs in sets_:
        out.update((min(i, j), max(i, j)) for i, j in pairs if i != j)
    return out
