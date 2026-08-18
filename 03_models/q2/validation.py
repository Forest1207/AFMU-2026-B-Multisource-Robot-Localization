"""Machine-checkable acceptance checks for official Q2 artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--figures", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    params = json.loads((args.results / "parameters.json").read_text(encoding="utf-8"))
    trajectory = pd.read_csv(args.results / "trajectory_10hz.csv")
    tuning = pd.read_csv(args.results / "process_noise_tuning.csv")
    sensitivity = pd.read_csv(args.results / "sensitivity.csv")
    required = ["time_s", "x", "y", "vx", "vy", "speed", "ax", "ay", "acceleration"]
    checks = {
        "required_columns": all(c in trajectory.columns for c in required),
        "all_finite": bool(np.all(np.isfinite(trajectory[required].to_numpy()))),
        "strict_time": bool(np.all(np.diff(trajectory["time_s"]) > 0)),
        "ten_hz": bool(np.max(np.abs(np.diff(trajectory["time_s"]) - 0.1)) < 1e-9),
        "row_count_matches": int(trajectory.shape[0]) == int(params["output_rows"]),
        "offset_inside_search": abs(params["time_offset_s"] - params["coarse_time_offset_s"]) < params["fine_search_half_width_s"] - 0.1,
        "corrected_mean_small": float(np.hypot(params["corrected_difference_mean_x_m"], params["corrected_difference_mean_y_m"])) < 0.02,
        "nis_consistent": abs(float(params["mean_nis"]) - 2.0) < 0.15,
        "whitened_innovation_lag1_small": float(params["mean_abs_lag1_whitened_innovation"]) < 0.10,
        "selected_q_not_boundary": float(params["selected_jerk_spectral_density"]) > float(tuning["jerk_spectral_density"].min()) and float(params["selected_jerk_spectral_density"]) < float(tuning["jerk_spectral_density"].max()),
        "sensitivity_offset_spread_small": float(sensitivity.loc[sensitivity["category"].isin(["alignment_method", "search_width"]), "time_offset_s"].max() - sensitivity.loc[sensitivity["category"].isin(["alignment_method", "search_width"]), "time_offset_s"].min()) < 0.15,
    }
    for sensor, diag in params["innovation_diagnostics_by_sensor"].items():
        checks[f"{sensor}_innovation_mean_engineering_small"] = (
            float(diag["mean_effect_index"]) < 0.25
        )
        checks[f"{sensor}_innovation_trend_engineering_small"] = (
            float(diag["trend_span_effect_index"]) < 0.25
        )
    stems = ["objective_profile", "calibration_comparison", "fused_trajectory_10hz",
             "innovation_diagnostics", "process_noise_tuning"]
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
