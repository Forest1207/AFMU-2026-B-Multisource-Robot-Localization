"""Machine validation for the official unrestricted Q4 schedule."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

import photography_model as photo
import shooting_model as shoot
from feasible_windows import _continuous_metrics, load_targets
from run_q4 import _protected_snapshot
from trajectory_state import TrajectoryState


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--figures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    params = json.loads((args.results / "parameters.json").read_text(encoding="utf-8"))
    schedule = pd.read_csv(args.results / "optimized_schedule.csv")
    trajectory = TrajectoryState.load(args.trajectory)
    targets = load_targets(args.targets)
    target_map = {target.target_id: target for target in targets}

    checks = {
        "nonempty_schedule": len(schedule) > 0,
        "schedule_count_matches": len(schedule) == int(params["selected_task_count"]),
        "coverage_not_above_36": 0 < int(params["coverage_count"]) <= 36,
        "no_artificial_capacity": params["milp"].get("artificial_capacity") is None,
        "no_cross_task_time_mutex": params["milp"].get("cross_task_time_mutex") is False,
        "all_milp_stages_optimal": all(
            int(params["milp"][key]) == 0
            for key in ("stage1_status", "stage2_status", "stage3_status")
        ),
        "all_milp_gaps_zero": all(
            params["milp"][key] is None or abs(float(params["milp"][key])) <= 1e-12
            for key in ("stage1_gap", "stage2_gap", "stage3_gap")
        ),
        "positive_margin": bool(np.all(schedule["归一化最小裕度"] >= -1e-10)),
        "milp_coverage_not_below_greedy": int(params["coverage_count"]) >= int(params["greedy_coverage_count"]),
        "milp_photo_not_below_greedy": int(params["photography_count"]) >= int(params["greedy_photography_count"]),
    }

    shooting = schedule[schedule["任务"] == shoot.TASK_NAME]
    checks["shooting_targets_unique"] = shooting["目标编号"].is_unique

    photo_angles_ok = True
    photography = schedule[schedule["任务"] == photo.TASK_NAME]
    for _, group in photography.groupby("目标编号"):
        values = group["方向角(deg)"].to_numpy()
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                photo_angles_ok &= (
                    photo.circular_separation_deg(values[i], values[j])
                    >= photo.MIN_ANGLE_SEPARATION_DEG - 1e-9
                )
    checks["photography_angle_separation"] = bool(photo_angles_ok)

    continuous_ok = True
    reported_ok = True
    for _, row in schedule.iterrows():
        metrics = _continuous_metrics(
            trajectory,
            target_map[str(row["目标编号"])],
            float(row["开始准备时刻(s)"]),
            float(row["任务执行时刻(s)"]),
            0.01,
        )
        continuous_ok &= metrics["margin"] >= -1e-9
        reported_ok &= abs(metrics["margin"] - float(row["归一化最小裕度"])) < 1e-9
    checks["continuous_001s_constraints"] = bool(continuous_ok)
    checks["reported_metrics_recomputed"] = bool(reported_ok)

    result_path = args.results / "result.xlsx"
    checks["protected_template_semantics"] = (
        _protected_snapshot(args.template) == _protected_snapshot(result_path)
    )
    wb = load_workbook(result_path, data_only=False)
    ws = wb[wb.sheetnames[0]]
    workbook_rows = []
    for row in range(2, ws.max_row + 1):
        values = [ws.cell(row, column).value for column in range(1, 6)]
        if values[1] is None:
            continue
        workbook_rows.append(values)
    expected_rows = [
        [int(row["序号"]), row["目标编号"], row["任务"],
         float(row["开始准备时刻(s)"]), float(row["任务执行时刻(s)"])]
        for _, row in schedule.iterrows()
    ]
    checks["result_workbook_rows_match"] = workbook_rows == expected_rows
    checks["workbook_expands_to_all_tasks"] = len(workbook_rows) == len(schedule)
    checks["no_formula_errors"] = all(
        not (isinstance(cell.value, str) and cell.value.startswith("#"))
        for row in ws.iter_rows() for cell in row
    )

    stems = ["trajectory_targets_schedule", "candidate_feasibility_map",
             "optimized_schedule_timeline", "constraint_margins"]
    checks["figure_triplets_complete"] = all(
        (args.figures / f"{stem}.{suffix}").exists()
        for stem in stems for suffix in ("png", "svg", "pdf")
    )

    report = {"ok": bool(all(checks.values())), "checks": checks}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
