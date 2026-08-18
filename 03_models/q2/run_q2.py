"""End-to-end runner for Q2: alignment, bias correction, fusion, 10 Hz output."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from coarse_alignment import estimate_coarse_offset
from data_loader import load_two_streams
from joint_alignment import aligned_samples, estimate_joint_alignment
from preprocess import clean_stream
from sensor_fusion import estimate_axis_variances, variance_weighted_fusion


def run_pipeline(
    workbook: str | Path,
    sheet1: str,
    sheet2: str,
    output_csv: str | Path,
    time_col: str = "时间(s)",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
    coarse_grid_dt: float = 0.02,
    max_abs_lag: float = 10.0,
    fine_half_width: float = 0.5,
    interpolation: str = "pchip",
    robust_iterations: int = 2,
    known_var1: tuple[float, float] | None = None,
    known_var2: tuple[float, float] | None = None,
) -> dict:
    s1, s2 = load_two_streams(
        workbook,
        sheet1,
        sheet2,
        time_col=time_col,
        x_col=x_col,
        y_col=y_col,
    )

    t1, xy1 = clean_stream(s1.time, s1.xy)
    t2, xy2 = clean_stream(s2.time, s2.xy)

    coarse_dt = estimate_coarse_offset(
        t1, xy1, t2, xy2,
        grid_dt=coarse_grid_dt,
        max_abs_lag=max_abs_lag,
    )

    result = estimate_joint_alignment(
        t1, xy1, t2, xy2,
        dt_bounds=(coarse_dt - fine_half_width, coarse_dt + fine_half_width),
        sample_dt=0.1,
        interpolation=interpolation,
        robust_iterations=robust_iterations,
    )

    grid, a, b = aligned_samples(
        t1, xy1, t2, xy2,
        dt=result.dt,
        sample_dt=0.1,
        interpolation=interpolation,
    )
    b_corrected = b - result.bias

    if known_var1 is None or known_var2 is None:
        var1, var2 = estimate_axis_variances(a, b_corrected)
    else:
        var1 = np.asarray(known_var1, dtype=float)
        var2 = np.asarray(known_var2, dtype=float)

    fusion = variance_weighted_fusion(a, b_corrected, var1, var2)

    out = pd.DataFrame(
        {
            "time_s": grid,
            "x_stream1": a[:, 0],
            "y_stream1": a[:, 1],
            "x_stream2_corrected": b_corrected[:, 0],
            "y_stream2_corrected": b_corrected[:, 1],
            "x_fused": fusion.fused_xy[:, 0],
            "y_fused": fusion.fused_xy[:, 1],
        }
    )
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")

    return {
        "coarse_dt": coarse_dt,
        "dt": result.dt,
        "bias_x": float(result.bias[0]),
        "bias_y": float(result.bias[1]),
        "rmse": result.rmse,
        "n_overlap": result.n_overlap,
        "var1_x": float(fusion.var1[0]),
        "var1_y": float(fusion.var1[1]),
        "var2_x": float(fusion.var2[0]),
        "var2_y": float(fusion.var2[1]),
        "w1_x": float(fusion.weights1[0]),
        "w1_y": float(fusion.weights1[1]),
        "w2_x": float(fusion.weights2[0]),
        "w2_y": float(fusion.weights2[1]),
        "output_csv": str(output_csv),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run Q2 alignment and fusion pipeline.")
    p.add_argument("workbook", help="Path to Q2 Excel workbook")
    p.add_argument("--sheet1", required=True, help="Sheet name of positioning method 1")
    p.add_argument("--sheet2", required=True, help="Sheet name of positioning method 2")
    p.add_argument("--output", default="05_results/q2_fused_10hz.csv")
    p.add_argument("--time-col", default="时间(s)")
    p.add_argument("--x-col", default="X坐标(m)")
    p.add_argument("--y-col", default="Y坐标(m)")
    p.add_argument("--max-abs-lag", type=float, default=10.0)
    p.add_argument("--fine-half-width", type=float, default=0.5)
    p.add_argument("--interpolation", choices=["linear", "cubic", "pchip"], default="pchip")
    p.add_argument("--robust-iterations", type=int, default=2)
    return p


def main() -> None:
    args = _build_parser().parse_args()
    summary = run_pipeline(
        workbook=args.workbook,
        sheet1=args.sheet1,
        sheet2=args.sheet2,
        output_csv=args.output,
        time_col=args.time_col,
        x_col=args.x_col,
        y_col=args.y_col,
        max_abs_lag=args.max_abs_lag,
        fine_half_width=args.fine_half_width,
        interpolation=args.interpolation,
        robust_iterations=args.robust_iterations,
    )
    print("Q2 completed")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
