"""Diagnostic plots for Q1 alignment."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from data_loader import TrajectorySamples
from interpolation_models import ContinuousTrajectory
from time_alignment import AlignmentResult


def plot_objective_scan(
    offsets: np.ndarray,
    mse: np.ndarray,
    result: AlignmentResult,
    path: str | Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(offsets, mse)
    ax.axvline(result.time_offset_s, linestyle="--", label="refined optimum")
    ax.set_xlabel("time offset Δt (s)")
    ax.set_ylabel("position MSE (m²)")
    ax.set_title("Q1 time-alignment objective")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_aligned_trajectories(
    stream1: TrajectorySamples,
    stream2: TrajectorySamples,
    delta_t: float,
    path: str | Path,
) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    ax.plot(stream1.xy[:, 0], stream1.xy[:, 1], label="method 1 (4 Hz)")
    ax.plot(stream2.xy[:, 0], stream2.xy[:, 1], label="method 2 (5 Hz)")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"Q1 spatial trajectories after time alignment, Δt={delta_t:.6f}s")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_alignment_residuals(
    traj1: ContinuousTrajectory,
    traj2: ContinuousTrajectory,
    result: AlignmentResult,
    path: str | Path,
    *,
    dt: float = 0.1,
) -> None:
    start = result.loss.overlap_start
    end = result.loss.overlap_end
    t = np.arange(start, end + 0.5 * dt, dt)
    t = t[t <= end + 1e-12]

    p1 = traj1.evaluate(t)
    p2 = traj2.evaluate(t - result.time_offset_s)
    residual = p1 - p2

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(t, residual[:, 0], label="x residual")
    ax.plot(t, residual[:, 1], label="y residual")
    ax.set_xlabel("aligned time (s)")
    ax.set_ylabel("residual (m)")
    ax.set_title("Q1 alignment residuals")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
