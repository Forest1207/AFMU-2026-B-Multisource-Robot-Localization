"""Q2 alignment and fusion sensitivity checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
Q3_DIR = HERE.parent / "q3"
if str(Q3_DIR) not in sys.path:
    sys.path.insert(0, str(Q3_DIR))

from data_loader import load_two_streams  # noqa: E402
from joint_alignment import estimate_joint_alignment  # noqa: E402
from preprocess import clean_stream  # noqa: E402
from robust_fusion import (  # noqa: E402
    asynchronous_robust_kf,
    resample_smoothed_state,
    rts_smoother,
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--sheet1", required=True)
    p.add_argument("--sheet2", required=True)
    p.add_argument("--parameters", type=Path, required=True)
    p.add_argument("--trajectory", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    params = json.loads(args.parameters.read_text(encoding="utf-8"))
    official = pd.read_csv(args.trajectory)
    official_xy = official[["x", "y"]].to_numpy()
    s1, s2 = load_two_streams(args.input, args.sheet1, args.sheet2)
    t1, xy1 = clean_stream(s1.time, s1.xy, remove_speed_outliers=False)
    t2, xy2 = clean_stream(s2.time, s2.xy, remove_speed_outliers=False)
    coarse = float(params["coarse_time_offset_s"])
    rows: list[dict] = []

    for method in ("linear", "pchip", "cubic"):
        for robust_iterations in (0, 2, 4):
            result = estimate_joint_alignment(
                t1, xy1, t2, xy2,
                dt_bounds=(coarse - 10.0, coarse + 10.0),
                interpolation=method,
                robust_iterations=robust_iterations,
            )
            rows.append(
                {
                    "category": "alignment_method",
                    "scenario": f"{method}-irls{robust_iterations}",
                    "time_offset_s": result.dt,
                    "bias_x_m": result.bias[0],
                    "bias_y_m": result.bias[1],
                    "alignment_rmse_m": result.rmse,
                    "trajectory_rms_change_m": np.nan,
                    "mean_nis": np.nan,
                }
            )
    for half_width in (5.0, 10.0, 15.0):
        result = estimate_joint_alignment(
            t1, xy1, t2, xy2,
            dt_bounds=(coarse - half_width, coarse + half_width),
            interpolation="pchip",
            robust_iterations=4,
        )
        rows.append(
            {
                "category": "search_width",
                "scenario": f"half-width-{half_width:g}s",
                "time_offset_s": result.dt,
                "bias_x_m": result.bias[0],
                "bias_y_m": result.bias[1],
                "alignment_rmse_m": result.rmse,
                "trajectory_rms_change_m": np.nan,
                "mean_nis": np.nan,
            }
        )

    bias = np.array([params["bias_x_m"], params["bias_y_m"]])
    R1 = np.array(params["R1"], dtype=float)
    R2 = np.array(params["R2"], dtype=float)
    q0 = float(params["selected_jerk_spectral_density"])
    for q_factor, gate in [
        (0.1, 0.99), (1.0, 0.99), (10.0, 0.99),
        (1.0, 0.975), (1.0, 0.995),
    ]:
        filt = asynchronous_robust_kf(
            t1, xy1, t2, xy2 - bias,
            time_offset=float(params["time_offset_s"]),
            R1=R1, R2=R2, estimate_bias=False,
            jerk_spectral_density=q0 * q_factor,
            gate_probability=gate,
        )
        grid, state = resample_smoothed_state(rts_smoother(filt), sample_dt=0.1)
        if grid.size != official.shape[0] or np.max(np.abs(grid - official["time_s"])) > 1e-8:
            raise AssertionError("Sensitivity output grid differs from official 10 Hz grid.")
        rms_change = float(np.sqrt(np.mean(np.sum((state[:, :2] - official_xy) ** 2, axis=1))))
        rows.append(
            {
                "category": "fusion_hyperparameter",
                "scenario": f"q-factor-{q_factor:g}_gate-{gate:g}",
                "time_offset_s": params["time_offset_s"],
                "bias_x_m": params["bias_x_m"],
                "bias_y_m": params["bias_y_m"],
                "alignment_rmse_m": params["robust_alignment_rmse_m"],
                "trajectory_rms_change_m": rms_change,
                "mean_nis": float(np.mean(filt.nis)),
            }
        )

    out = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")
    align = out[out["category"].isin(["alignment_method", "search_width"])]
    print(f"scenarios={len(out)}")
    print(f"time-offset range={align.time_offset_s.min():.6f}..{align.time_offset_s.max():.6f}s")
    print(f"max trajectory RMS change={out.trajectory_rms_change_m.max():.6e}m")


if __name__ == "__main__":
    main()
