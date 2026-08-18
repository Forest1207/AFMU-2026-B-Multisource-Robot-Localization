"""End-to-end runner for Q3 real-data bias testing and asynchronous fusion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
Q2_DIR = HERE.parent / "q2"
if str(Q2_DIR) not in sys.path:
    sys.path.insert(0, str(Q2_DIR))

from coarse_alignment import estimate_coarse_offset  # noqa: E402
from data_loader import load_two_streams  # noqa: E402
from joint_alignment import aligned_samples, estimate_joint_alignment  # noqa: E402
from preprocess import clean_stream  # noqa: E402

from bias_test import analyze_bias  # noqa: E402
from robust_fusion import (  # noqa: E402
    asynchronous_robust_kf,
    resample_smoothed_state,
    rts_smoother,
    state_kinematics,
    symmetric_measurement_covariances,
)


def _cov_from_cli(values: list[float] | None) -> np.ndarray | None:
    if values is None:
        return None
    arr = np.asarray(values, dtype=float)
    if arr.size == 2:
        if np.any(arr <= 0):
            raise ValueError("Measurement variances must be positive.")
        return np.diag(arr)
    if arr.size == 4:
        R = arr.reshape(2, 2)
        if np.any(np.linalg.eigvalsh(R) <= 0):
            raise ValueError("Measurement covariance must be positive definite.")
        return R
    raise ValueError("R must contain either 2 diagonal variances or 4 matrix entries.")


def run_pipeline(
    workbook: str | Path,
    sheet1: str,
    sheet2: str,
    output_csv: str | Path,
    summary_json: str | Path | None = None,
    innovation_csv: str | Path | None = None,
    time_col: str = "时间(s)",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
    coarse_grid_dt: float = 0.02,
    max_abs_lag: float = 10.0,
    fine_half_width: float = 0.5,
    interpolation: str = "pchip",
    robust_iterations: int = 3,
    alpha: float = 0.05,
    practical_threshold: float = 0.25,
    n_boot: int = 2000,
    block_length: int | None = None,
    statistical_only: bool = False,
    R1: np.ndarray | None = None,
    R2: np.ndarray | None = None,
    jerk_spectral_density: float = 0.5,
    fixed_bias_rw_var: float = 1e-8,
    drifting_bias_rw_var: float = 1e-4,
    gate_probability: float = 0.99,
    output_dt: float = 0.1,
) -> dict:
    """Run Q3 from raw Excel sheets through 10 Hz RTS-smoothed output."""
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
        t1,
        xy1,
        t2,
        xy2,
        grid_dt=coarse_grid_dt,
        max_abs_lag=max_abs_lag,
    )
    alignment = estimate_joint_alignment(
        t1,
        xy1,
        t2,
        xy2,
        dt_bounds=(coarse_dt - fine_half_width, coarse_dt + fine_half_width),
        sample_dt=output_dt,
        interpolation=interpolation,
        robust_iterations=robust_iterations,
    )

    aligned_time, a, b = aligned_samples(
        t1,
        xy1,
        t2,
        xy2,
        dt=alignment.dt,
        sample_dt=output_dt,
        interpolation=interpolation,
    )
    diagnostics = analyze_bias(
        aligned_time,
        a,
        b,
        alpha=alpha,
        practical_threshold=practical_threshold,
        n_boot=n_boot,
        block_length=block_length,
    )
    wald = diagnostics["wald"]
    bootstrap = diagnostics["bootstrap"]
    trend = diagnostics["trend"]

    has_bias = bool(
        wald.reject_null
        and (statistical_only or wald.practically_significant)
    )
    drifting_bias = bool(has_bias and trend.drifting)

    corrected_difference = (b - alignment.bias) - a
    if R1 is None or R2 is None:
        est_R1, est_R2 = symmetric_measurement_covariances(corrected_difference)
        if R1 is None:
            R1 = est_R1
        if R2 is None:
            R2 = est_R2
    R1 = np.asarray(R1, dtype=float).reshape(2, 2)
    R2 = np.asarray(R2, dtype=float).reshape(2, 2)

    bias_rw_var = drifting_bias_rw_var if drifting_bias else fixed_bias_rw_var
    filt = asynchronous_robust_kf(
        t1,
        xy1,
        t2,
        xy2,
        time_offset=alignment.dt,
        R1=R1,
        R2=R2,
        estimate_bias=has_bias,
        initial_bias=alignment.bias if has_bias else None,
        jerk_spectral_density=jerk_spectral_density,
        bias_random_walk_var=bias_rw_var,
        gate_probability=gate_probability,
    )
    smooth = rts_smoother(filt)
    grid, state = resample_smoothed_state(smooth, sample_dt=output_dt)
    kin = state_kinematics(state)

    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"time_s": grid, **kin}).to_csv(
        output_csv,
        index=False,
        encoding="utf-8-sig",
    )

    if innovation_csv is not None:
        innovation_csv = Path(innovation_csv)
        innovation_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "time_s": filt.time,
                "sensor": filt.sensor,
                "innovation_x": filt.innovation[:, 0],
                "innovation_y": filt.innovation[:, 1],
                "nis": filt.nis,
                "measurement_covariance_scale": filt.r_scale,
            }
        ).to_csv(innovation_csv, index=False, encoding="utf-8-sig")

    summary = {
        "coarse_time_offset_s": float(coarse_dt),
        "time_offset_s": float(alignment.dt),
        "time_offset_sign_convention": (
            "stream2 timestamp maps to reference time as "
            "t2_corrected = t2 - time_offset"
        ),
        "profile_bias_x_m": float(alignment.bias[0]),
        "profile_bias_y_m": float(alignment.bias[1]),
        "alignment_rmse_m": float(alignment.rmse),
        "alignment_overlap_n": int(alignment.n_overlap),
        "wald": wald.to_dict(),
        "bootstrap": bootstrap.to_dict(),
        "trend": trend.to_dict(),
        "bias_state_enabled": has_bias,
        "bias_drifting": drifting_bias,
        "bias_random_walk_var": float(bias_rw_var),
        "R1": R1.tolist(),
        "R2": R2.tolist(),
        "mean_nis": float(np.mean(filt.nis)),
        "p95_nis": float(np.percentile(filt.nis, 95)),
        "downweighted_measurement_fraction": float(np.mean(filt.r_scale > 1.0)),
        "output_rows": int(grid.size),
        "output_csv": str(output_csv),
        "innovation_csv": None if innovation_csv is None else str(innovation_csv),
    }

    if has_bias:
        summary["smoothed_final_bias_x_m"] = float(smooth.state[-1, 6])
        summary["smoothed_final_bias_y_m"] = float(smooth.state[-1, 7])

    if summary_json is not None:
        summary_json = Path(summary_json)
        summary_json.parent.mkdir(parents=True, exist_ok=True)
        summary_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary["summary_json"] = str(summary_json)

    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Q3: systematic-bias testing + asynchronous robust KF/RTS fusion."
    )
    p.add_argument("workbook", help="Path to attachment-3 Excel workbook")
    p.add_argument("--sheet1", required=True, help="Sheet for positioning method 1")
    p.add_argument("--sheet2", required=True, help="Sheet for positioning method 2")
    p.add_argument("--output", default="05_results/q3_fused_10hz.csv")
    p.add_argument("--summary", default="05_results/q3_summary.json")
    p.add_argument("--innovations", default="05_results/q3_innovations.csv")
    p.add_argument("--time-col", default="时间(s)")
    p.add_argument("--x-col", default="X坐标(m)")
    p.add_argument("--y-col", default="Y坐标(m)")
    p.add_argument("--coarse-grid-dt", type=float, default=0.02)
    p.add_argument("--max-abs-lag", type=float, default=10.0)
    p.add_argument("--fine-half-width", type=float, default=0.5)
    p.add_argument(
        "--interpolation",
        choices=["linear", "cubic", "pchip"],
        default="pchip",
    )
    p.add_argument("--robust-iterations", type=int, default=3)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--practical-threshold", type=float, default=0.25)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--block-length", type=int)
    p.add_argument(
        "--statistical-only",
        action="store_true",
        help="Enable bias state whenever p < alpha, ignoring engineering threshold.",
    )
    p.add_argument(
        "--R1",
        type=float,
        nargs="+",
        help="Sensor-1 covariance: 2 diagonal variances or 4 row-major entries.",
    )
    p.add_argument(
        "--R2",
        type=float,
        nargs="+",
        help="Sensor-2 covariance: 2 diagonal variances or 4 row-major entries.",
    )
    p.add_argument("--jerk-q", type=float, default=0.5)
    p.add_argument("--fixed-bias-rw-var", type=float, default=1e-8)
    p.add_argument("--drifting-bias-rw-var", type=float, default=1e-4)
    p.add_argument("--gate-probability", type=float, default=0.99)
    p.add_argument("--output-dt", type=float, default=0.1)
    return p


def main() -> None:
    args = _build_parser().parse_args()
    summary = run_pipeline(
        workbook=args.workbook,
        sheet1=args.sheet1,
        sheet2=args.sheet2,
        output_csv=args.output,
        summary_json=args.summary,
        innovation_csv=args.innovations,
        time_col=args.time_col,
        x_col=args.x_col,
        y_col=args.y_col,
        coarse_grid_dt=args.coarse_grid_dt,
        max_abs_lag=args.max_abs_lag,
        fine_half_width=args.fine_half_width,
        interpolation=args.interpolation,
        robust_iterations=args.robust_iterations,
        alpha=args.alpha,
        practical_threshold=args.practical_threshold,
        n_boot=args.n_boot,
        block_length=args.block_length,
        statistical_only=args.statistical_only,
        R1=_cov_from_cli(args.R1),
        R2=_cov_from_cli(args.R2),
        jerk_spectral_density=args.jerk_q,
        fixed_bias_rw_var=args.fixed_bias_rw_var,
        drifting_bias_rw_var=args.drifting_bias_rw_var,
        gate_probability=args.gate_probability,
        output_dt=args.output_dt,
    )
    print("Q3 completed")
    for key, value in summary.items():
        if key in {"wald", "bootstrap", "trend", "R1", "R2"}:
            print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
