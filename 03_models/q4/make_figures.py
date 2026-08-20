"""Build Q4 figures and a provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from diagnostics import (
    plot_candidate_map,
    plot_margins,
    plot_optimization_framework,
    plot_schedule,
    plot_trajectory_targets,
)
from feasible_windows import load_targets


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--figures", type=Path, required=True)
    args = parser.parse_args()
    trajectory = pd.read_csv(args.trajectory)
    target_frame = pd.DataFrame([
        {"target_id": target.target_id, "x_m": target.x_m,
         "y_m": target.y_m, "task": target.task}
        for target in load_targets(args.targets)
    ])
    candidates = pd.read_csv(args.results / "feasible_tasks.csv")
    schedule = pd.read_csv(args.results / "optimized_schedule.csv")
    args.figures.mkdir(parents=True, exist_ok=True)
    plot_trajectory_targets(trajectory, target_frame, schedule,
                            args.figures / "trajectory_targets_schedule.png")
    plot_candidate_map(candidates, schedule,
                       args.figures / "candidate_feasibility_map.png")
    plot_schedule(schedule, args.figures / "optimized_schedule_timeline.png")
    plot_margins(schedule, args.figures / "constraint_margins.png")
    plot_optimization_framework(args.figures / "optimization_framework.png")
    stems = ["trajectory_targets_schedule", "candidate_feasibility_map",
             "optimized_schedule_timeline", "constraint_margins",
             "optimization_framework"]
    manifest = {
        "trajectory": str(args.trajectory),
        "trajectory_sha256": sha256(args.trajectory),
        "targets": str(args.targets),
        "targets_sha256": sha256(args.targets),
        "source_results": ["feasible_tasks.csv", "optimized_schedule.csv", "parameters.json"],
        "figures": [{"stem": stem, "formats": ["png", "svg", "pdf"]}
                    for stem in stems],
    }
    (args.results / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"generated {len(stems)} Q4 figures")


if __name__ == "__main__":
    main()
