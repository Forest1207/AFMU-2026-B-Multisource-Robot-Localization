"""Publication figures for Q2 calibration and fusion diagnostics."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2

plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42


def save_figure(fig: plt.Figure, png_path: str | Path) -> None:
    path = Path(png_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_objective(offsets: np.ndarray, robust: np.ndarray, ordinary: np.ndarray,
                   optimum: float, path: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.plot(offsets, ordinary, color="#999999", linewidth=1.2, label="ordinary profile")
    ax.plot(offsets, robust, color="#0072B2", linewidth=1.8, label="Huber profile")
    ax.axvline(optimum, color="#D55E00", linestyle="--", label=f"optimum {optimum:.4f} s")
    ax.set_xlabel("time offset (s)")
    ax.set_ylabel("profile objective (m²)")
    ax.set_title("Q2 spatio-temporal calibration objective")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    save_figure(fig, path)


def plot_calibration(a: np.ndarray, b: np.ndarray, b_corrected: np.ndarray,
                     path: str | Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), sharex=True, sharey=True)
    axes[0].plot(a[:, 0], a[:, 1], color="#0072B2", linewidth=1.2, label="method 1")
    axes[0].plot(b[:, 0], b[:, 1], color="#D55E00", linewidth=1.0, alpha=0.8, label="method 2 raw")
    axes[0].set_title("Before spatial-bias correction")
    axes[1].plot(a[:, 0], a[:, 1], color="#0072B2", linewidth=1.2, label="method 1")
    axes[1].plot(b_corrected[:, 0], b_corrected[:, 1], color="#009E73", linewidth=1.0,
                 alpha=0.8, label="method 2 corrected")
    axes[1].set_title("After correction")
    for ax in axes:
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("X (m)")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
    axes[0].set_ylabel("Y (m)")
    fig.tight_layout()
    save_figure(fig, path)


def plot_fused_trajectory(trajectory: pd.DataFrame, path: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    ax.plot(trajectory["x"], trajectory["y"], color="#0072B2", linewidth=1.4)
    ax.scatter(trajectory["x"].iloc[0], trajectory["y"].iloc[0], s=42,
               facecolors="white", edgecolors="black", label="start", zorder=3)
    ax.scatter(trajectory["x"].iloc[-1], trajectory["y"].iloc[-1], s=42,
               marker="s", color="#D55E00", edgecolors="black", label="end", zorder=3)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("Q2 asynchronous KF/RTS fused trajectory at 10 Hz")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    save_figure(fig, path)


def plot_innovations(innovations: pd.DataFrame, path: str | Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(8.2, 8.0), sharex=True)
    for axis_index, component in enumerate(("x", "y")):
        for sensor, color in [(1, "#0072B2"), (2, "#D55E00")]:
            d = innovations[innovations["sensor"] == sensor]
            axes[axis_index].plot(
                d["time_s"], d[f"innovation_{component}"], color=color,
                linewidth=0.55, alpha=0.65, label=f"method {sensor}, {component}"
            )
        axes[axis_index].axhline(0.0, color="black", linewidth=0.7)
        axes[axis_index].set_ylabel("innovation (m)")
        axes[axis_index].legend(frameon=False, ncol=2)
        axes[axis_index].grid(alpha=0.2)
    axes[0].set_title("Q2 innovation and normalized innovation squared")
    nis_column = "pre_gate_nis" if "pre_gate_nis" in innovations else "nis"
    axes[2].plot(innovations["time_s"], innovations[nis_column], color="#009E73", linewidth=0.55)
    axes[2].axhline(chi2.ppf(0.99, 2), color="#D55E00", linestyle="--",
                    label="99% chi-square gate")
    axes[2].set_xlabel("reference time (s)")
    axes[2].set_ylabel("pre-gate NIS")
    axes[2].set_ylim(bottom=0)
    axes[2].legend(frameon=False)
    axes[2].grid(alpha=0.2)
    fig.tight_layout()
    save_figure(fig, path)


def plot_tuning(tuning: pd.DataFrame, selected_q: float, path: str | Path) -> None:
    fig, ax1 = plt.subplots(figsize=(8.0, 4.6))
    ax1.semilogx(tuning["jerk_spectral_density"], tuning["diagnostic_score"],
                 marker="o", color="#0072B2", label="diagnostic score")
    ax1.axvline(selected_q, color="#D55E00", linestyle="--", label=f"selected q={selected_q:.3g}")
    ax1.set_xlabel("jerk spectral density q")
    ax1.set_ylabel("NIS/whiteness score")
    ax1.set_yscale("log")
    ax1.set_title("Q2 process-noise selection")
    ax1.grid(alpha=0.25, which="both")
    ax1.legend(frameon=False)
    fig.tight_layout()
    save_figure(fig, path)
