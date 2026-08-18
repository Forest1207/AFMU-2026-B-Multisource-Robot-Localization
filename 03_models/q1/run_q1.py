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
from pathlib import Path

import pandas as pd

from data_loader import load_attachment1
from diagnostics import (
    plot_aligned_trajectories,
    plot_alignment_residuals,
    plot_objective_scan,
)
from interpolation_10hz import aligned_stream2, merge_aligned_samples, reconstruct_10hz
from interpolation_models import build_trajectory
from time_alignment import alignment_loss, estimate_time_offset


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
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

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
    parameters["input"] = str(args.input)
    parameters["output_hz"] = 10.0

    with open(args.output_dir / "parameters.json", "w", encoding="utf-8") as f:
        json.dump(parameters, f, ensure_ascii=False, indent=2)

    summary = (
        "# Q1 Summary\n\n"
        f"- interpolation: `{args.method}`\n"
        f"- time offset Δt: `{result.time_offset_s:.10f} s`\n"
        f"- sign convention: `t2_aligned = t2 + Δt`\n"
        f"- aligned RMSE: `{result.loss.rmse:.6e} m`\n"
        f"- overlap: `{result.loss.overlap_seconds:.3f} s`\n"
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
        args.output_dir / "objective_scan.png",
    )
    plot_aligned_trajectories(
        stream1,
        stream2,
        result.time_offset_s,
        args.output_dir / "aligned_trajectory.png",
    )
    plot_alignment_residuals(
        traj1,
        traj2,
        result,
        args.output_dir / "alignment_residuals.png",
    )

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
