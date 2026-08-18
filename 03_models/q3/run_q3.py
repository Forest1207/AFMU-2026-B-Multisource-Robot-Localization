"""End-to-end runner for Q3 real-data bias testing and asynchronous fusion."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

HERE = Path(__file__).resolve().parent
Q2_DIR = HERE.parent / "q2"
if str(Q2_DIR) not in sys.path:
    sys.path.insert(0, str(Q2_DIR))

from coarse_alignment import (  # noqa: E402
    estimate_coarse_offset,
    estimate_elapsed_position_offset,
)
from data_loader import load_two_streams  # noqa: E402
from joint_alignment import aligned_samples, estimate_joint_alignment  # noqa: E402
from preprocess import clean_stream  # noqa: E402
from sensor_fusion import robust_third_difference_covariance  # noqa: E402

from bias_test import analyze_bias  # noqa: E402
from robust_fusion import (  # noqa: E402
    asynchronous_robust_kf,
    resample_smoothed_covariance,
    resample_smoothed_state,
    rts_smoother,
    state_kinematics,
    symmetric_measurement_covariances,
)


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _lag1(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float).reshape(-1)
    if x.size < 3 or np.std(x[:-1]) <= 1e-12 or np.std(x[1:]) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def _whiten_innovations(innovation: np.ndarray, cov: np.ndarray) -> np.ndarray:
    out = np.empty_like(np.asarray(innovation, dtype=float))
    for index, (value, matrix) in enumerate(zip(innovation, cov, strict=True)):
        out[index] = np.linalg.solve(np.linalg.cholesky(matrix), value)
    return out


def select_process_noise(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2: np.ndarray,
    time_offset: float,
    R1: np.ndarray,
    R2: np.ndarray,
    estimate_bias: bool,
    initial_bias: np.ndarray | None,
    bias_random_walk_var: float,
    gate_probability: float,
    candidates: np.ndarray | None = None,
) -> tuple[float, pd.DataFrame]:
    if candidates is None:
        candidates = np.logspace(-6, 3, 19)
    rows = []
    for q in np.asarray(candidates, dtype=float):
        filt = asynchronous_robust_kf(
            t1, xy1, t2, xy2,
            time_offset=time_offset,
            R1=R1, R2=R2,
            estimate_bias=estimate_bias,
            initial_bias=initial_bias,
            jerk_spectral_density=float(q),
            bias_random_walk_var=bias_random_walk_var,
            gate_probability=gate_probability,
            max_r_inflation=1.0,
        )
        whitened = _whiten_innovations(
            filt.innovation, filt.pre_gate_innovation_cov
        )
        ac = []
        for sensor in (1, 2):
            mask = filt.sensor == sensor
            ac.extend([_lag1(whitened[mask, 0]), _lag1(whitened[mask, 1])])
        mean_ac = float(np.mean(np.abs(ac)))
        mean_nis = float(np.mean(filt.pre_gate_nis))
        rows.append(
            {
                "jerk_spectral_density": float(q),
                "mean_nis": mean_nis,
                "p95_nis": float(np.percentile(filt.pre_gate_nis, 95)),
                "effective_mean_nis": float(np.mean(filt.nis)),
                "mean_abs_lag1_whitened_innovation": mean_ac,
                "downweighted_fraction": float(np.mean(filt.r_scale > 1.0)),
                "diagnostic_score": abs(mean_nis - 2.0) + 2.0 * mean_ac,
            }
        )
    table = pd.DataFrame(rows)
    best = int(table["diagnostic_score"].idxmin())
    return float(table.loc[best, "jerk_spectral_density"]), table


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
    tuning_csv: str | Path | None = None,
    time_col: str = "时间(s)",
    x_col: str = "X坐标(m)",
    y_col: str = "Y坐标(m)",
    coarse_grid_dt: float = 0.02,
    max_abs_lag: float = 120.0,
    fine_half_width: float = 10.0,
    interpolation: str = "pchip",
    robust_iterations: int = 3,
    alpha: float = 0.05,
    practical_threshold: float = 0.25,
    n_boot: int = 2000,
    block_length: int | None = None,
    statistical_only: bool = False,
    R1: np.ndarray | None = None,
    R2: np.ndarray | None = None,
    jerk_spectral_density: float | None = None,
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
    t1, xy1 = clean_stream(s1.time, s1.xy, remove_speed_outliers=False)
    t2, xy2 = clean_stream(s2.time, s2.xy, remove_speed_outliers=False)

    if min(t1[-1], t2[-1]) > max(t1[0], t2[0]):
        coarse_dt = estimate_coarse_offset(
            t1, xy1, t2, xy2,
            grid_dt=coarse_grid_dt,
            max_abs_lag=max_abs_lag,
        )
        coarse_method = "overlap speed correlation"
    else:
        coarse_dt = estimate_elapsed_position_offset(
            t1, xy1, t2, xy2,
            grid_dt=max(coarse_grid_dt, 0.05),
            max_elapsed_shift=max_abs_lag,
        )
        coarse_method = "elapsed centered-position correlation"
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

    bootstrap_supports_zero = bool(np.all(
        (bootstrap.ci_low <= 0.0) & (bootstrap.ci_high >= 0.0)
    ))
    bootstrap_rejects_zero = not bootstrap_supports_zero
    if bool(wald.reject_null) != bootstrap_rejects_zero:
        raise RuntimeError(
            "HAC-Wald and moving-block bootstrap bias decisions conflict; "
            "the model contract requires diagnostic review before fusion."
        )

    has_bias = bool(
        wald.reject_null
        and (statistical_only or wald.practically_significant)
    )
    drifting_bias = bool(has_bias and trend.drifting)

    corrected_difference = (b - alignment.bias) - a
    if R1 is None or R2 is None:
        est_R1 = robust_third_difference_covariance(t1, xy1)
        est_R2 = robust_third_difference_covariance(t2, xy2)
        if R1 is None:
            R1 = est_R1
        if R2 is None:
            R2 = est_R2
    R1 = np.asarray(R1, dtype=float).reshape(2, 2)
    R2 = np.asarray(R2, dtype=float).reshape(2, 2)

    bias_rw_var = drifting_bias_rw_var if drifting_bias else fixed_bias_rw_var
    if jerk_spectral_density is None:
        selected_q, tuning = select_process_noise(
            t1, xy1, t2, xy2,
            time_offset=alignment.dt,
            R1=R1, R2=R2,
            estimate_bias=has_bias,
            initial_bias=alignment.bias if has_bias else None,
            bias_random_walk_var=bias_rw_var,
            gate_probability=gate_probability,
        )
    else:
        selected_q = float(jerk_spectral_density)
        tuning = pd.DataFrame()
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
        jerk_spectral_density=selected_q,
        bias_random_walk_var=bias_rw_var,
        gate_probability=gate_probability,
    )
    smooth = rts_smoother(filt)
    grid, state = resample_smoothed_state(smooth, sample_dt=output_dt)
    cov_grid, state_cov = resample_smoothed_covariance(
        smooth,
        sample_dt=output_dt,
        jerk_spectral_density=selected_q,
        bias_random_walk_var=bias_rw_var,
    )
    if grid.size != cov_grid.size or np.max(np.abs(grid - cov_grid)) > 1e-10:
        raise RuntimeError("State and covariance output grids disagree.")
    kin = state_kinematics(state)
    kin["x_std"] = np.sqrt(np.maximum(state_cov[:, 0, 0], 0.0))
    kin["y_std"] = np.sqrt(np.maximum(state_cov[:, 1, 1], 0.0))

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
                "pre_gate_nis": filt.pre_gate_nis,
                "measurement_covariance_scale": filt.r_scale,
            }
        ).to_csv(innovation_csv, index=False, encoding="utf-8-sig")

    if tuning_csv is not None and not tuning.empty:
        tuning_csv = Path(tuning_csv)
        tuning_csv.parent.mkdir(parents=True, exist_ok=True)
        tuning.to_csv(tuning_csv, index=False, encoding="utf-8-sig")

    summary = {
        "input_workbook": str(Path(workbook).resolve()),
        "input_sha256": _sha256(workbook),
        "sheet1": sheet1,
        "sheet2": sheet2,
        "stream1_rows": int(t1.size),
        "stream2_rows": int(t2.size),
        "coarse_time_offset_s": float(coarse_dt),
        "coarse_alignment_method": coarse_method,
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
        "bootstrap_supports_zero_bias": bootstrap_supports_zero,
        "bias_decision_diagnostics_consistent": True,
        "trend": trend.to_dict(),
        "bias_state_enabled": has_bias,
        "bias_drifting": drifting_bias,
        "bias_random_walk_var": float(bias_rw_var),
        "selected_jerk_spectral_density": float(selected_q),
        "R1": R1.tolist(),
        "R2": R2.tolist(),
        "mean_nis": float(np.mean(filt.pre_gate_nis)),
        "p95_nis": float(np.percentile(filt.pre_gate_nis, 95)),
        "effective_mean_nis": float(np.mean(filt.nis)),
        "downweighted_measurement_fraction": float(np.mean(filt.r_scale > 1.0)),
        "mean_abs_lag1_whitened_innovation": float(
            np.mean([
                abs(_lag1(_whiten_innovations(
                    filt.innovation, filt.pre_gate_innovation_cov
                )[filt.sensor == sensor, axis]))
                for sensor in (1, 2) for axis in (0, 1)
            ])
        ),
        "median_position_std_m": float(
            np.median(np.hypot(kin["x_std"], kin["y_std"]))
        ),
        "max_position_std_m": float(
            np.max(np.hypot(kin["x_std"], kin["y_std"]))
        ),
        "filtered_covariance_min_eigenvalue": float(np.min([
            np.min(np.linalg.eigvalsh(matrix)) for matrix in filt.filtered_cov
        ])),
        "smoothed_covariance_min_eigenvalue": float(np.min([
            np.min(np.linalg.eigvalsh(matrix)) for matrix in smooth.cov
        ])),
        "output_covariance_min_eigenvalue": float(np.min([
            np.min(np.linalg.eigvalsh(matrix)) for matrix in state_cov
        ])),
        "output_rows": int(grid.size),
        "output_start_s": float(grid[0]),
        "output_end_s": float(grid[-1]),
        "output_dt_s": float(output_dt),
        "output_finite": bool(np.all(np.isfinite(state))),
        "output_csv": str(output_csv),
        "innovation_csv": None if innovation_csv is None else str(innovation_csv),
        "tuning_csv": None if tuning_csv is None else str(tuning_csv),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
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
    p.add_argument("--tuning", default="05_results/q3_process_noise_tuning.csv")
    p.add_argument("--time-col", default="时间(s)")
    p.add_argument("--x-col", default="X坐标(m)")
    p.add_argument("--y-col", default="Y坐标(m)")
    p.add_argument("--coarse-grid-dt", type=float, default=0.02)
    p.add_argument("--max-abs-lag", type=float, default=120.0)
    p.add_argument("--fine-half-width", type=float, default=10.0)
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
    p.add_argument("--jerk-q", type=float)
    p.add_argument("--fixed-bias-rw-var", type=float, default=1e-8)
    p.add_argument("--drifting-bias-rw-var", type=float, default=1e-4)
    p.add_argument("--gate-probability", type=float, default=0.99)
    p.add_argument("--output-dt", type=float, default=0.1)
    return p


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = _build_parser().parse_args()
    summary = run_pipeline(
        workbook=args.workbook,
        sheet1=args.sheet1,
        sheet2=args.sheet2,
        output_csv=args.output,
        summary_json=args.summary,
        innovation_csv=args.innovations,
        tuning_csv=args.tuning,
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
