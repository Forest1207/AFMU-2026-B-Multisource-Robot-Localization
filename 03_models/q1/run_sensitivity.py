"""One-factor sensitivity checks for the Q1 time-offset estimate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from data_loader import load_attachment1
from interpolation_models import build_trajectory
from time_alignment import estimate_time_offset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Q1 numerical sensitivity checks.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("05_results/q1/sensitivity.csv"),
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    stream1, stream2 = load_attachment1(args.input)
    trajectory1 = build_trajectory(stream1, "cubic")
    trajectory2 = build_trajectory(stream2, "cubic")

    baseline = {
        "min_overlap_seconds": 60.0,
        "coarse_step": 0.5,
        "final_eval_dt": 0.05,
    }
    scenarios = [("baseline", "none", 0.0, baseline)]
    for parameter, values in {
        "min_overlap_seconds": (120.0, 300.0, 600.0),
        "coarse_step": (0.25, 1.0),
        "final_eval_dt": (0.025, 0.1),
    }.items():
        for value in values:
            config = baseline | {parameter: value}
            scenarios.append((f"{parameter}={value:g}", parameter, value, config))

    rows = []
    for scenario, parameter, value, config in scenarios:
        result, _, _ = estimate_time_offset(
            stream1,
            stream2,
            trajectory1,
            trajectory2,
            min_overlap_seconds=config["min_overlap_seconds"],
            coarse_step=config["coarse_step"],
            final_eval_dt=config["final_eval_dt"],
        )
        rows.append(
            {
                "scenario": scenario,
                "varied_parameter": parameter,
                "varied_value": value,
                **config,
                "time_offset_s": result.time_offset_s,
                "reported_time_offset_s": round(result.time_offset_s, 4),
                "aligned_rmse_m": result.loss.rmse,
                "overlap_seconds": result.loss.overlap_seconds,
                "boundary_distance_s": result.boundary_distance_s,
            }
        )

    result_table = pd.DataFrame(rows)
    spread = float(result_table["time_offset_s"].max() - result_table["time_offset_s"].min())
    if spread > 1e-6:
        raise AssertionError(f"Q1 offset sensitivity spread is too large: {spread:.3e}s")
    if not (result_table["reported_time_offset_s"] == -198.4317).all():
        raise AssertionError("Q1 reported offset changes under a planned sensitivity scenario.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_table.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"scenarios={len(result_table)}, raw offset spread={spread:.3e}s")
    print(f"written: {args.output}")


if __name__ == "__main__":
    main()
