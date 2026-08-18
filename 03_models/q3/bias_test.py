"""Statistical diagnostics for systematic bias in Q3 real positioning data.

The module tests the *relative* spatial bias between two already time-aligned
2-D positioning streams. It accounts for temporal correlation through a
Newey-West/HAC covariance estimator and provides a moving-block bootstrap as a
robustness check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.stats import chi2, norm


@dataclass(frozen=True)
class BiasTestResult:
    bias: np.ndarray
    cov_mean: np.ndarray
    wald_stat: float
    p_value: float
    alpha: float
    reject_null: bool
    bias_norm: float
    noise_scale: float
    effect_index: float
    practical_threshold: float
    practically_significant: bool
    hac_lag: int
    n: int

    def to_dict(self) -> dict:
        out = asdict(self)
        out["bias"] = self.bias.tolist()
        out["cov_mean"] = self.cov_mean.tolist()
        return out


@dataclass(frozen=True)
class BootstrapResult:
    point_bias: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    norm_ci: tuple[float, float]
    alpha: float
    block_length: int
    n_boot: int

    def to_dict(self) -> dict:
        return {
            "point_bias": self.point_bias.tolist(),
            "ci_low": self.ci_low.tolist(),
            "ci_high": self.ci_high.tolist(),
            "norm_ci": list(self.norm_ci),
            "alpha": self.alpha,
            "block_length": self.block_length,
            "n_boot": self.n_boot,
        }


@dataclass(frozen=True)
class TrendTestResult:
    slope: np.ndarray
    slope_se: np.ndarray
    p_value: np.ndarray
    alpha_axis: float
    significant_axis: np.ndarray
    drifting: bool
    hac_lag: int

    def to_dict(self) -> dict:
        return {
            "slope": self.slope.tolist(),
            "slope_se": self.slope_se.tolist(),
            "p_value": self.p_value.tolist(),
            "alpha_axis": self.alpha_axis,
            "significant_axis": self.significant_axis.astype(bool).tolist(),
            "drifting": bool(self.drifting),
            "hac_lag": self.hac_lag,
        }


def _as_2d(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2:
        raise ValueError("values must have shape (n, 2).")
    if x.shape[0] < 8:
        raise ValueError("At least eight aligned residual samples are required.")
    if np.any(~np.isfinite(x)):
        raise ValueError("values contain non-finite entries.")
    return x


def default_hac_lag(n: int) -> int:
    """Automatic Newey-West lag, capped to keep the estimator well behaved."""
    if n < 2:
        return 0
    lag = int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    return max(0, min(lag, n - 2))


def hac_covariance_of_mean(
    values: np.ndarray,
    max_lag: int | None = None,
) -> tuple[np.ndarray, int]:
    """Newey-West/HAC covariance of the sample mean for a bivariate series."""
    x = _as_2d(values)
    n = x.shape[0]
    lag = default_hac_lag(n) if max_lag is None else int(max_lag)
    lag = max(0, min(lag, n - 2))

    u = x - np.mean(x, axis=0, keepdims=True)
    long_run = (u.T @ u) / n
    for ell in range(1, lag + 1):
        weight = 1.0 - ell / (lag + 1.0)
        gamma = (u[ell:].T @ u[:-ell]) / n
        long_run += weight * (gamma + gamma.T)

    cov_mean = long_run / n
    cov_mean = 0.5 * (cov_mean + cov_mean.T)
    ridge = max(float(np.trace(cov_mean)) * 1e-12, 1e-15)
    cov_mean = cov_mean + ridge * np.eye(2)
    return cov_mean, lag


def _robust_noise_scale(values: np.ndarray) -> float:
    centered = values - np.median(values, axis=0, keepdims=True)
    mag = np.linalg.norm(centered, axis=1)
    med = float(np.median(mag))
    mad = float(np.median(np.abs(mag - med)))
    scale = 1.4826 * mad
    if scale <= np.finfo(float).eps:
        scale = float(np.sqrt(np.mean(np.sum(centered**2, axis=1))))
    return max(scale, np.finfo(float).eps)


def wald_bias_test(
    differences: np.ndarray,
    alpha: float = 0.05,
    max_lag: int | None = None,
    practical_threshold: float = 0.25,
) -> BiasTestResult:
    """Test H0: E[stream2-stream1] = [0, 0] with HAC covariance."""
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0, 1).")
    if practical_threshold < 0:
        raise ValueError("practical_threshold must be non-negative.")

    d = _as_2d(differences)
    bias = np.mean(d, axis=0)
    cov_mean, lag = hac_covariance_of_mean(d, max_lag=max_lag)
    inv_cov = np.linalg.pinv(cov_mean, hermitian=True)
    stat = float(bias.T @ inv_cov @ bias)
    p_value = float(chi2.sf(stat, df=2))

    bias_norm = float(np.linalg.norm(bias))
    noise_scale = _robust_noise_scale(d)
    effect = bias_norm / noise_scale

    return BiasTestResult(
        bias=bias,
        cov_mean=cov_mean,
        wald_stat=stat,
        p_value=p_value,
        alpha=alpha,
        reject_null=bool(p_value < alpha),
        bias_norm=bias_norm,
        noise_scale=noise_scale,
        effect_index=float(effect),
        practical_threshold=float(practical_threshold),
        practically_significant=bool(effect >= practical_threshold),
        hac_lag=lag,
        n=d.shape[0],
    )


def moving_block_bootstrap_bias(
    differences: np.ndarray,
    n_boot: int = 2000,
    block_length: int | None = None,
    alpha: float = 0.05,
    seed: int = 2026,
) -> BootstrapResult:
    """Moving-block bootstrap confidence intervals for the relative bias."""
    if n_boot < 100:
        raise ValueError("n_boot should be at least 100.")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0, 1).")

    d = _as_2d(differences)
    n = d.shape[0]
    if block_length is None:
        block_length = max(2, int(round(n ** (1.0 / 3.0))))
    block_length = int(block_length)
    if not 1 <= block_length <= n:
        raise ValueError("block_length must be between 1 and n.")

    rng = np.random.default_rng(seed)
    max_start = n - block_length
    n_blocks = int(np.ceil(n / block_length))
    boot = np.empty((n_boot, 2), dtype=float)
    base = np.arange(block_length)

    for b in range(n_boot):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        idx = (starts[:, None] + base[None, :]).reshape(-1)[:n]
        boot[b] = np.mean(d[idx], axis=0)

    q_low = 100.0 * alpha / 2.0
    q_high = 100.0 * (1.0 - alpha / 2.0)
    ci_low = np.percentile(boot, q_low, axis=0)
    ci_high = np.percentile(boot, q_high, axis=0)
    norms = np.linalg.norm(boot, axis=1)
    norm_ci = (
        float(np.percentile(norms, q_low)),
        float(np.percentile(norms, q_high)),
    )

    return BootstrapResult(
        point_bias=np.mean(d, axis=0),
        ci_low=np.asarray(ci_low),
        ci_high=np.asarray(ci_high),
        norm_ci=norm_ci,
        alpha=alpha,
        block_length=block_length,
        n_boot=n_boot,
    )


def _hac_ols_slope(
    time: np.ndarray,
    y: np.ndarray,
    max_lag: int,
) -> tuple[float, float, float]:
    t = np.asarray(time, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)
    tc = t - np.mean(t)
    X = np.column_stack([np.ones_like(tc), tc])
    xtx_inv = np.linalg.pinv(X.T @ X, hermitian=True)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta

    scores = X * resid[:, None]
    meat = scores.T @ scores
    for ell in range(1, max_lag + 1):
        weight = 1.0 - ell / (max_lag + 1.0)
        cross = scores[ell:].T @ scores[:-ell]
        meat += weight * (cross + cross.T)

    cov = xtx_inv @ meat @ xtx_inv
    se = float(np.sqrt(max(cov[1, 1], 0.0)))
    slope = float(beta[1])
    if se <= np.finfo(float).eps:
        p = 0.0 if abs(slope) > 1e-12 else 1.0
    else:
        p = float(2.0 * norm.sf(abs(slope / se)))
    return slope, se, p


def trend_test(
    time: np.ndarray,
    differences: np.ndarray,
    alpha: float = 0.05,
    max_lag: int | None = None,
) -> TrendTestResult:
    """Check whether relative bias has a significant linear drift over time."""
    d = _as_2d(differences)
    t = np.asarray(time, dtype=float).reshape(-1)
    if t.size != d.shape[0] or np.any(~np.isfinite(t)):
        raise ValueError("time must be finite and match differences length.")
    if np.ptp(t) <= 0:
        raise ValueError("time must span a positive interval.")

    lag = default_hac_lag(t.size) if max_lag is None else int(max_lag)
    lag = max(0, min(lag, t.size - 2))
    alpha_axis = alpha / 2.0

    slopes = np.empty(2)
    ses = np.empty(2)
    pvals = np.empty(2)
    for axis in range(2):
        slopes[axis], ses[axis], pvals[axis] = _hac_ols_slope(t, d[:, axis], lag)
    sig = pvals < alpha_axis

    return TrendTestResult(
        slope=slopes,
        slope_se=ses,
        p_value=pvals,
        alpha_axis=alpha_axis,
        significant_axis=sig,
        drifting=bool(np.any(sig)),
        hac_lag=lag,
    )


def analyze_bias(
    time: np.ndarray,
    xy1_aligned: np.ndarray,
    xy2_aligned: np.ndarray,
    alpha: float = 0.05,
    practical_threshold: float = 0.25,
    hac_lag: int | None = None,
    n_boot: int = 2000,
    block_length: int | None = None,
    seed: int = 2026,
) -> dict:
    """Run the full Q3 bias diagnostic suite on aligned positions."""
    a = np.asarray(xy1_aligned, dtype=float)
    b = np.asarray(xy2_aligned, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Aligned trajectories must have the same shape.")
    diff = _as_2d(b - a)

    wald = wald_bias_test(
        diff,
        alpha=alpha,
        max_lag=hac_lag,
        practical_threshold=practical_threshold,
    )
    bootstrap = moving_block_bootstrap_bias(
        diff,
        n_boot=n_boot,
        block_length=block_length,
        alpha=alpha,
        seed=seed,
    )
    trend = trend_test(time, diff, alpha=alpha, max_lag=hac_lag)
    return {
        "wald": wald,
        "bootstrap": bootstrap,
        "trend": trend,
        "differences": diff,
    }
