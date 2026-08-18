"""Q3 sensitivity for alignment, bias decision and fusion hyperparameters."""

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

from data_loader import load_two_streams  # noqa: E402
from joint_alignment import aligned_samples, estimate_joint_alignment  # noqa: E402
from preprocess import clean_stream  # noqa: E402
from bias_test import analyze_bias  # noqa: E402
from robust_fusion import (  # noqa: E402
    asynchronous_robust_kf,
    resample_smoothed_state,
    rts_smoother,
)


def main() -> None:
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
    rows = []

    for method in ("linear", "pchip", "cubic"):
        for iterations in (0, 3):
            r = estimate_joint_alignment(
                t1, xy1, t2, xy2,
                dt_bounds=(coarse - 10.0, coarse + 10.0),
                interpolation=method, robust_iterations=iterations,
            )
            rows.append({"category": "alignment", "scenario": f"{method}-irls{iterations}",
                         "time_offset_s": r.dt, "bias_x_m": r.bias[0], "bias_y_m": r.bias[1],
                         "p_value": np.nan, "effect_index": np.nan,
                         "ci_x_low": np.nan, "ci_x_high": np.nan,
                         "ci_y_low": np.nan, "ci_y_high": np.nan,
                         "trajectory_rms_change_m": np.nan, "mean_pre_gate_nis": np.nan})
    for width in (5.0, 10.0, 15.0):
        r = estimate_joint_alignment(
            t1, xy1, t2, xy2,
            dt_bounds=(coarse - width, coarse + width),
            interpolation="pchip", robust_iterations=3,
        )
        rows.append({"category": "search_width", "scenario": f"half-width-{width:g}s",
                     "time_offset_s": r.dt, "bias_x_m": r.bias[0], "bias_y_m": r.bias[1],
                     "p_value": np.nan, "effect_index": np.nan,
                     "ci_x_low": np.nan, "ci_x_high": np.nan,
                     "ci_y_low": np.nan, "ci_y_high": np.nan,
                     "trajectory_rms_change_m": np.nan, "mean_pre_gate_nis": np.nan})

    dt = float(params["time_offset_s"])
    aligned_time, a, b = aligned_samples(t1, xy1, t2, xy2, dt, 0.1, "pchip")
    for hac_lag, block in [(4, 7), (8, 14), (16, 28)]:
        diag = analyze_bias(aligned_time, a, b, hac_lag=hac_lag,
                            n_boot=1000, block_length=block, seed=2026)
        w, boot = diag["wald"], diag["bootstrap"]
        rows.append({"category": "bias_inference", "scenario": f"hac-{hac_lag}_block-{block}",
                     "time_offset_s": dt, "bias_x_m": w.bias[0], "bias_y_m": w.bias[1],
                     "p_value": w.p_value, "effect_index": w.effect_index,
                     "ci_x_low": boot.ci_low[0], "ci_x_high": boot.ci_high[0],
                     "ci_y_low": boot.ci_low[1], "ci_y_high": boot.ci_high[1],
                     "trajectory_rms_change_m": np.nan, "mean_pre_gate_nis": np.nan})

    R1, R2 = np.array(params["R1"]), np.array(params["R2"])
    q0 = float(params["selected_jerk_spectral_density"])
    for factor, gate in [(0.1, 0.99), (1.0, 0.99), (10.0, 0.99),
                         (1.0, 0.975), (1.0, 0.995)]:
        filt = asynchronous_robust_kf(
            t1, xy1, t2, xy2,
            time_offset=dt, R1=R1, R2=R2,
            estimate_bias=bool(params["bias_state_enabled"]),
            initial_bias=np.array([params["profile_bias_x_m"], params["profile_bias_y_m"]])
            if params["bias_state_enabled"] else None,
            jerk_spectral_density=q0 * factor,
            bias_random_walk_var=float(params["bias_random_walk_var"]),
            gate_probability=gate,
        )
        grid, state = resample_smoothed_state(rts_smoother(filt), sample_dt=0.1)
        if len(grid) != len(official) or np.max(np.abs(grid - official["time_s"])) > 1e-8:
            raise AssertionError("Q3 sensitivity grid differs from official output.")
        change = float(np.sqrt(np.mean(np.sum((state[:, :2] - official_xy) ** 2, axis=1))))
        rows.append({"category": "fusion", "scenario": f"q-factor-{factor:g}_gate-{gate:g}",
                     "time_offset_s": dt, "bias_x_m": params["profile_bias_x_m"],
                     "bias_y_m": params["profile_bias_y_m"], "p_value": params["wald"]["p_value"],
                     "effect_index": params["wald"]["effect_index"],
                     "ci_x_low": np.nan, "ci_x_high": np.nan,
                     "ci_y_low": np.nan, "ci_y_high": np.nan,
                     "trajectory_rms_change_m": change,
                     "mean_pre_gate_nis": float(np.mean(filt.pre_gate_nis))})

    out = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")
    align = out[out["category"].isin(["alignment", "search_width"])]
    print(f"scenarios={len(out)}")
    print(f"alignment range={align.time_offset_s.min():.4f}..{align.time_offset_s.max():.4f}s")
    print(f"bias decisions reject count={(out.loc[out.category == 'bias_inference', 'p_value'] < .05).sum()}")
    print(f"max trajectory RMS change={out.trajectory_rms_change_m.max():.4f}m")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
