"""Rebuild all Q2 figures and their provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from data_loader import load_two_streams
from diagnostics import (
    plot_calibration,
    plot_fused_trajectory,
    plot_innovations,
    plot_objective,
    plot_tuning,
)
from joint_alignment import aligned_samples, profile_objective_scan
from preprocess import clean_stream


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--sheet1", required=True)
    p.add_argument("--sheet2", required=True)
    p.add_argument("--results", type=Path, default=Path("05_results/q2"))
    p.add_argument("--figures", type=Path, default=Path("06_figures/q2"))
    args = p.parse_args()

    params = json.loads((args.results / "parameters.json").read_text(encoding="utf-8"))
    s1, s2 = load_two_streams(args.input, args.sheet1, args.sheet2)
    t1, xy1 = clean_stream(s1.time, s1.xy, remove_speed_outliers=False)
    t2, xy2 = clean_stream(s2.time, s2.xy, remove_speed_outliers=False)
    dt = float(params["time_offset_s"])
    bias = np.array([params["bias_x_m"], params["bias_y_m"]])
    grid, a, b = aligned_samples(t1, xy1, t2, xy2, dt, 0.1, "pchip")
    coarse = float(params["coarse_time_offset_s"])
    offsets = np.linspace(coarse - 10.0, coarse + 10.0, 401)
    robust_obj, _ = profile_objective_scan(
        t1, xy1, t2, xy2, offsets, robust_iterations=4
    )
    ordinary_obj, _ = profile_objective_scan(
        t1, xy1, t2, xy2, offsets, robust_iterations=0
    )

    args.figures.mkdir(parents=True, exist_ok=True)
    plot_objective(offsets, robust_obj, ordinary_obj, dt,
                   args.figures / "objective_profile.png")
    plot_calibration(a, b, b - bias, args.figures / "calibration_comparison.png")
    trajectory = pd.read_csv(args.results / "trajectory_10hz.csv")
    innovations = pd.read_csv(args.results / "innovations.csv")
    tuning = pd.read_csv(args.results / "process_noise_tuning.csv")
    plot_fused_trajectory(trajectory, args.figures / "fused_trajectory_10hz.png")
    plot_innovations(innovations, args.figures / "innovation_diagnostics.png")
    plot_tuning(tuning, float(params["selected_jerk_spectral_density"]),
                args.figures / "process_noise_tuning.png")

    stems = ["objective_profile", "calibration_comparison", "fused_trajectory_10hz",
             "innovation_diagnostics", "process_noise_tuning"]
    manifest = {
        "input": str(args.input),
        "input_sha256": sha256(args.input),
        "source_results": ["parameters.json", "trajectory_10hz.csv", "innovations.csv",
                           "process_noise_tuning.csv"],
        "figures": [{"stem": stem, "formats": ["png", "svg", "pdf"]} for stem in stems],
    }
    (args.results / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"generated {len(stems)} Q2 figures")


if __name__ == "__main__":
    main()
