"""Machine-readable validation gate for the official Q3 artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--figures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    params = json.loads((args.results / "parameters.json").read_text(encoding="utf-8"))
    trajectory = pd.read_csv(args.results / "trajectory_10hz.csv")
    innovations = pd.read_csv(args.results / "innovations.csv")
    tuning = pd.read_csv(args.results / "process_noise_tuning.csv")
    sensitivity = pd.read_csv(args.results / "sensitivity.csv")
    required = [
        "time_s", "x", "y", "vx", "vy", "speed", "ax", "ay",
        "acceleration", "x_std", "y_std",
    ]
    wald = params["wald"]
    boot = params["bootstrap"]
    trend = params["trend"]
    alignment = sensitivity[sensitivity["category"].isin(["alignment", "search_width"])]
    inference = sensitivity[sensitivity["category"] == "bias_inference"]
    selected_q = float(params["selected_jerk_spectral_density"])
    checks = {
        "required_columns": all(column in trajectory.columns for column in required),
        "all_finite": bool(np.all(np.isfinite(trajectory[required].to_numpy()))),
        "strict_time": bool(np.all(np.diff(trajectory["time_s"]) > 0)),
        "ten_hz": bool(np.max(np.abs(np.diff(trajectory["time_s"]) - 0.1)) < 1e-9),
        "row_count_matches": len(trajectory) == int(params["output_rows"]),
        "uncertainty_positive": bool(np.all(trajectory[["x_std", "y_std"]].to_numpy() > 0)),
        "offset_inside_search": abs(float(params["time_offset_s"]) - float(params["coarse_time_offset_s"])) < 9.9,
        "wald_does_not_reject": not bool(wald["reject_null"]) and float(wald["p_value"]) >= 0.05,
        "effect_engineering_small": (not bool(wald["practically_significant"]) and float(wald["effect_index"]) < 0.25),
        "bootstrap_axes_include_zero": all(
            float(low) <= 0.0 <= float(high)
            for low, high in zip(boot["ci_low"], boot["ci_high"], strict=True)
        ),
        "no_detected_drift": not bool(trend["drifting"]),
        "bias_state_disabled": not bool(params["bias_state_enabled"]),
        "nis_consistent": abs(float(params["mean_nis"]) - 2.0) < 0.15,
        "whitened_innovation_lag1_small": float(params["mean_abs_lag1_whitened_innovation"]) < 0.10,
        "selected_q_not_boundary": selected_q > float(tuning["jerk_spectral_density"].min()) and selected_q < float(tuning["jerk_spectral_density"].max()),
        "innovation_fields_complete": {"innovation_x", "innovation_y", "nis", "pre_gate_nis"}.issubset(innovations.columns),
        "alignment_sensitivity_small": float(alignment["time_offset_s"].max() - alignment["time_offset_s"].min()) < 0.15,
        "bias_decision_sensitivity_stable": bool(np.all(inference["p_value"] >= 0.05)),
        "bias_diagnostics_consistent": bool(params["bias_decision_diagnostics_consistent"]),
        "filter_covariance_psd": float(params["filtered_covariance_min_eigenvalue"]) >= -1e-9,
        "smoother_covariance_psd": float(params["smoothed_covariance_min_eigenvalue"]) >= -1e-9,
        "output_covariance_psd": float(params["output_covariance_min_eigenvalue"]) >= -1e-9,
    }
    stems = [
        "objective_profile", "bias_confidence_interval", "bias_time_series",
        "fused_trajectory_uncertainty", "innovation_diagnostics",
        "process_noise_tuning",
    ]
    checks["figure_triplets_complete"] = all(
        (args.figures / f"{stem}.{suffix}").exists()
        for stem in stems for suffix in ("png", "svg", "pdf")
    )
    report = {"ok": bool(all(checks.values())), "checks": checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
