"""Q1 fixed time-offset estimation.

Main model:
    Δt* = argmin J(Δt),
    J(Δt) = mean ||r1(t) - r2(t - Δt)||^2

Sign convention:
    t2_aligned = t2 + Δt

Cross-correlation is only used to generate coarse candidate offsets. Final
selection is based on position-domain MSE and bounded continuous optimization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from cross_correlation import CorrelationPeak, coarse_offset_candidates
from data_loader import TrajectorySamples
from interpolation_models import ContinuousTrajectory


@dataclass(frozen=True)
class LossResult:
    mse: float
    rmse: float
    overlap_start: float
    overlap_end: float
    overlap_seconds: float
    n_eval: int


@dataclass(frozen=True)
class AlignmentResult:
    time_offset_s: float
    loss: LossResult
    feasible_bounds: tuple[float, float]
    coarse_best_offset_s: float
    coarse_best_mse: float
    correlation_candidates: tuple[CorrelationPeak, ...]
    boundary_distance_s: float

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sign_convention"] = "t2_aligned = t2 + time_offset_s"
        return data


def feasible_offset_bounds(
    stream1: TrajectorySamples,
    stream2: TrajectorySamples,
    min_overlap_seconds: float,
) -> tuple[float, float]:
    """Offsets that preserve at least `min_overlap_seconds` of overlap."""
    lower = stream1.start + min_overlap_seconds - stream2.end
    upper = stream1.end - min_overlap_seconds - stream2.start
    if lower >= upper:
        raise ValueError(
            "The requested minimum overlap is impossible for the two streams."
        )
    return float(lower), float(upper)


def alignment_loss(
    delta_t: float,
    traj1: ContinuousTrajectory,
    traj2: ContinuousTrajectory,
    *,
    eval_dt: float = 0.1,
    min_overlap_seconds: float = 60.0,
) -> LossResult:
    """Evaluate position MSE on the valid common true-time interval."""
    start = max(traj1.t_min, traj2.t_min + delta_t)
    end = min(traj1.t_max, traj2.t_max + delta_t)
    overlap = end - start
    if overlap < min_overlap_seconds:
        return LossResult(
            mse=float("inf"),
            rmse=float("inf"),
            overlap_start=float(start),
            overlap_end=float(end),
            overlap_seconds=float(max(0.0, overlap)),
            n_eval=0,
        )

    t = np.arange(start, end + 0.5 * eval_dt, eval_dt)
    t = t[t <= end + 1e-12]
    p1 = traj1.evaluate(t)
    p2 = traj2.evaluate(t - delta_t)
    squared = np.sum((p1 - p2) ** 2, axis=1)
    mse = float(np.mean(squared))
    return LossResult(
        mse=mse,
        rmse=float(np.sqrt(mse)),
        overlap_start=float(start),
        overlap_end=float(end),
        overlap_seconds=float(overlap),
        n_eval=int(t.size),
    )


def coarse_grid_search(
    bounds: tuple[float, float],
    traj1: ContinuousTrajectory,
    traj2: ContinuousTrajectory,
    *,
    step: float = 0.5,
    eval_dt: float = 0.2,
    min_overlap_seconds: float = 60.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Global coarse scan used as a safety net against false NCC peaks."""
    lo, hi = bounds
    grid = np.arange(lo, hi + 0.5 * step, step)
    grid = grid[grid <= hi + 1e-12]
    mse = np.array(
        [
            alignment_loss(
                d,
                traj1,
                traj2,
                eval_dt=eval_dt,
                min_overlap_seconds=min_overlap_seconds,
            ).mse
            for d in grid
        ],
        dtype=float,
    )
    return grid, mse


