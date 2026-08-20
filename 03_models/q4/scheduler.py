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
    # Interval graphs are perfect: one constraint for every maximal active set
    # is equivalent to all pairwise resource-conflict constraints.  Using
    # cliques keeps the uncapped model compact enough for exact MILP solution.
    resource_cliques: list[tuple[int, ...]] = []
    starts = sorted({candidate.preparation_start_s for candidate in candidates})
    for time_s in starts:
        active = tuple(
            i for i, candidate in enumerate(candidates)
            if candidate.preparation_start_s <= time_s + 1e-9
            and candidate.execution_time_s + 0.01 > time_s + 1e-9
        )
        if len(active) > 1:
            resource_cliques.append(active)
    maximal_cliques = [
        clique for i, clique in enumerate(resource_cliques)
        if not any(set(clique) < set(other) for other in resource_cliques[i + 1:])
    ]
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

    total_rows = len(maximal_cliques) + len(shot_groups) + len(angle_conflicts)
    matrix = lil_matrix((total_rows, n), dtype=float)
    upper = np.ones(total_rows, dtype=float)
    row = 0
    for clique in maximal_cliques:
        matrix[row, list(clique)] = 1.0
        row += 1
    for group in shot_groups.values():
        matrix[row, group] = 1.0
        row += 1
    for i, j in angle_conflicts:
        matrix[row, i] = matrix[row, j] = 1.0
        row += 1
    return matrix, upper


def optimize_schedule(candidates: list[Candidate], capacity: int | None = None) -> ScheduleResult:
    if not candidates:
        raise ValueError("No continuously feasible candidates were generated.")
    n = len(candidates)
    base_A, base_upper = _base_constraints(candidates)
    if capacity is None:
        A1 = base_A.tocsr()
        lower1 = np.full(base_A.shape[0], -np.inf)
        upper1 = base_upper
    else:
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

    margins = np.array([candidate.normalized_margin for candidate in candidates])
    # Stage 2: the selected minimum is one of the finite candidate margins.
    # Binary search therefore avoids a weak big-M max-min formulation.
    margin_levels = np.unique(margins)
    left, right, best = 0, len(margin_levels) - 1, 0
    stage2 = stage1
    while left <= right:
        middle = (left + right) // 2
        eligible = (margins >= margin_levels[middle] - 1e-12).astype(float)
        trial = milp(
            c=-np.ones(n), integrality=np.ones(n),
            bounds=Bounds(np.zeros(n), eligible),
            constraints=LinearConstraint(
                base_A.tocsr(), np.full(base_A.shape[0], -np.inf), base_upper
            ),
            options={"mip_rel_gap": 0.0},
        )
        if trial.success and int(round(-trial.fun)) >= maximum_count:
            best, stage2, left = middle, trial, middle + 1
        else:
            right = middle - 1
    minimum_margin = float(margin_levels[best])

    # Stage 3: preserve count and best minimum margin, then maximize total
    # normalized margin.  Angular diversity remains a hard feasibility rule.
    eligible = (margins >= minimum_margin - 1e-12).astype(float)
    count_row = lil_matrix((1, n), dtype=float)
    count_row[0, :] = 1.0
    A3 = vstack([base_A, count_row]).tocsr()
    lower3 = np.r_[np.full(base_A.shape[0], -np.inf), maximum_count]
    upper3 = np.r_[base_upper, maximum_count]
    stage3 = milp(
        c=-margins, integrality=np.ones(n),
        bounds=Bounds(np.zeros(n), eligible),
        constraints=LinearConstraint(A3, lower3, upper3),
        options={"mip_rel_gap": 0.0},
    )
    if not stage3.success:
        raise RuntimeError(f"Stage-3 MILP failed: {stage3.message}")
    selected = [candidate for candidate, value in zip(candidates, stage3.x, strict=True)
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
