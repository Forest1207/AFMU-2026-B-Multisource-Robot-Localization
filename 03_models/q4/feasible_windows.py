"""Sliding-window feasibility tests for Q4 shooting and photography."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ShootingRules:
    min_distance: float = 5.0
    max_distance: float = 30.0
    max_speed: float = 2.0
    max_acceleration: float = 1.5
    lead_time: float = 1.5


@dataclass(frozen=True)
class PhotographyRules:
    min_distance: float = 10.0
    max_distance: float = 40.0
    max_speed: float = 1.5
    max_acceleration: float = 1.5
    lead_time: float = 0.5


def basic_feasible_mask(
    distance: np.ndarray,
    speed: np.ndarray,
    acceleration: np.ndarray,
    min_distance: float,
    max_distance: float,
    max_speed: float,
    max_acceleration: float,
) -> np.ndarray:
    arrays = [np.asarray(v, dtype=float) for v in (distance, speed, acceleration)]
    if not (arrays[0].shape == arrays[1].shape == arrays[2].shape):
        raise ValueError("distance, speed and acceleration must have identical shapes")
    d, v, a = arrays
    return (
        np.isfinite(d) & np.isfinite(v) & np.isfinite(a)
        & (d >= min_distance) & (d <= max_distance)
        & (v <= max_speed) & (a <= max_acceleration)
    )


def rolling_all(mask: np.ndarray, window_samples: int) -> np.ndarray:
    """True at k iff mask is true for every sample in [k-window+1, k]."""
    m = np.asarray(mask, dtype=bool).reshape(-1)
    if window_samples <= 0:
        raise ValueError("window_samples must be positive")
    out = np.zeros_like(m)
    if m.size < window_samples:
        return out
    counts = np.convolve(m.astype(int), np.ones(window_samples, dtype=int), mode="valid")
    out[window_samples - 1:] = counts == window_samples
    return out


def lead_window_samples(lead_time: float, fs: float) -> int:
    """Number of samples including both endpoints of a lead-time interval."""
    if lead_time < 0 or fs <= 0:
        raise ValueError("lead_time must be non-negative and fs positive")
    return int(np.ceil(lead_time * fs - 1e-12)) + 1


def shooting_feasible_mask(
    distance: np.ndarray,
    speed: np.ndarray,
    acceleration: np.ndarray,
    fs: float = 10.0,
    rules: ShootingRules = ShootingRules(),
) -> np.ndarray:
    basic = basic_feasible_mask(
        distance, speed, acceleration,
        rules.min_distance, rules.max_distance,
        rules.max_speed, rules.max_acceleration,
    )
    return rolling_all(basic, lead_window_samples(rules.lead_time, fs))


def photography_feasible_mask(
    distance: np.ndarray,
    speed: np.ndarray,
    acceleration: np.ndarray,
    fs: float = 10.0,
    rules: PhotographyRules = PhotographyRules(),
    require_full_lead_window: bool = True,
) -> np.ndarray:
    """Return photo feasibility.

    Set ``require_full_lead_window=False`` if the final interpretation of the
    statement treats 0.5 s only as camera orientation preparation, rather than
    requiring the motion/distance limits over that entire interval.
    """
    basic = basic_feasible_mask(
        distance, speed, acceleration,
        rules.min_distance, rules.max_distance,
        rules.max_speed, rules.max_acceleration,
    )
    if not require_full_lead_window:
        return basic
    return rolling_all(basic, lead_window_samples(rules.lead_time, fs))


def true_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return inclusive [start, end] index intervals of consecutive True values."""
    m = np.asarray(mask, dtype=bool).reshape(-1)
    if m.size == 0:
        return []
    padded = np.r_[False, m, False].astype(int)
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    return list(zip(starts.tolist(), ends.tolist()))
