"""Lexicographic MILP scheduler for compressed Q4 candidates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix, vstack

import photography_model as photo
import shooting_model as shoot
from feasible_windows import Candidate


@dataclass(frozen=True)
class ScheduleResult:
    selected: list[Candidate]
    maximum_task_count: int
    minimum_margin: float
    stage1_status: int
    stage2_status: int
    stage3_status: int
    stage1_gap: float | None
    stage2_gap: float | None
    stage3_gap: float | None


def _gap(result) -> float | None:
    value = getattr(result, "mip_gap", None)
    return None if value is None else float(value)


def _base_constraints(candidates: list[Candidate]) -> tuple[lil_matrix, np.ndarray]:
    n = len(candidates)
    rows: list[tuple[int, int]] = []
    # Closed preparation/execution intervals may not overlap.  A 0.01 s gap
    # separates an execution instant from the next preparation interval.
    for i in range(n):
        a = candidates[i]
        for j in range(i + 1, n):
            b = candidates[j]
            separated = (
                a.execution_time_s + 0.01 <= b.preparation_start_s + 1e-9
                or b.execution_time_s + 0.01 <= a.preparation_start_s + 1e-9
            )
            if not separated:
                rows.append((i, j))
    shot_groups: dict[str, list[int]] = {}
    for index, candidate in enumerate(candidates):
        if candidate.task == shoot.TASK_NAME:
            shot_groups.setdefault(candidate.target_id, []).append(index)
    angle_conflicts: list[tuple[int, int]] = []
    photo_groups: dict[str, list[int]] = {}
    for index, candidate in enumerate(candidates):
        if candidate.task == photo.TASK_NAME:
            photo_groups.setdefault(candidate.target_id, []).append(index)
    for group in photo_groups.values():
        for position, i in enumerate(group):
            for j in group[position + 1:]:
                if photo.circular_separation_deg(
                    candidates[i].angle_deg, candidates[j].angle_deg
                ) < photo.MIN_ANGLE_SEPARATION_DEG - 1e-9:
                    angle_conflicts.append((i, j))

    total_rows = len(rows) + len(shot_groups) + len(angle_conflicts)
    matrix = lil_matrix((total_rows, n), dtype=float)
    upper = np.ones(total_rows, dtype=float)
    row = 0
    for i, j in rows:
        matrix[row, i] = matrix[row, j] = 1.0
        row += 1
    for group in shot_groups.values():
        matrix[row, group] = 1.0
        row += 1
    for i, j in angle_conflicts:
        matrix[row, i] = matrix[row, j] = 1.0
        row += 1
    return matrix, upper


def optimize_schedule(candidates: list[Candidate], capacity: int = 9) -> ScheduleResult:
    if not candidates:
        raise ValueError("No continuously feasible candidates were generated.")
    n = len(candidates)
    base_A, base_upper = _base_constraints(candidates)
    count_row = lil_matrix((1, n), dtype=float)
    count_row[0, :] = 1.0
    A1 = vstack([base_A, count_row]).tocsr()
    lower1 = np.r_[np.full(base_A.shape[0], -np.inf), -np.inf]
    upper1 = np.r_[base_upper, float(capacity)]
    stage1 = milp(
        c=-np.ones(n), integrality=np.ones(n), bounds=Bounds(0, 1),
        constraints=LinearConstraint(A1, lower1, upper1),
        options={"mip_rel_gap": 0.0},
    )
    if not stage1.success:
        raise RuntimeError(f"Stage-1 MILP failed: {stage1.message}")
    maximum_count = int(round(np.sum(stage1.x > 0.5)))

    # Stage 2: with the optimal count fixed, maximize the minimum normalized
    # constraint margin among selected candidates.
    A2 = lil_matrix((base_A.shape[0] + 1 + n, n + 1), dtype=float)
    A2[:base_A.shape[0], :n] = base_A
    A2[base_A.shape[0], :n] = 1.0
    margins = np.array([candidate.normalized_margin for candidate in candidates])
    big_m = 2.0
    for i, margin in enumerate(margins):
        A2[base_A.shape[0] + 1 + i, i] = big_m
        A2[base_A.shape[0] + 1 + i, n] = 1.0
    lower2 = np.r_[np.full(base_A.shape[0], -np.inf), maximum_count,
                   np.full(n, -np.inf)]
    upper2 = np.r_[base_upper, maximum_count, margins + big_m]
    c2 = np.zeros(n + 1)
    c2[-1] = -1.0
    stage2 = milp(
        c=c2, integrality=np.r_[np.ones(n), 0],
        bounds=Bounds(np.zeros(n + 1), np.r_[np.ones(n), 1.0]),
        constraints=LinearConstraint(A2.tocsr(), lower2, upper2),
        options={"mip_rel_gap": 0.0},
    )
    if not stage2.success:
        raise RuntimeError(f"Stage-2 MILP failed: {stage2.message}")
    minimum_margin = float(stage2.x[-1])

    # Stage 3: preserve the optimal minimum margin, then maximize total margin
    # and same-target photographic angular diversity via AND auxiliaries.
    eligible = margins >= minimum_margin - 1e-7
    photo_pairs: list[tuple[int, int, float]] = []
    groups: dict[str, list[int]] = {}
    for index, candidate in enumerate(candidates):
        if eligible[index] and candidate.task == photo.TASK_NAME:
            groups.setdefault(candidate.target_id, []).append(index)
    for group in groups.values():
        for position, i in enumerate(group):
            for j in group[position + 1:]:
                separation = photo.circular_separation_deg(
                    candidates[i].angle_deg, candidates[j].angle_deg
                )
                if separation >= photo.MIN_ANGLE_SEPARATION_DEG - 1e-9:
                    photo_pairs.append((i, j, separation / 180.0))
    p = len(photo_pairs)
    A3 = lil_matrix((base_A.shape[0] + 1 + 3 * p, n + p), dtype=float)
    A3[:base_A.shape[0], :n] = base_A
    A3[base_A.shape[0], :n] = 1.0
    lower3 = np.r_[np.full(base_A.shape[0], -np.inf), maximum_count,
                   np.full(3 * p, -np.inf)]
    upper3 = np.r_[base_upper, maximum_count, np.zeros(3 * p)]
    row = base_A.shape[0] + 1
    for pair_index, (i, j, _) in enumerate(photo_pairs):
        y = n + pair_index
        A3[row, y], A3[row, i] = 1.0, -1.0       # y <= xi
        A3[row + 1, y], A3[row + 1, j] = 1.0, -1.0  # y <= xj
        A3[row + 2, i], A3[row + 2, j], A3[row + 2, y] = 1.0, 1.0, -1.0
        upper3[row + 2] = 1.0                     # y >= xi+xj-1
        row += 3
    c3 = np.zeros(n + p)
    c3[:n] = -margins
    # Small expected-hit reward prevents arbitrary task labels without
    # overpowering margins; angular diversity is a genuine secondary reward.
    c3[:n] -= np.array([
        0.02 * shoot.HIT_PROBABILITY if candidate.task == shoot.TASK_NAME else 0.0
        for candidate in candidates
    ])
    if p:
        c3[n:] = -0.25 * np.array([pair[2] for pair in photo_pairs])
    lower_bounds = np.zeros(n + p)
    upper_bounds = np.ones(n + p)
    upper_bounds[:n] = eligible.astype(float)
    stage3 = milp(
        c=c3, integrality=np.ones(n + p),
        bounds=Bounds(lower_bounds, upper_bounds),
        constraints=LinearConstraint(A3.tocsr(), lower3, upper3),
        options={"mip_rel_gap": 0.0},
    )
    if not stage3.success:
        raise RuntimeError(f"Stage-3 MILP failed: {stage3.message}")
    selected = [candidate for candidate, value in zip(candidates, stage3.x[:n], strict=True)
                if value > 0.5]
    selected.sort(key=lambda candidate: candidate.execution_time_s)
    return ScheduleResult(
        selected=selected,
        maximum_task_count=maximum_count,
        minimum_margin=min(candidate.normalized_margin for candidate in selected),
        stage1_status=int(stage1.status), stage2_status=int(stage2.status),
        stage3_status=int(stage3.status), stage1_gap=_gap(stage1),
        stage2_gap=_gap(stage2), stage3_gap=_gap(stage3),
    )
