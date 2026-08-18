"""Q2: robust spatio-temporal calibration and asynchronous KF/RTS fusion."""

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
from scipy.stats import chi2

HERE = Path(__file__).resolve().parent
Q3_DIR = HERE.parent / "q3"
if str(Q3_DIR) not in sys.path:
    sys.path.insert(0, str(Q3_DIR))

from coarse_alignment import estimate_coarse_offset  # noqa: E402
from data_loader import load_two_streams  # noqa: E402
from joint_alignment import aligned_samples, estimate_joint_alignment  # noqa: E402
from preprocess import clean_stream  # noqa: E402
from robust_fusion import (  # noqa: E402
    asynchronous_robust_kf,
    resample_smoothed_state,
    rts_smoother,
    state_kinematics,
)
from bias_test import hac_covariance_of_mean, trend_test  # noqa: E402
from sensor_fusion import (  # noqa: E402
    robust_third_difference_covariance,
    variance_weighted_fusion,
)


def _lag1(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float).reshape(-1)
    if x.size < 3 or np.std(x[:-1]) <= 1e-12 or np.std(x[1:]) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _innovation_nll(innovation: np.ndarray, cov: np.ndarray) -> float:
    terms = []
    for v, S in zip(innovation, cov, strict=True):
        sign, logdet = np.linalg.slogdet(S)
        if sign <= 0:
            return float("inf")
        terms.append(logdet + float(v.T @ np.linalg.solve(S, v)))
    return 0.5 * float(np.mean(terms))


