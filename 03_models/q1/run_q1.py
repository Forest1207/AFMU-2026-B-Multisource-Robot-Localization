"""End-to-end runner for Question 1.

Example
-------
python 03_models/q1/run_q1.py \
    --input 00_problem/attachments/附件1.xlsx \
    --output-dir 05_results/q1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from data_loader import load_attachment1
from diagnostics import (
    plot_aligned_trajectories,
    plot_alignment_residuals,
    plot_objective_scan,
    plot_trajectory_10hz,
)
from interpolation_10hz import aligned_stream2, merge_aligned_samples, reconstruct_10hz
from interpolation_models import build_trajectory
from time_alignment import alignment_loss, estimate_time_offset
from validation import (
    file_sha256,
    runtime_versions,
    validate_official_output,
)


METHODS = ("linear", "cubic", "pchip", "akima")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Solve CUMCM 2026 B Question 1.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("00_problem/attachments/附件1.xlsx"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("05_results/q1"),
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        default=Path("06_figures/q1"),
    )
    parser.add_argument(
        "--method",
        choices=METHODS,
        default="cubic",
        help="Interpolation model used for the official run.",
    )
    parser.add_argument(
        "--compare-interpolators",
        action="store_true",
        help="Run the full alignment once for each interpolation method.",
    )
    parser.add_argument("--min-overlap", type=float, default=60.0)
    parser.add_argument("--corr-grid-dt", type=float, default=0.1)
    parser.add_argument("--coarse-step", type=float, default=0.5)
    parser.add_argument("--final-eval-dt", type=float, default=0.05)
    return parser.parse_args()


def solve_with_method(
    stream1,
    stream2,
    method: str,
    args: argparse.Namespace,
):
    traj1 = build_trajectory(stream1, method=method)
    traj2 = build_trajectory(stream2, method=method)

    alignment, scan_offset, scan_mse = estimate_time_offset(
        stream1,
        stream2,
        traj1,
        traj2,
        min_overlap_seconds=args.min_overlap,
        corr_grid_dt=args.corr_grid_dt,
        coarse_step=args.coarse_step,
        final_eval_dt=args.final_eval_dt,
    )
    return traj1, traj2, alignment, scan_offset, scan_mse


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.figure_dir.mkdir(parents=True, exist_ok=True)

    stream1, stream2 = load_attachment1(args.input)

    comparison_rows: list[dict] = []
    if args.compare_interpolators:
        for method in METHODS:
            _, _, result, _, _ = solve_with_method(stream1, stream2, method, args)
            comparison_rows.append(
                {
                    "method": method,
                    "time_offset_s": result.time_offset_s,
                    "mse_m2": result.loss.mse,
                    "rmse_m": result.loss.rmse,
                    "overlap_seconds": result.loss.overlap_seconds,
                }
            )
        pd.DataFrame(comparison_rows).to_csv(
            args.output_dir / "interpolation_comparison.csv",
            index=False,
            encoding="utf-8-sig",
        )

    traj1, traj2, result, scan_offset, scan_mse = solve_with_method(
        stream1, stream2, args.method, args
    )

    stream2_aligned = aligned_stream2(stream2, result.time_offset_s)
    merged, merge_diag = merge_aligned_samples(stream1, stream2_aligned)

    expected_max_gap = max(
        1.0 / stream1.nominal_rate_hz,
        1.0 / stream2.nominal_rate_hz,
    ) + 1e-6
    if merge_diag.max_time_gap_s > 2.0 * expected_max_gap:
        raise RuntimeError(
            "Merged data contain a large unsupported time gap "
            f"({merge_diag.max_time_gap_s:.3f}s); refusing to interpolate across it."
        )

    trajectory_10hz = reconstruct_10hz(
        merged,
        method=args.method,
        output_hz=10.0,
    )
    trajectory_10hz.to_csv(
        args.output_dir / "trajectory_10hz.csv",
        index=False,
        encoding="utf-8-sig",
    )

    validation = validate_official_output(
        stream1,
        stream2,
        result,
        merge_diag,
        trajectory_10hz,
    )

    pd.DataFrame(
        {"time_offset_s": scan_offset, "mse_m2": scan_mse}
    ).to_csv(
        args.output_dir / "objective_scan.csv",
        index=False,
        encoding="utf-8-sig",
    )

    parameters = result.to_dict()
    parameters["interpolation_method"] = args.method
    parameters["merge_diagnostics"] = {
        "n_stream1": merge_diag.n_stream1,
        "n_stream2": merge_diag.n_stream2,
        "n_merged": merge_diag.n_merged,
        "duplicate_groups": merge_diag.duplicate_groups,
        "max_duplicate_disagreement_m": merge_diag.max_duplicate_disagreement_m,
        "max_time_gap_s": merge_diag.max_time_gap_s,
    }
    parameters["reported_time_offset_s"] = round(result.time_offset_s, 4)
    parameters["input"] = {
        "filename": args.input.name,
        "bytes": args.input.stat().st_size,
        "sha256": file_sha256(args.input),
    }
    parameters["output_hz"] = 10.0
    parameters["runtime_versions"] = runtime_versions()
    parameters["validation"] = validation.to_dict()

    with open(args.output_dir / "parameters.json", "w", encoding="utf-8") as f:
        json.dump(parameters, f, ensure_ascii=False, indent=2)

    summary = (
        "# Q1 Summary\n\n"
        f"- interpolation: `{args.method}`\n"
        f"- time offset Δt (reported): `{result.time_offset_s:.4f} s`\n"
        f"- time offset Δt (raw estimate): `{result.time_offset_s:.10f} s`\n"
        f"- sign convention: `t2_aligned = t2 + Δt`\n"
        f"- aligned RMSE: `{result.loss.rmse:.6e} m`\n"
        f"- overlap: `{result.loss.overlap_seconds:.3f} s`\n"
        f"- coincident timestamp groups: `{merge_diag.duplicate_groups}`\n"
        f"- maximum coincident-coordinate disagreement: "
        f"`{merge_diag.max_duplicate_disagreement_m:.3e} m`\n"
        f"- independent exact-coordinate matches: "
        f"`{validation.independent_exact_match_count}`\n"
        f"- independent offset: `{validation.independent_offset_s:.4f} s`\n"
        f"- output rows: `{len(trajectory_10hz)}`\n"
        f"- output interval: "
        f"`[{trajectory_10hz.time.iloc[0]:.6f}, "
        f"{trajectory_10hz.time.iloc[-1]:.6f}] s`\n"
    )
    (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")

    plot_objective_scan(
        scan_offset,
        scan_mse,
        result,
        args.figure_dir / "objective_scan.png",
    )
    plot_aligned_trajectories(
        stream1,
        stream2,
        result.time_offset_s,
        args.figure_dir / "aligned_trajectory.png",
    )
    plot_alignment_residuals(
        traj1,
        traj2,
        result,
        args.figure_dir / "alignment_residuals.png",
    )
    plot_trajectory_10hz(
        trajectory_10hz,
        args.figure_dir / "trajectory_10hz.png",
    )

    figure_manifest = {
        "q1": [
            {
                "path": f"{args.figure_dir.as_posix()}/objective_scan.png",
                "svg_path": f"{args.figure_dir.as_posix()}/objective_scan.svg",
                "pdf_path": f"{args.figure_dir.as_posix()}/objective_scan.pdf",
                "purpose": "验证时间对齐目标函数的全局极小值与边界距离",
                "source": "05_results/q1/objective_scan.csv",
            },
            {
                "path": f"{args.figure_dir.as_posix()}/aligned_trajectory.png",
                "svg_path": f"{args.figure_dir.as_posix()}/aligned_trajectory.svg",
                "pdf_path": f"{args.figure_dir.as_posix()}/aligned_trajectory.pdf",
                "purpose": "展示两种定位方式在空间轨迹上的一致覆盖",
                "source": "附件1.xlsx",
            },
            {
                "path": f"{args.figure_dir.as_posix()}/alignment_residuals.png",
                "svg_path": f"{args.figure_dir.as_posix()}/alignment_residuals.svg",
                "pdf_path": f"{args.figure_dir.as_posix()}/alignment_residuals.pdf",
                "purpose": "验证最优偏差下x/y位置残差接近数值误差",
                "source": "05_results/q1/parameters.json",
            },
            {
                "path": f"{args.figure_dir.as_posix()}/trajectory_10hz.png",
                "svg_path": f"{args.figure_dir.as_posix()}/trajectory_10hz.svg",
                "pdf_path": f"{args.figure_dir.as_posix()}/trajectory_10hz.pdf",
                "purpose": "给出题目要求的10 Hz重建轨迹及起终点",
                "source": "05_results/q1/trajectory_10hz.csv",
            },
        ]
    }
    with open(args.output_dir / "figure_manifest.json", "w", encoding="utf-8") as f:
        json.dump(figure_manifest, f, ensure_ascii=False, indent=2)

    final_check = alignment_loss(
        result.time_offset_s,
        traj1,
        traj2,
        eval_dt=args.final_eval_dt,
        min_overlap_seconds=args.min_overlap,
    )
    print(f"Δt* = {result.time_offset_s:.10f} s")
    print(f"RMSE = {final_check.rmse:.6e} m")
    print(f"10 Hz rows = {len(trajectory_10hz)}")
    print(f"Results written to: {args.output_dir}")


if __name__ == "__main__":
    main()
