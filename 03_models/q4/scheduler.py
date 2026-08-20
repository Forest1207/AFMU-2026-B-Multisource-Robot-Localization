"""Lexicographic MILP scheduler for Q4 compressed candidates.

The formal model follows the competition statement and the reference-package
Q4 structure: there is no artificial nine-row capacity and no assumption that
preparation windows of different tasks are mutually exclusive.  The decision
problem is therefore driven by target coverage, repeated photographic views
and safety margin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack

import photography_model as photo
import shooting_model as shoot
from feasible_windows import Candidate


@dataclass(frozen=True)
class ScheduleResult:
    selected: list[Candidate]
    coverage_count: int
    photo_count: int
    total_margin: float
    stage1_status: int
    stage2_status: int
    stage3_status: int
    stage1_gap: float | None
    stage2_gap: float | None
    stage3_gap: float | None
    angle_conflict_count: int


def _gap(result) -> float | None:
    value = getattr(result, "mip_gap", None)
    return None if value is None else float(value)


def _build_base(candidates: list[Candidate]):
    """Build x/y linking, shooting uniqueness and photo-angle constraints."""
    n_x = len(candidates)
    groups: dict[tuple[str, str], list[int]] = {}
    for index, candidate in enumerate(candidates):
        groups.setdefault((candidate.task, candidate.target_id), []).append(index)

    group_keys = sorted(groups)
    y_index = {key: n_x + i for i, key in enumerate(group_keys)}
    n = n_x + len(group_keys)

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    row_id = 0

    def add(coefficients: dict[int, float], lo: float = -np.inf,
            hi: float = np.inf) -> None:
        nonlocal row_id
        for column, value in coefficients.items():
            rows.append(row_id)
            cols.append(column)
            vals.append(float(value))
        lower.append(float(lo))
        upper.append(float(hi))
        row_id += 1

    # y_g=1 iff at least one candidate for target-task group g is selected.
    for key in group_keys:
        ids = groups[key]
        y = y_index[key]
        add({**{j: 1.0 for j in ids}, y: -1.0}, lo=0.0)  # sum x - y >= 0
        add({**{j: 1.0 for j in ids}, y: -float(len(ids))}, hi=0.0)  # sum x <= M y
        if key[0] == shoot.TASK_NAME:
            add({j: 1.0 for j in ids}, hi=1.0)

    angle_conflicts = 0
    for key, ids in groups.items():
        if key[0] != photo.TASK_NAME:
            continue
        for position, i in enumerate(ids):
            for j in ids[position + 1:]:
                if photo.circular_separation_deg(
                    candidates[i].angle_deg, candidates[j].angle_deg
                ) < photo.MIN_ANGLE_SEPARATION_DEG - 1e-9:
                    add({i: 1.0, j: 1.0}, hi=1.0)
                    angle_conflicts += 1

    A = coo_matrix((vals, (rows, cols)), shape=(row_id, n)).tocsr()
    return A, np.asarray(lower), np.asarray(upper), y_index, angle_conflicts


def optimize_schedule(candidates: list[Candidate]) -> ScheduleResult:
    """Solve coverage -> photo count -> safety-margin lexicographic MILP."""
    if not candidates:
        raise ValueError("No continuously feasible candidates were generated.")

    n_x = len(candidates)
    base_A, base_lower, base_upper, y_index, angle_conflicts = _build_base(candidates)
    n = base_A.shape[1]
    y_ids = np.asarray(list(y_index.values()), dtype=int)
    photo_ids = np.asarray(
        [i for i, candidate in enumerate(candidates) if candidate.task == photo.TASK_NAME],
        dtype=int,
    )
    integrality = np.ones(n, dtype=int)
    bounds = Bounds(np.zeros(n), np.ones(n))

    def solve(c: np.ndarray, extra_rows=None, extra_lower=None, extra_upper=None):
        A = base_A
        lower = base_lower
        upper = base_upper
        if extra_rows:
            A = vstack([base_A] + extra_rows).tocsr()
            lower = np.concatenate([base_lower, np.asarray(extra_lower, dtype=float)])
            upper = np.concatenate([base_upper, np.asarray(extra_upper, dtype=float)])
        result = milp(
            c=c,
            integrality=integrality,
            bounds=bounds,
            constraints=LinearConstraint(A, lower, upper),
            options={"mip_rel_gap": 0.0, "presolve": True},
        )
        if not result.success:
            raise RuntimeError(f"Q4 MILP failed: {result.message}")
        return result

    c1 = np.zeros(n)
    c1[y_ids] = -1.0
    stage1 = solve(c1)
    coverage_count = int(round(float(np.sum(stage1.x[y_ids]))))

    fix_coverage = coo_matrix(
        (
            np.ones(len(y_ids), dtype=float),
            (np.zeros(len(y_ids), dtype=int), y_ids),
        ),
        shape=(1, n),
    ).tocsr()

    c2 = np.zeros(n)
    c2[photo_ids] = -1.0
    stage2 = solve(c2, [fix_coverage], [coverage_count], [coverage_count])
    photo_count = int(round(float(np.sum(stage2.x[photo_ids]))))

    fix_photo = coo_matrix(
        (
            np.ones(len(photo_ids), dtype=float),
            (np.zeros(len(photo_ids), dtype=int), photo_ids),
        ),
        shape=(1, n),
    ).tocsr()

    margins = np.asarray([candidate.normalized_margin for candidate in candidates], dtype=float)
    c3 = np.zeros(n)
    c3[:n_x] = -margins
    stage3 = solve(
        c3,
        [fix_coverage, fix_photo],
        [coverage_count, photo_count],
        [coverage_count, photo_count],
    )

    selected = [
        candidate
        for candidate, value in zip(candidates, stage3.x[:n_x], strict=True)
        if value > 0.5
    ]
    selected.sort(key=lambda item: (item.execution_time_s, item.task, item.target_id))

    return ScheduleResult(
        selected=selected,
        coverage_count=coverage_count,
        photo_count=photo_count,
        total_margin=float(sum(item.normalized_margin for item in selected)),
        stage1_status=int(stage1.status),
        stage2_status=int(stage2.status),
        stage3_status=int(stage3.status),
        stage1_gap=_gap(stage1),
        stage2_gap=_gap(stage2),
        stage3_gap=_gap(stage3),
        angle_conflict_count=angle_conflicts,
    )
