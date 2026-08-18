"""Synthetic recovery test for the Q1 time-alignment algorithm."""

from __future__ import annotations

import numpy as np

from data_loader import TrajectorySamples
from interpolation_models import build_trajectory
from time_alignment import estimate_time_offset


def true_position(t: np.ndarray) -> np.ndarray:
    """Non-periodic-enough smooth 2-D path for an identifiability test."""
    x = 0.015 * t + 2.0 * np.sin(0.037 * t) + 0.2 * np.sin(0.131 * t)
    y = 0.0008 * t**2 + 1.4 * np.cos(0.041 * t) + 0.15 * np.sin(0.173 * t)
    return np.column_stack((x, y))


def main() -> None:
    true_dt = -3.7317

    t1 = np.arange(20.0, 180.0, 0.25)
    t2 = np.arange(38.0, 210.0, 0.20)

    p1 = true_position(t1)
    p2 = true_position(t2 + true_dt)

    s1 = TrajectorySamples("synthetic-4Hz", t1, p1, 4.0)
    s2 = TrajectorySamples("synthetic-5Hz", t2, p2, 5.0)
    s1.validate()
    s2.validate()

    tr1 = build_trajectory(s1, "cubic")
    tr2 = build_trajectory(s2, "cubic")
    result, _, _ = estimate_time_offset(
        s1,
        s2,
        tr1,
        tr2,
        min_overlap_seconds=30.0,
        coarse_step=0.5,
        final_eval_dt=0.05,
    )

    error = abs(result.time_offset_s - true_dt)
    print(f"true Δt={true_dt:.6f}s, estimated={result.time_offset_s:.9f}s")
    print(f"absolute error={error:.3e}s, RMSE={result.loss.rmse:.3e}m")
    if error > 0.01:
        raise AssertionError("Synthetic time-offset recovery failed.")


if __name__ == "__main__":
    main()