def _refine_around_seed(
    seed: float,
    bounds: tuple[float, float],
    traj1: ContinuousTrajectory,
    traj2: ContinuousTrajectory,
    *,
    half_width: float,
    eval_dt: float,
    min_overlap_seconds: float,
    xatol: float,
) -> tuple[float, LossResult]:
    lo = max(bounds[0], seed - half_width)
    hi = min(bounds[1], seed + half_width)
    if not lo < hi:
        return seed, alignment_loss(
            seed,
            traj1,
            traj2,
            eval_dt=eval_dt,
            min_overlap_seconds=min_overlap_seconds,
        )

    # Freeze one evaluation grid for the whole local bracket.  If the grid
    # were rebuilt from the candidate-dependent overlap start, tiny changes in
    # ``delta_t`` would also shift every evaluation timestamp.  That makes the
    # numerical objective slightly non-smooth and can move a noiseless optimum
    # by about 1e-6 s.  The interval below is valid for every d in [lo, hi].
    fixed_start = max(traj1.t_min, traj2.t_min + hi)
    fixed_end = min(traj1.t_max, traj2.t_max + lo)
    if fixed_end - fixed_start < min_overlap_seconds:
        return seed, alignment_loss(
            seed,
            traj1,
            traj2,
            eval_dt=eval_dt,
            min_overlap_seconds=min_overlap_seconds,
        )

    eval_time = np.arange(fixed_start, fixed_end + 0.5 * eval_dt, eval_dt)
    eval_time = eval_time[eval_time <= fixed_end + 1e-12]
    position1 = traj1.evaluate(eval_time)

    def fixed_grid_mse(delta_t: float) -> float:
        position2 = traj2.evaluate(eval_time - float(delta_t))
        return float(np.mean(np.sum((position1 - position2) ** 2, axis=1)))

    result = minimize_scalar(
        fixed_grid_mse,
        bounds=(lo, hi),
        method="bounded",
        options={"xatol": xatol, "maxiter": 1000},
    )
    dt = float(result.x)
    return dt, alignment_loss(
        dt,
        traj1,
        traj2,
        eval_dt=eval_dt,
        min_overlap_seconds=min_overlap_seconds,
    )


def estimate_time_offset(
    stream1: TrajectorySamples,
    stream2: TrajectorySamples,
    traj1: ContinuousTrajectory,
    traj2: ContinuousTrajectory,
    *,
    min_overlap_seconds: float = 60.0,
    corr_grid_dt: float = 0.1,
    corr_feature: str = "velocity",
    corr_top_k: int = 8,
    coarse_step: float = 0.5,
    coarse_eval_dt: float = 0.2,
    refine_half_width: float | None = None,
    final_eval_dt: float = 0.05,
    xatol: float = 1e-10,
) -> tuple[AlignmentResult, np.ndarray, np.ndarray]:
    """Estimate Δt with NCC candidates + global coarse scan + continuous refine."""
    bounds = feasible_offset_bounds(stream1, stream2, min_overlap_seconds)

    candidates = coarse_offset_candidates(
        stream1,
        stream2,
        traj1,
        traj2,
        grid_dt=corr_grid_dt,
        feature=corr_feature,
        min_overlap_seconds=min_overlap_seconds,
        top_k=corr_top_k,
        offset_bounds=bounds,
    )

    # Correlation score alone can choose a periodic false peak. Re-rank candidates
    # by the actual position-domain objective before refinement.
    candidate_mse = [
        alignment_loss(
            c.offset_seconds,
            traj1,
            traj2,
            eval_dt=coarse_eval_dt,
            min_overlap_seconds=min_overlap_seconds,
        ).mse
        for c in candidates
    ]

    global_grid, global_mse = coarse_grid_search(
        bounds,
        traj1,
        traj2,
        step=coarse_step,
        eval_dt=coarse_eval_dt,
        min_overlap_seconds=min_overlap_seconds,
    )
    global_best_idx = int(np.nanargmin(global_mse))
    coarse_global_seed = float(global_grid[global_best_idx])

    # Use both the best NCC-derived seed and the global-grid seed.
    seeds = [coarse_global_seed]
    if candidates:
        seeds.append(float(candidates[int(np.argmin(candidate_mse))].offset_seconds))

    if refine_half_width is None:
        refine_half_width = max(2.0 * coarse_step, 1.0)

    refined: list[tuple[float, LossResult]] = []
    for seed in seeds:
        refined.append(
            _refine_around_seed(
                seed,
                bounds,
                traj1,
                traj2,
                half_width=refine_half_width,
                eval_dt=final_eval_dt,
                min_overlap_seconds=min_overlap_seconds,
                xatol=xatol,
            )
        )

    best_dt, best_loss = min(refined, key=lambda item: item[1].mse)
    boundary_distance = min(best_dt - bounds[0], bounds[1] - best_dt)

    alignment = AlignmentResult(
        time_offset_s=float(best_dt),
        loss=best_loss,
        feasible_bounds=bounds,
        coarse_best_offset_s=coarse_global_seed,
        coarse_best_mse=float(global_mse[global_best_idx]),
        correlation_candidates=tuple(candidates),
        boundary_distance_s=float(boundary_distance),
    )
    return alignment, global_grid, global_mse
