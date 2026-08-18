"""Synthetic sanity test for Q2 alignment and fusion modules."""

from __future__ import annotations

import numpy as np

from joint_alignment import estimate_joint_alignment
from sensor_fusion import variance_weighted_fusion


def _truth(t: np.ndarray) -> np.ndarray:
    x = 0.8 * t + 1.5 * np.sin(0.7 * t)
    y = -0.3 * t + 1.2 * np.cos(0.45 * t) + 0.15 * np.sin(1.7 * t)
    return np.column_stack((x, y))


def main() -> None:
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

    # Simple independent check of inverse-variance weighting.
    a = np.array([[0.0, 0.0], [1.0, 1.0]])
    b = np.array([[0.2, -0.2], [1.2, 0.8]])
    fused = variance_weighted_fusion(a, b, np.array([1.0, 1.0]), np.array([4.0, 4.0]))
    assert np.allclose(fused.weights1, [0.8, 0.8])
    assert np.allclose(fused.weights2, [0.2, 0.2])
    print("synthetic test passed")


if __name__ == "__main__":
    main()
