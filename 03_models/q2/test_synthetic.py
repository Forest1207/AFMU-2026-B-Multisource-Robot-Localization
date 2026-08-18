"""Synthetic sanity test for Q2 alignment and fusion modules."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
Q3_DIR = HERE.parent / "q3"
if str(Q3_DIR) not in sys.path:
    sys.path.insert(0, str(Q3_DIR))

from joint_alignment import estimate_joint_alignment
from robust_fusion import (
    asynchronous_robust_kf,
    resample_smoothed_state,
    rts_smoother,
)
from sensor_fusion import robust_third_difference_covariance
from sensor_fusion import variance_weighted_fusion


def _truth(t: np.ndarray) -> np.ndarray:
    x = 0.8 * t + 1.5 * np.sin(0.7 * t)
    y = -0.3 * t + 1.2 * np.cos(0.45 * t) + 0.15 * np.sin(1.7 * t)
    return np.column_stack((x, y))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    rng = np.random.default_rng(2026)
    true_dt = 0.37
    true_bias = np.array([0.85, -0.42])

    t1 = np.arange(0.0, 30.0, 0.25)
    t2 = np.arange(0.0, 30.0, 0.20)

    # Convention: z2(s) observes physical state at s - true_dt plus bias.
    xy1 = _truth(t1) + rng.normal(scale=[0.025, 0.035], size=(t1.size, 2))
    xy2 = _truth(t2 - true_dt) + true_bias + rng.normal(
        scale=[0.05, 0.06], size=(t2.size, 2)
    )

    result = estimate_joint_alignment(
        t1, xy1, t2, xy2,
        dt_bounds=(0.0, 0.8),
        sample_dt=0.1,
        interpolation="pchip",
        robust_iterations=2,
    )

    print("true dt:", true_dt, "estimated:", result.dt)
    print("true bias:", true_bias, "estimated:", result.bias)
    print("aligned RMSE:", result.rmse)

    assert abs(result.dt - true_dt) < 0.08
    assert np.linalg.norm(result.bias - true_bias) < 0.15

    # Standard Huber profile must improve recovery under gross outliers.
    xy2_outlier = xy2.copy()
    outlier_idx = np.arange(8, xy2.shape[0], 17)
    xy2_outlier[outlier_idx] += rng.normal(
        loc=0.0, scale=[1.5, 1.8], size=(outlier_idx.size, 2)
    )
    ordinary = estimate_joint_alignment(
        t1, xy1, t2, xy2_outlier,
        dt_bounds=(-0.4, 1.1), sample_dt=0.1,
        interpolation="pchip", robust_iterations=0,
    )
    robust = estimate_joint_alignment(
        t1, xy1, t2, xy2_outlier,
        dt_bounds=(-0.4, 1.1), sample_dt=0.1,
        interpolation="pchip", robust_iterations=4,
    )
    ordinary_error = abs(ordinary.dt - true_dt) + np.linalg.norm(ordinary.bias - true_bias)
    robust_error = abs(robust.dt - true_dt) + np.linalg.norm(robust.bias - true_bias)
    assert robust_error < ordinary_error

    R1 = robust_third_difference_covariance(t1, xy1)
    R2 = robust_third_difference_covariance(t2, xy2)
    expected1 = np.array([0.025**2, 0.035**2])
    expected2 = np.array([0.05**2, 0.06**2])
    assert np.all((np.diag(R1) / expected1 > 0.4) & (np.diag(R1) / expected1 < 2.5))
    assert np.all((np.diag(R2) / expected2 > 0.4) & (np.diag(R2) / expected2 < 2.5))
    filt = asynchronous_robust_kf(
        t1,
        xy1,
        t2,
        xy2 - result.bias,
        time_offset=result.dt,
        R1=R1,
        R2=R2,
        estimate_bias=False,
        jerk_spectral_density=0.1,
    )
    grid, state = resample_smoothed_state(rts_smoother(filt), sample_dt=0.1)
    truth_xy = _truth(grid)
    fused_rmse = float(np.sqrt(np.mean(np.sum((state[:, :2] - truth_xy) ** 2, axis=1))))
    assert np.all(np.isfinite(state))
    assert min(np.min(np.linalg.eigvalsh(filt.filtered_cov)),
               np.min(np.linalg.eigvalsh(rts_smoother(filt).cov))) > -1e-9
    assert np.max(np.abs(np.diff(grid) - 0.1)) < 1e-10
    assert fused_rmse < 0.10

    # Simple independent check of inverse-variance weighting.
    a = np.array([[0.0, 0.0], [1.0, 1.0]])
    b = np.array([[0.2, -0.2], [1.2, 0.8]])
    fused = variance_weighted_fusion(a, b, np.array([1.0, 1.0]), np.array([4.0, 4.0]))
    assert np.allclose(fused.weights1, [0.8, 0.8])
    assert np.allclose(fused.weights2, [0.2, 0.2])
    print("synthetic fused RMSE:", fused_rmse)
    print("outlier recovery ordinary/Huber error:", ordinary_error, robust_error)
    print("synthetic test passed")


if __name__ == "__main__":
    main()
