"""Diagnostic plots for Q1 alignment."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import TrajectorySamples
from interpolation_models import ContinuousTrajectory
from time_alignment import AlignmentResult


# Keep labels editable in vector deliverables instead of converting them to
# glyph paths; embed TrueType text in PDF for reliable publication output.
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42


def _save_publication_figure(fig: plt.Figure, path: str | Path) -> None:
    """Save a 300-DPI PNG plus editable SVG and PDF versions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")


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
    _save_publication_figure(fig, path)
    plt.close(fig)


def plot_aligned_trajectories(
    stream1: TrajectorySamples,
    stream2: TrajectorySamples,
    delta_t: float,
    path: str | Path,
) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    ax.plot(
        stream1.xy[:, 0],
        stream1.xy[:, 1],
        color="#0072B2",
        linewidth=1.8,
        label="method 1 (4 Hz)",
    )
    ax.plot(
        stream2.xy[:, 0],
        stream2.xy[:, 1],
        color="#D55E00",
        linewidth=1.4,
        linestyle="--",
        label="method 2 (5 Hz)",
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"Q1 aligned sensor coverage, Δt={delta_t:.4f} s")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    _save_publication_figure(fig, path)
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
    _save_publication_figure(fig, path)
    plt.close(fig)


def plot_trajectory_10hz(trajectory: pd.DataFrame, path: str | Path) -> None:
    """Plot the required 10 Hz trajectory with unambiguous endpoints."""
    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    ax.plot(trajectory["x"], trajectory["y"], color="#0072B2", linewidth=1.2)
    ax.scatter(
        trajectory["x"].iloc[0],
        trajectory["y"].iloc[0],
        marker="o",
        s=42,
        facecolors="white",
        edgecolors="black",
        linewidths=1.1,
        label="start",
        zorder=3,
    )
    ax.scatter(
        trajectory["x"].iloc[-1],
        trajectory["y"].iloc[-1],
        marker="s",
        s=38,
        color="#D55E00",
        edgecolors="black",
        linewidths=0.7,
        label="end",
        zorder=3,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("Q1 reconstructed trajectory at 10 Hz")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    _save_publication_figure(fig, path)
    plt.close(fig)
