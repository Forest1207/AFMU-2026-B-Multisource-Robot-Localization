"""End-to-end Q4 pipeline: trajectory -> candidates -> MILP -> Excel result."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from conflict_builder import (
    build_photo_angle_conflicts,
    build_resource_conflicts,
    merge_conflicts,
)
from feasible_windows import PhotographyRules, ShootingRules
from local_refinement import refine_candidate, validate_photo_angle_separation
from photography_model import build_photography_candidates
from scheduler import ScheduleResult, solve_lexicographic
from shooting_model import build_shooting_candidates
from target_geometry import Target, compute_all_geometry, read_targets
from trajectory_state import reconstruct_state


def read_trajectory(
    path: str | Path,
    sheet_name: str | int = 0,
    time_col: str = "时间(s)",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
) -> tuple[np.ndarray, np.ndarray]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=sheet_name)
    missing = [c for c in (time_col, x_col, y_col) if c not in df.columns]
    if missing:
        raise ValueError(f"trajectory missing columns {missing}; actual={list(df.columns)}")
    sub = df[[time_col, x_col, y_col]].apply(pd.to_numeric, errors="coerce").dropna()
    return sub[time_col].to_numpy(float), sub[[x_col, y_col]].to_numpy(float)


def load_targets_from_args(args: argparse.Namespace) -> list[Target]:
    common = dict(
        workbook=args.targets,
        id_col=args.target_id_col,
        x_col=args.target_x_col,
        y_col=args.target_y_col,
        type_col=args.target_type_col,
    )
    targets: list[Target] = []
    if args.shoot_sheet is not None:
        targets.extend(read_targets(sheet_name=args.shoot_sheet, default_task_type="shoot", **common))
    if args.photo_sheet is not None:
        targets.extend(read_targets(sheet_name=args.photo_sheet, default_task_type="photo", **common))
    if not targets:
        targets = read_targets(sheet_name=args.target_sheet, default_task_type=None, **common)
    ids = [t.target_id for t in targets]
    if len(ids) != len(set(ids)):
        raise ValueError("target IDs must be unique across shooting and photo inputs")
    return targets


def export_result(
    result: ScheduleResult,
    output: str | Path,
    expected_hit_probability: float = 0.85,
) -> None:
    rows = []
    for c in result.selected:
        rows.append({
            "任务类型": "射击" if c.task_type == "shoot" else "拍照",
            "目标编号": c.target_id,
            "执行时间(s)": c.time,
            "距离(m)": c.distance,
            "速度(m/s)": c.speed,
            "加速度(m/s^2)": c.acceleration,
            "方位角(deg)": c.bearing_deg,
            "安全裕度": c.quality,
            "准备窗口起点(s)": c.resource_start,
            "准备窗口终点(s)": c.resource_end,
        })
    tasks = pd.DataFrame(rows)
    shoot_count = int(sum(c.task_type == "shoot" for c in result.selected))
    photo_count = int(sum(c.task_type == "photo" for c in result.selected))
    summary = pd.DataFrame([
        {"指标": "覆盖任务目标数", "数值": result.covered_targets},
        {"指标": "安排射击次数", "数值": shoot_count},
        {"指标": "有效拍照次数", "数值": photo_count},
        {"指标": "期望命中目标数(单次0.85)", "数值": expected_hit_probability * shoot_count},
        {"指标": "安全裕度总和", "数值": result.quality_sum},
    ])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        tasks.to_excel(writer, sheet_name="任务结果", index=False)
        summary.to_excel(writer, sheet_name="汇总", index=False)


def run(args: argparse.Namespace) -> ScheduleResult:
    time, xy = read_trajectory(
        args.trajectory,
        sheet_name=args.trajectory_sheet,
        time_col=args.time_col,
        x_col=args.x_col,
        y_col=args.y_col,
    )
    state = reconstruct_state(time, xy, fs=args.fs, smoothing=args.smoothing)
    targets = load_targets_from_args(args)
    geometry = compute_all_geometry(state, targets)

    shooting_rules = ShootingRules()
    photo_rules = PhotographyRules()
    candidates = []
    for target in targets:
        geo = geometry[target.target_id]
        if target.task_type == "shoot":
            cs, _ = build_shooting_candidates(
                state, geo, fs=args.fs, rules=shooting_rules,
                max_per_segment=args.max_shoot_per_segment,
            )
        else:
            cs, _ = build_photography_candidates(
                state, geo, fs=args.fs, rules=photo_rules,
                require_full_lead_window=not args.photo_orientation_only,
                angle_bin_deg=args.angle_bin_deg,
            )
        candidates.extend(cs)

    angle_conflicts = build_photo_angle_conflicts(candidates, min_angle_deg=60.0)
    if args.exclusive_resource:
        resource_conflicts = build_resource_conflicts(candidates)
        conflicts = merge_conflicts(angle_conflicts, resource_conflicts)
    else:
        conflicts = angle_conflicts

    result = solve_lexicographic(
        candidates,
        conflicts=conflicts,
        single_shot_per_target=not args.allow_repeat_shots,
    )

    if args.refine and result.selected and not args.exclusive_resource:
        target_map = {t.target_id: t for t in targets}
        refined = [
            refine_candidate(
                c, state, target_map[c.target_id],
                radius=args.refine_radius,
                dense_dt=args.refine_step,
                shooting_rules=shooting_rules,
                photo_rules=photo_rules,
            )
            for c in result.selected
        ]
        # Refinement is accepted only if it preserves the hard photo-angle rule.
        if validate_photo_angle_separation(refined, min_angle_deg=60.0):
            result = ScheduleResult(
                selected=sorted(refined, key=lambda c: c.time),
                covered_targets=result.covered_targets,
                photo_count=result.photo_count,
                quality_sum=float(sum(c.quality for c in refined)),
                solver_messages=result.solver_messages,
            )

    export_result(result, args.output)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Q4 fixed-trajectory task optimization")
    p.add_argument("--trajectory", required=True, help="Q3 fused trajectory xlsx/csv")
    p.add_argument("--targets", required=True, help="attachment 4 target workbook")
    p.add_argument("--output", default="05_results/q4_result.xlsx")
    p.add_argument("--trajectory-sheet", default=0)
    p.add_argument("--target-sheet", default=0)
    p.add_argument("--shoot-sheet", default=None)
    p.add_argument("--photo-sheet", default=None)
    p.add_argument("--time-col", default="时间(s)")
    p.add_argument("--x-col", default="X坐标(m)")
    p.add_argument("--y-col", default="Y坐标(m)")
    p.add_argument("--target-id-col", default="目标编号")
    p.add_argument("--target-x-col", default="X坐标(m)")
    p.add_argument("--target-y-col", default="Y坐标(m)")
    p.add_argument("--target-type-col", default="任务类型")
    p.add_argument("--fs", type=float, default=10.0)
    p.add_argument("--smoothing", type=float, default=None)
    p.add_argument("--angle-bin-deg", type=float, default=10.0)
    p.add_argument("--max-shoot-per-segment", type=int, default=5)
    p.add_argument("--photo-orientation-only", action="store_true",
                   help="treat 0.5 s as orientation preparation only")
    p.add_argument("--exclusive-resource", action="store_true",
                   help="optional engineering assumption: preparation windows cannot overlap")
    p.add_argument("--allow-repeat-shots", action="store_true")
    p.add_argument("--refine", action="store_true")
    p.add_argument("--refine-radius", type=float, default=0.1)
    p.add_argument("--refine-step", type=float, default=0.01)
    return p


if __name__ == "__main__":
    parser = build_parser()
    result = run(parser.parse_args())
    print(
        f"selected={len(result.selected)}, covered={result.covered_targets}, "
        f"photos={result.photo_count}, quality={result.quality_sum:.4f}"
    )
