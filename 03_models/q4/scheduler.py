"""Lexicographic binary MILP scheduler for Q4."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, lil_matrix, vstack

from candidate_generator import TaskCandidate


@dataclass(frozen=True)
class ScheduleResult:
    selected: list[TaskCandidate]
    covered_targets: int
    photo_count: int
    quality_sum: float
    solver_messages: tuple[str, str, str]


def _solve(c: np.ndarray, A: csr_matrix, lb: np.ndarray, ub: np.ndarray):
    n = c.size
    result = milp(
        c=c,
        integrality=np.ones(n, dtype=int),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(A, lb, ub),
        options={"presolve": True},
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"MILP failed: {result.message}")
    return result


def solve_lexicographic(
    candidates: list[TaskCandidate],
    conflicts: set[tuple[int, int]] | None = None,
    single_shot_per_target: bool = True,
) -> ScheduleResult:
    """Solve Q4 in three stages: coverage -> photo count -> safety quality."""
    if not candidates:
        return ScheduleResult([], 0, 0, 0.0, ("no candidates",) * 3)
    conflicts = conflicts or set()
    n = len(candidates)

    # Coverage variables y_g represent completion of each (task_type, target_id).
    group_keys = sorted({(c.task_type, c.target_id) for c in candidates})
    group_index = {key: j for j, key in enumerate(group_keys)}
    g = len(group_keys)
    total_vars = n + g

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    def add_row(coeff: dict[int, float], lo: float, hi: float) -> None:
        rows.append(coeff)
        lower.append(lo)
        upper.append(hi)

    # y_g == OR(x_j in group), linearized as y <= sum x and x_j <= y.
    members: dict[tuple[str, str], list[int]] = {key: [] for key in group_keys}
    for j, c in enumerate(candidates):
        members[(c.task_type, c.target_id)].append(j)
    for key, idxs in members.items():
        y = n + group_index[key]
        add_row({y: 1.0, **{j: -1.0 for j in idxs}}, -np.inf, 0.0)
        for j in idxs:
            add_row({j: 1.0, y: -1.0}, -np.inf, 0.0)
        if single_shot_per_target and key[0] == "shoot":
            add_row({j: 1.0 for j in idxs}, -np.inf, 1.0)

    for i, j in sorted(conflicts):
        if not (0 <= i < n and 0 <= j < n) or i == j:
            raise ValueError(f"invalid conflict pair {(i, j)}")
        add_row({i: 1.0, j: 1.0}, -np.inf, 1.0)

    A = lil_matrix((len(rows), total_vars), dtype=float)
    for r, coeff in enumerate(rows):
        for col, value in coeff.items():
            A[r, col] = value
    A = A.tocsr()
    lb = np.asarray(lower, dtype=float)
    ub = np.asarray(upper, dtype=float)

    # Stage 1: maximize number of covered task-target groups.
    c1 = np.zeros(total_vars)
    c1[n:] = -1.0
    r1 = _solve(c1, A, lb, ub)
    coverage_star = int(round(np.sum(r1.x[n:])))

    coverage_row = csr_matrix(
        (np.ones(g), (np.zeros(g, dtype=int), np.arange(n, n + g))),
        shape=(1, total_vars),
    )
    A2 = vstack([A, coverage_row], format="csr")
    lb2 = np.r_[lb, coverage_star]
    ub2 = np.r_[ub, coverage_star]

    # Stage 2: among maximum-coverage solutions, maximize valid photo count.
    c2 = np.zeros(total_vars)
    photo_indices = [i for i, c in enumerate(candidates) if c.task_type == "photo"]
    c2[photo_indices] = -1.0
    r2 = _solve(c2, A2, lb2, ub2)
    photo_star = int(round(np.sum(r2.x[photo_indices]))) if photo_indices else 0

    photo_row = lil_matrix((1, total_vars), dtype=float)
    for i in photo_indices:
        photo_row[0, i] = 1.0
    A3 = vstack([A2, photo_row.tocsr()], format="csr")
    lb3 = np.r_[lb2, photo_star]
    ub3 = np.r_[ub2, photo_star]

    # Stage 3: maximize robustness/safety margin without sacrificing stages 1-2.
    c3 = np.zeros(total_vars)
    c3[:n] = -np.asarray([max(0.0, c.quality) for c in candidates])
    r3 = _solve(c3, A3, lb3, ub3)

    chosen_idx = np.flatnonzero(r3.x[:n] > 0.5).tolist()
    selected = sorted((candidates[i] for i in chosen_idx), key=lambda c: c.time)
    return ScheduleResult(
        selected=selected,
        covered_targets=coverage_star,
        photo_count=photo_star,
        quality_sum=float(sum(c.quality for c in selected)),
        solver_messages=(str(r1.message), str(r2.message), str(r3.message)),
    )
