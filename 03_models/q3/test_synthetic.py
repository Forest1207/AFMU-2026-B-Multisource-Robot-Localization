"""Synthetic regression test for the Q3 alignment/bias/fusion pipeline.

Run from this directory with:
    python test_synthetic.py

The test injects a stream-2 clock offset, a constant 2-D bias, Gaussian noise
and a few outliers. It checks offset/bias recovery and verifies that the
asynchronous KF + RTS stage returns finite 10 Hz states.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
Q2_DIR = HERE.parent / "q2"
if str(Q2_DIR) not in sys.path:
    sys.path.insert(0, str(Q2_DIR))

from coarse_alignment import estimate_coarse_offset  # noqa: E402
from joint_alignment import aligned_samples, estimate_joint_alignment  # noqa: E402

from bias_test import (  # noqa: E402
    analyze_bias,
    moving_block_bootstrap_bias,
    wald_bias_test,
)
from robust_fusion import (  # noqa: E402
    asynchronous_robust_kf,
    resample_smoothed_state,
    rts_smoother,
    state_kinematics,
    symmetric_measurement_covariances,
)


def truth(t: np.ndarray) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    x = 0.08 * t**2 + 2.5 * np.sin(0.45 * t) + 0.5 * np.sin(1.2 * t)
    y = 0.03 * t**2 + 1.8 * np.cos(0.37 * t) + 0.7 * np.sin(0.9 * t)
    return np.column_stack([x, y])


def main() -> None:
    rng = np.random.default_rng(2026)
    dt_true = 0.18
    bias_true = np.array([0.60, -0.35])

    physical1 = np.arange(0.0, 30.0, 0.25)  # 4 Hz
    physical2 = np.arange(0.0, 30.0, 0.20)  # 5 Hz
    device_t1 = physical1.copy()
    device_t2 = physical2 + dt_true

    xy1 = truth(physical1) + rng.normal(
        0.0,
        0.04,
        size=(physical1.size, 2),
    )
    xy2 = truth(physical2) + bias_true + rng.normal(
        0.0,
        0.05,
        size=(physical2.size, 2),
    )
    xy2[[30, 90]] += np.array([[1.0, -0.8], [-0.9, 1.1]])

    coarse = estimate_coarse_offset(
        device_t1,
        xy1,
        device_t2,
        xy2,
        grid_dt=0.02,
        max_abs_lag=1.0,
    )
    alignment = estimate_joint_alignment(
        device_t1,
        xy1,
        device_t2,
        xy2,
        dt_bounds=(coarse - 0.4, coarse + 0.4),
        sample_dt=0.1,
        interpolation="pchip",
        robust_iterations=4,
    )

    grid, a, b = aligned_samples(
        device_t1,
        xy1,
        device_t2,
        xy2,
        dt=alignment.dt,
        sample_dt=0.1,
        interpolation="pchip",
    )
    diag = analyze_bias(
        grid,
        a,
        b,
        practical_threshold=0.2,
        n_boot=500,
        seed=2026,
    )

    assert abs(alignment.dt - dt_true) < 0.08, (alignment.dt, dt_true)
    assert np.linalg.norm(alignment.bias - bias_true) < 0.15, (
        alignment.bias,
        bias_true,
    )
    assert diag["wald"].reject_null
    assert diag["wald"].practically_significant

    # Multi-seed Monte Carlo checks the test rather than forcing the sample
    # mean to zero.  The process length matches the official aligned sample
    # order of magnitude and retains AR(1) serial correlation.
    trials = 100
    null_rejections = 0
    alternative_rejections = 0
    bootstrap_joint_coverage = 0
    for seed in range(trials):
        local_rng = np.random.default_rng(9000 + seed)
        null_noise = local_rng.normal(0.0, 0.08, size=(3000, 2))
        for k in range(1, len(null_noise)):
            null_noise[k] += 0.55 * null_noise[k - 1]
        null_rejections += int(wald_bias_test(null_noise).reject_null)
        alternative_rejections += int(wald_bias_test(
            null_noise + np.array([0.03, -0.03])
        ).reject_null)
        if seed < 30:
            interval = moving_block_bootstrap_bias(
                null_noise, n_boot=300, block_length=14, seed=12000 + seed
            )
            bootstrap_joint_coverage += int(np.all(
                (interval.ci_low <= 0.0) & (interval.ci_high >= 0.0)
            ))
    null_rate = null_rejections / trials
    power = alternative_rejections / trials
    coverage = bootstrap_joint_coverage / 30.0
    assert null_rate <= 0.10, null_rate
    assert power >= 0.90, power
    assert coverage >= 0.80, coverage

    residual = (b - alignment.bias) - a
    R1, R2 = symmetric_measurement_covariances(residual)
    filt = asynchronous_robust_kf(
        device_t1,
        xy1,
        device_t2,
        xy2,
        time_offset=alignment.dt,
        R1=R1,
        R2=R2,
        estimate_bias=True,
        initial_bias=alignment.bias,
        jerk_spectral_density=0.3,
        bias_random_walk_var=1e-8,
    )
    smooth = rts_smoother(filt)
    t10, x10 = resample_smoothed_state(smooth, sample_dt=0.1)
    kin = state_kinematics(x10)

    assert t10.size > 200
    assert np.all(np.isfinite(x10))
    assert np.all(np.isfinite(kin["speed"]))
    assert np.all(np.isfinite(kin["acceleration"]))

    print("Synthetic Q3 test passed")
    print(f"true dt={dt_true:.4f}, estimated dt={alignment.dt:.4f}")
    print(f"true bias={bias_true}, estimated bias={alignment.bias}")
    print(f"Wald p={diag['wald'].p_value:.3e}")
    print(f"Monte Carlo null rejection={null_rate:.3f}, power={power:.3f}")
    print(f"bootstrap joint coverage={coverage:.3f}")
    print(f"downweighted fraction={np.mean(filt.r_scale > 1.0):.3f}")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
