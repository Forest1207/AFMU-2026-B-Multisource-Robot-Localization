"""Rebuild Q3 figures and provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from diagnostics import (
    plot_bias_ci,
    plot_bias_series,
    plot_innovations,
    plot_objective,
    plot_trajectory,
    plot_tuning,
)

HERE = Path(__file__).resolve().parent
Q2_DIR = HERE.parent / "q2"
if str(Q2_DIR) not in sys.path:
    sys.path.insert(0, str(Q2_DIR))

from data_loader import load_two_streams  # noqa: E402
from joint_alignment import aligned_samples, profile_objective_scan  # noqa: E402
from preprocess import clean_stream  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--sheet1", required=True)
    p.add_argument("--sheet2", required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--figures", type=Path, required=True)
    args = p.parse_args()
    params = json.loads((args.results / "parameters.json").read_text(encoding="utf-8"))
    s1, s2 = load_two_streams(args.input, args.sheet1, args.sheet2)
    t1, xy1 = clean_stream(s1.time, s1.xy, remove_speed_outliers=False)
    t2, xy2 = clean_stream(s2.time, s2.xy, remove_speed_outliers=False)
    coarse = float(params["coarse_time_offset_s"])
    dt = float(params["time_offset_s"])
    offsets = np.linspace(coarse - 10.0, coarse + 10.0, 401)
    objective, _ = profile_objective_scan(t1, xy1, t2, xy2, offsets, robust_iterations=3)
    aligned_time, a, b = aligned_samples(t1, xy1, t2, xy2, dt, 0.1, "pchip")
    args.figures.mkdir(parents=True, exist_ok=True)
    plot_objective(offsets, objective, dt, args.figures / "objective_profile.png")
    plot_bias_ci(params["wald"], params["bootstrap"], args.figures / "bias_confidence_interval.png")
    plot_bias_series(aligned_time, b - a, args.figures / "bias_time_series.png")
    plot_trajectory(pd.read_csv(args.results / "trajectory_10hz.csv"),
                    args.figures / "fused_trajectory_uncertainty.png")
    plot_innovations(pd.read_csv(args.results / "innovations.csv"),
                     args.figures / "innovation_diagnostics.png")
    plot_tuning(pd.read_csv(args.results / "process_noise_tuning.csv"),
                float(params["selected_jerk_spectral_density"]),
                args.figures / "process_noise_tuning.png")
    stems = ["objective_profile", "bias_confidence_interval", "bias_time_series",
             "fused_trajectory_uncertainty", "innovation_diagnostics", "process_noise_tuning"]
    manifest = {
        "input": str(args.input),
        "input_sha256": sha256(args.input),
        "source_results": ["parameters.json", "trajectory_10hz.csv", "innovations.csv",
                           "process_noise_tuning.csv"],
        "figures": [{"stem": s, "formats": ["png", "svg", "pdf"]} for s in stems],
    }
    (args.results / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"generated {len(stems)} Q3 figures")


if __name__ == "__main__":
    main()
