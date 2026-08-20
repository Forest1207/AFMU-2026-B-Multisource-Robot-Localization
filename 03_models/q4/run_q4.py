"""Run Q4 candidate generation, MILP scheduling and template-preserving export."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy.interpolate import PchipInterpolator

import photography_model as photo
import shooting_model as shoot
from feasible_windows import (
    Candidate,
    _continuous_metrics,
    generate_candidates,
    load_targets,
)
from scheduler import optimize_schedule
from trajectory_state import TrajectoryState


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cell_signature(cell) -> dict:
    return {
        "value": cell.value,
        "style_id": cell.style_id,
        "number_format": cell.number_format,
        "font": str(cell.font),
        "fill": str(cell.fill),
        "border": str(cell.border),
        "alignment": str(cell.alignment),
        "protection": str(cell.protection),
    }


def _untouched_snapshot(path: str | Path) -> dict:
    wb = load_workbook(path, data_only=False)
    ws = wb[wb.sheetnames[0]]
    cells = {}
    for row in range(1, min(ws.max_row, 10) + 1):
        for column in range(8, ws.max_column + 1):
            cell = ws.cell(row, column)
            cells[cell.coordinate] = _cell_signature(cell)
    return {
        "sheetnames": wb.sheetnames,
        "merged": [str(item) for item in ws.merged_cells.ranges],
        "freeze_panes": str(ws.freeze_panes),
        "instruction_cells": cells,
    }


def _rounded_and_verified(selected: list[Candidate], trajectory: TrajectoryState,
                          targets) -> list[Candidate]:
    target_map = {target.target_id: target for target in targets}
    rounded = []
    for candidate in selected:
        start = round(candidate.preparation_start_s, 2)
        end = round(candidate.execution_time_s, 2)
        metrics = _continuous_metrics(
            trajectory, target_map[candidate.target_id], start, end, 0.01
        )
        if metrics["margin"] < -1e-9:
            raise RuntimeError("Two-decimal schedule time failed 0.01 s recheck.")
        rounded.append(replace(
            candidate,
            preparation_start_s=start,
            execution_time_s=end,
            angle_deg=metrics["angle_deg"],
            normalized_margin=metrics["margin"],
            min_distance_m=metrics["min_distance_m"],
            max_distance_m=metrics["max_distance_m"],
            max_speed_mps=metrics["max_speed_mps"],
            max_acceleration_mps2=metrics["max_acceleration_mps2"],
        ))
    rounded.sort(key=lambda item: item.execution_time_s)
    return rounded


def _compatible(candidate: Candidate, selected: list[Candidate]) -> bool:
    for other in selected:
        separated = (
            candidate.execution_time_s + 0.01 <= other.preparation_start_s + 1e-9
            or other.execution_time_s + 0.01 <= candidate.preparation_start_s + 1e-9
        )
        if not separated:
            return False
        if (candidate.task == shoot.TASK_NAME == other.task
                and candidate.target_id == other.target_id):
            return False
        if (candidate.task == photo.TASK_NAME == other.task
                and candidate.target_id == other.target_id
                and photo.circular_separation_deg(candidate.angle_deg, other.angle_deg)
                < photo.MIN_ANGLE_SEPARATION_DEG - 1e-9):
            return False
    return True


def greedy_baseline(candidates: list[Candidate], capacity: int | None = None) -> list[Candidate]:
    selected: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (
        item.execution_time_s, -item.normalized_margin, item.target_id
    )):
        if _compatible(candidate, selected):
            selected.append(candidate)
            if capacity is not None and len(selected) == capacity:
                break
    return selected


def robustness_check(selected: list[Candidate], trajectory: TrajectoryState,
                     targets, trials: int = 500, seed: int = 2026,
                     position_std_scale: float = 0.5,
                     state_relative_sd: float = 0.05) -> dict:
    rng = np.random.default_rng(seed)
    frame = trajectory.frame
    sx_interp = PchipInterpolator(trajectory.time, frame["x_std"], extrapolate=False)
    sy_interp = PchipInterpolator(trajectory.time, frame["y_std"], extrapolate=False)
    target_map = {target.target_id: target for target in targets}
    task_success = np.ones((trials, len(selected)), dtype=bool)
    for index, candidate in enumerate(selected):
        target = target_map[candidate.target_id]
        count = int(round((candidate.execution_time_s - candidate.preparation_start_s) / 0.01))
        query = candidate.preparation_start_s + 0.01 * np.arange(count + 1)
        query[-1] = candidate.execution_time_s
        state = trajectory.evaluate(query)
        sx = np.asarray(sx_interp(query), dtype=float)
        sy = np.asarray(sy_interp(query), dtype=float)
        for trial in range(trials):
            # One correlated position displacement per task window represents
            # a local systematic trajectory realization; small state-magnitude
            # perturbations cover speed/acceleration estimation uncertainty.
            x = state["x"] + rng.normal(0.0, position_std_scale) * sx
            y = state["y"] + rng.normal(0.0, position_std_scale) * sy
            speed = state["speed"] * max(0.0, 1.0 + rng.normal(0.0, state_relative_sd))
            acceleration = state["acceleration"] * max(0.0, 1.0 + rng.normal(0.0, state_relative_sd))
            distance = np.hypot(x - target.x_m, y - target.y_m)
            margin_function = (shoot.normalized_margin if candidate.task == shoot.TASK_NAME
                               else photo.normalized_margin)
            task_success[trial, index] = bool(np.min(
                margin_function(distance, speed, acceleration)
            ) >= 0.0)
    return {
        "trials": trials,
        "seed": seed,
        "position_std_scale": position_std_scale,
        "speed_acceleration_relative_sd": state_relative_sd,
        "per_task_feasible_rate": task_success.mean(axis=0).tolist(),
        "whole_schedule_feasible_rate": float(np.all(task_success, axis=1).mean()),
    }


def write_result_template(template: str | Path, output: str | Path,
                          selected: list[Candidate]) -> dict:
    before = _untouched_snapshot(template)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, output)
    wb = load_workbook(output)
    ws = wb[wb.sheetnames[0]]
    required_last_row = len(selected) + 1
    for row in range(11, required_last_row + 1):
        for column in range(1, 6):
            source = ws.cell(10, column)
            target = ws.cell(row, column)
            target._style = copy.copy(source._style)
            target.number_format = source.number_format
            target.alignment = copy.copy(source.alignment)
            target.protection = copy.copy(source.protection)
        ws.cell(row, 1).value = row - 1
    for row, candidate in enumerate(selected, start=2):
        ws.cell(row, 1).value = row - 1
        ws.cell(row, 2).value = candidate.target_id
        ws.cell(row, 3).value = candidate.task
        ws.cell(row, 4).value = candidate.preparation_start_s
        ws.cell(row, 5).value = candidate.execution_time_s
    wb.save(output)
    after = _untouched_snapshot(output)
    if before != after:
        raise RuntimeError("Untouched result.xlsx values or styles changed.")
    return {
        "template_sha256": sha256(template),
        "output_sha256": sha256(output),
        "untouched_snapshot_equal": True,
        "result_range": f"A2:E{required_last_row}",
        "instruction_area_preserved": "H1:L10",
        "filled_rows": len(selected),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)

    trajectory = TrajectoryState.load(args.trajectory)
    targets = load_targets(args.targets)
    candidates = generate_candidates(trajectory, targets)
    greedy = greedy_baseline(candidates)
    schedule = optimize_schedule(candidates)
    selected = _rounded_and_verified(schedule.selected, trajectory, targets)
    robust_scenarios = {
        "moderate": robustness_check(
            selected, trajectory, targets, trials=500, seed=2026,
            position_std_scale=0.5, state_relative_sd=0.05,
        ),
        "standard": robustness_check(
            selected, trajectory, targets, trials=500, seed=2027,
            position_std_scale=1.0, state_relative_sd=0.05,
        ),
        "severe": robustness_check(
            selected, trajectory, targets, trials=500, seed=2028,
            position_std_scale=1.5, state_relative_sd=0.10,
        ),
    }

    candidate_frame = pd.DataFrame([candidate.to_dict() for candidate in candidates])
    candidate_frame.to_csv(args.results / "feasible_tasks.csv", index=False,
                           encoding="utf-8-sig")
    schedule_frame = pd.DataFrame([
        {"序号": index, "目标编号": item.target_id, "任务": item.task,
         "开始准备时刻(s)": item.preparation_start_s,
         "任务执行时刻(s)": item.execution_time_s,
         "方向角(deg)": item.angle_deg,
         "归一化最小裕度": item.normalized_margin,
         "准备窗最小距离(m)": item.min_distance_m,
         "准备窗最大距离(m)": item.max_distance_m,
         "准备窗最大速度(m/s)": item.max_speed_mps,
         "准备窗最大加速度(m/s²)": item.max_acceleration_mps2}
        for index, item in enumerate(selected, start=1)
    ])
    schedule_frame.to_csv(args.results / "optimized_schedule.csv", index=False,
                          encoding="utf-8-sig")
    workbook = write_result_template(
        args.template, args.results / "result.xlsx", selected
    )
    shot_count = sum(item.task == shoot.TASK_NAME for item in selected)
    photo_count = len(selected) - shot_count
    parameters = {
        "trajectory": str(args.trajectory.resolve()),
        "trajectory_sha256": sha256(args.trajectory),
        "targets_workbook": str(args.targets.resolve()),
        "targets_sha256": sha256(args.targets),
        "target_counts": {"shooting": 18, "photography": 18},
        "candidate_count": len(candidates),
        "candidate_count_by_task": candidate_frame.groupby("task").size().to_dict(),
        "maximum_task_count": schedule.maximum_task_count,
        "selected_task_count": len(selected),
        "shooting_count": shot_count,
        "photography_count": photo_count,
        "expected_shooting_hits": shoot.HIT_PROBABILITY * shot_count,
        "minimum_normalized_margin": min(item.normalized_margin for item in selected),
        "greedy_task_count": len(greedy),
        "greedy_minimum_margin": min(item.normalized_margin for item in greedy),
        "milp": {
            "stage1_status": schedule.stage1_status,
            "stage2_status": schedule.stage2_status,
            "stage3_status": schedule.stage3_status,
            "stage1_gap": schedule.stage1_gap,
            "stage2_gap": schedule.stage2_gap,
            "stage3_gap": schedule.stage3_gap,
            "capacity_upper_bound": None,
            "greedy_reference_computed": True,
        },
        "continuous_recheck_step_s": 0.01,
        "robustness_scenarios": robust_scenarios,
        "result_workbook": workbook,
    }
    (args.results / "parameters.json").write_text(
        json.dumps(parameters, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(parameters, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