def _whiten_innovations(innovation: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Whiten each innovation with its contemporaneous pre-gate covariance."""
    out = np.empty_like(np.asarray(innovation, dtype=float))
    for index, (value, matrix) in enumerate(zip(innovation, cov, strict=True)):
        out[index] = np.linalg.solve(np.linalg.cholesky(matrix), value)
    return out


def select_process_noise(
    t1: np.ndarray,
    xy1: np.ndarray,
    t2: np.ndarray,
    xy2_corrected: np.ndarray,
    time_offset: float,
    R1: np.ndarray,
    R2: np.ndarray,
    candidates: np.ndarray,
    gate_probability: float,
) -> tuple[float, pd.DataFrame]:
    """Select white-jerk intensity by robust innovation likelihood."""
    rows: list[dict] = []
    for q in np.asarray(candidates, dtype=float):
        filt = asynchronous_robust_kf(
            t1,
            xy1,
            t2,
            xy2_corrected,
            time_offset=time_offset,
            R1=R1,
            R2=R2,
            estimate_bias=False,
            jerk_spectral_density=float(q),
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
        rows.append(
            {
                "jerk_spectral_density": float(q),
                "mean_robust_nll": _innovation_nll(
                    filt.innovation, filt.pre_gate_innovation_cov
                ),
                "mean_nis": float(np.mean(filt.pre_gate_nis)),
                "p95_nis": float(np.percentile(filt.pre_gate_nis, 95)),
                "effective_mean_nis": float(np.mean(filt.nis)),
                "mean_abs_lag1_whitened_innovation": float(np.mean(np.abs(ac))),
                "downweighted_fraction": float(np.mean(filt.r_scale > 1.0)),
            }
        )
    table = pd.DataFrame(rows)
    # A correctly tuned 2-D filter should have mean NIS near 2 and nearly
    # white innovations.  NLL alone tended to select the zero-process-noise
    # boundary because the robust gate changes the likelihood normalizer.
    table["diagnostic_score"] = (
        np.abs(table["mean_nis"] - 2.0)
        + 2.0 * table["mean_abs_lag1_whitened_innovation"]
    )
    best_index = int(table["diagnostic_score"].idxmin())
    return float(table.loc[best_index, "jerk_spectral_density"]), table


def _roughness(xy: np.ndarray) -> float:
    p = np.asarray(xy, dtype=float)
    if p.shape[0] < 4:
        return float("nan")
    return float(np.sqrt(np.mean(np.sum(np.diff(p, n=3, axis=0) ** 2, axis=1))))


def _innovation_diagnostics(filt) -> dict:
    out = {}
    for sensor in (1, 2):
        mask = filt.sensor == sensor
        values = filt.innovation[mask]
        time = filt.time[mask]
        mean = np.mean(values, axis=0)
        cov_mean, lag = hac_covariance_of_mean(values)
        stat = float(mean.T @ np.linalg.pinv(cov_mean, hermitian=True) @ mean)
        noise_scale = float(np.sqrt(np.mean(np.var(values, axis=0, ddof=1))))
        trend = trend_test(time, values)
        span_effect = float(
            np.linalg.norm(trend.slope * np.ptp(time)) / max(noise_scale, 1e-12)
        )
        out[f"sensor{sensor}"] = {
            "mean_x_m": float(mean[0]),
            "mean_y_m": float(mean[1]),
            "hac_wald_stat": stat,
            "hac_p_value": float(chi2.sf(stat, 2)),
            "hac_lag": int(lag),
            "mean_effect_index": float(np.linalg.norm(mean) / max(noise_scale, 1e-12)),
            "trend_slope_x_m_per_s": float(trend.slope[0]),
            "trend_slope_y_m_per_s": float(trend.slope[1]),
            "trend_p_x": float(trend.p_value[0]),
            "trend_p_y": float(trend.p_value[1]),
            "trend_span_effect_index": span_effect,
        }
    return out


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
    max_abs_lag: float = 200.0,
    fine_half_width: float = 10.0,
    interpolation: str = "pchip",
    robust_iterations: int = 4,
    gate_probability: float = 0.99,
    output_dt: float = 0.1,
    process_noise_candidates: np.ndarray | None = None,
) -> dict:
    s1, s2 = load_two_streams(
        workbook, sheet1, sheet2, time_col=time_col, x_col=x_col, y_col=y_col
    )
    t1, xy1 = clean_stream(s1.time, s1.xy, remove_speed_outliers=False)
    t2, xy2 = clean_stream(s2.time, s2.xy, remove_speed_outliers=False)

    coarse_dt = estimate_coarse_offset(
        t1, xy1, t2, xy2, grid_dt=coarse_grid_dt, max_abs_lag=max_abs_lag
    )
    robust = estimate_joint_alignment(
        t1, xy1, t2, xy2,
        dt_bounds=(coarse_dt - fine_half_width, coarse_dt + fine_half_width),
        sample_dt=output_dt,
        interpolation=interpolation,
        robust_iterations=robust_iterations,
    )
    ordinary = estimate_joint_alignment(
        t1, xy1, t2, xy2,
        dt_bounds=(coarse_dt - fine_half_width, coarse_dt + fine_half_width),
        sample_dt=output_dt,
        interpolation=interpolation,
        robust_iterations=0,
    )

    aligned_time, a, b = aligned_samples(
        t1, xy1, t2, xy2, robust.dt, output_dt, interpolation
    )
    b_corrected = b - robust.bias
    raw_difference = b - a
    corrected_difference = b_corrected - a

    R1 = robust_third_difference_covariance(t1, xy1)
    R2 = robust_third_difference_covariance(t2, xy2)
    xy2_corrected = xy2 - robust.bias
    if process_noise_candidates is None:
        process_noise_candidates = np.unique(
            np.concatenate([np.logspace(-11, -6, 11), np.logspace(-5, 2, 8)])
        )
    selected_q, tuning = select_process_noise(
        t1, xy1, t2, xy2_corrected, robust.dt, R1, R2,
        process_noise_candidates, gate_probability,
    )
    filt = asynchronous_robust_kf(
        t1, xy1, t2, xy2_corrected,
        time_offset=robust.dt,
        R1=R1,
        R2=R2,
        estimate_bias=False,
        jerk_spectral_density=selected_q,
        gate_probability=gate_probability,
    )
    smooth = rts_smoother(filt)
    grid, state = resample_smoothed_state(smooth, sample_dt=output_dt)
    kin = state_kinematics(state)

    baseline = variance_weighted_fusion(a, b_corrected, np.ones(2), np.ones(2)).fused_xy
    main_xy = np.column_stack((kin["x"], kin["y"]))
    main_overlap = np.column_stack(
        [np.interp(aligned_time, grid, kin["x"]), np.interp(aligned_time, grid, kin["y"])]
    )

    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"time_s": grid, **kin}).to_csv(
        output_csv, index=False, encoding="utf-8-sig"
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
    if tuning_csv is not None:
        tuning_csv = Path(tuning_csv)
        tuning_csv.parent.mkdir(parents=True, exist_ok=True)
        tuning.to_csv(tuning_csv, index=False, encoding="utf-8-sig")

    baseline_roughness = _roughness(baseline)
    main_roughness = _roughness(main_overlap)
    summary = {
        "input_workbook": str(Path(workbook).resolve()),
        "input_sha256": _sha256(workbook),
        "sheet1": sheet1,
        "sheet2": sheet2,
        "stream1_rows": int(t1.size),
        "stream2_rows": int(t2.size),
        "interpolation": interpolation,
        "robust_iterations": int(robust_iterations),
        "fine_search_half_width_s": float(fine_half_width),
        "gate_probability": float(gate_probability),
        "coarse_time_offset_s": float(coarse_dt),
        "time_offset_s": float(robust.dt),
        "time_offset_sign_convention": "t2_corrected = t2 - time_offset",
        "relative_bias_definition": "bias = stream2 - stream1",
        "bias_x_m": float(robust.bias[0]),
        "bias_y_m": float(robust.bias[1]),
        "bias_norm_m": float(np.linalg.norm(robust.bias)),
        "robust_alignment_rmse_m": float(robust.rmse),
        "ordinary_time_offset_s": float(ordinary.dt),
        "ordinary_bias_x_m": float(ordinary.bias[0]),
        "ordinary_bias_y_m": float(ordinary.bias[1]),
        "ordinary_alignment_rmse_m": float(ordinary.rmse),
        "overlap_samples_10hz": int(aligned_time.size),
        "uncorrected_difference_mean_x_m": float(np.mean(raw_difference[:, 0])),
        "uncorrected_difference_mean_y_m": float(np.mean(raw_difference[:, 1])),
        "corrected_difference_mean_x_m": float(np.mean(corrected_difference[:, 0])),
        "corrected_difference_mean_y_m": float(np.mean(corrected_difference[:, 1])),
        "corrected_inter_sensor_rmse_m": float(np.sqrt(np.mean(np.sum(corrected_difference**2, axis=1)))),
        "R1": R1.tolist(),
        "R2": R2.tolist(),
        "selected_jerk_spectral_density": float(selected_q),
        "mean_nis": float(np.mean(filt.pre_gate_nis)),
        "p95_nis": float(np.percentile(filt.pre_gate_nis, 95)),
        "effective_mean_nis": float(np.mean(filt.nis)),
        "mean_abs_lag1_whitened_innovation": float(tuning.loc[tuning["jerk_spectral_density"] == selected_q, "mean_abs_lag1_whitened_innovation"].iloc[0]),
        "downweighted_measurement_fraction": float(np.mean(filt.r_scale > 1.0)),
        "innovation_diagnostics_by_sensor": _innovation_diagnostics(filt),
        "baseline_equal_average_roughness": baseline_roughness,
        "main_rts_overlap_roughness": main_roughness,
        "roughness_reduction_fraction": float(1.0 - main_roughness / baseline_roughness),
        "main_to_stream1_rmse_m": float(np.sqrt(np.mean(np.sum((main_overlap - a) ** 2, axis=1)))),
        "main_to_corrected_stream2_rmse_m": float(np.sqrt(np.mean(np.sum((main_overlap - b_corrected) ** 2, axis=1)))),
        "output_start_s": float(grid[0]),
        "output_end_s": float(grid[-1]),
        "output_rows": int(grid.size),
        "output_dt_s": float(output_dt),
        "output_finite": bool(np.all(np.isfinite(main_xy))),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "output_csv": str(output_csv),
        "innovation_csv": None if innovation_csv is None else str(innovation_csv),
        "tuning_csv": None if tuning_csv is None else str(tuning_csv),
    }
    if summary_json is not None:
        summary_json = Path(summary_json)
        summary_json.parent.mkdir(parents=True, exist_ok=True)
        summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["summary_json"] = str(summary_json)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run Q2 robust calibration and fusion.")
    p.add_argument("workbook")
    p.add_argument("--sheet1", required=True)
    p.add_argument("--sheet2", required=True)
    p.add_argument("--output", default="05_results/q2/trajectory_10hz.csv")
    p.add_argument("--summary", default="05_results/q2/parameters.json")
    p.add_argument("--innovations", default="05_results/q2/innovations.csv")
    p.add_argument("--tuning", default="05_results/q2/process_noise_tuning.csv")
    p.add_argument("--time-col", default="时间(s)")
    p.add_argument("--x-col", default="X坐标(m)")
    p.add_argument("--y-col", default="Y坐标(m)")
    p.add_argument("--coarse-grid-dt", type=float, default=0.02)
    p.add_argument("--max-abs-lag", type=float, default=200.0)
    p.add_argument("--fine-half-width", type=float, default=10.0)
    p.add_argument("--interpolation", choices=["linear", "cubic", "pchip"], default="pchip")
    p.add_argument("--robust-iterations", type=int, default=4)
    p.add_argument("--gate-probability", type=float, default=0.99)
    p.add_argument("--output-dt", type=float, default=0.1)
    return p


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = _build_parser().parse_args()
    summary = run_pipeline(
        args.workbook, args.sheet1, args.sheet2, args.output,
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
        gate_probability=args.gate_probability,
        output_dt=args.output_dt,
    )
    print("Q2 completed")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
