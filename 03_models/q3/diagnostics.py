"""Publication figures for Q3 statistical decision and fused state."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2

plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42


def save(fig: plt.Figure, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=300, bbox_inches="tight")
    fig.savefig(p.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(p.with_suffix(".pdf"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_objective(offsets, objective, optimum, path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.plot(offsets, objective, color="#0072B2", linewidth=1.6)
    ax.axvline(optimum, color="#D55E00", linestyle="--", label=f"optimum {optimum:.4f} s")
    ax.set(xlabel="time offset (s)", ylabel="Huber profile objective (m²)",
           title="Q3 fixed-grid alignment objective")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    save(fig, path)


def plot_bias_ci(wald: dict, bootstrap: dict, path) -> None:
    bias = np.asarray(wald["bias"])
    low = np.asarray(bootstrap["ci_low"])
    high = np.asarray(bootstrap["ci_high"])
    yerr = np.vstack([bias - low, high - bias])
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.errorbar([0, 1], bias, yerr=yerr, fmt="o", color="#0072B2",
                capsize=6, linewidth=1.6, label="95% block-bootstrap CI")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks([0, 1], ["relative bias x", "relative bias y"])
    ax.set_ylabel("bias (m)")
    ax.set_title(f"Q3 bias decision: HAC-Wald p={wald['p_value']:.3f}")
    ax.grid(alpha=0.25, axis="y")
    ax.legend(frameon=False)
    fig.tight_layout()
    save(fig, path)


def plot_bias_series(time, difference, path) -> None:
    d = pd.DataFrame({"time": time, "dx": difference[:, 0], "dy": difference[:, 1]})
    window = max(5, int(round(len(d) / 50)))
    roll = d[["dx", "dy"]].rolling(window, center=True, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(8.2, 4.7))
    ax.plot(d["time"], d["dx"], color="#0072B2", alpha=0.18, linewidth=0.5)
    ax.plot(d["time"], d["dy"], color="#D55E00", alpha=0.18, linewidth=0.5)
    ax.plot(d["time"], roll["dx"], color="#0072B2", linewidth=1.6, label="x rolling mean")
    ax.plot(d["time"], roll["dy"], color="#D55E00", linewidth=1.6, label="y rolling mean")
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set(xlabel="reference time (s)", ylabel="method 2 - method 1 (m)",
           title="Q3 aligned inter-sensor differences")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    save(fig, path)


def plot_trajectory(trajectory: pd.DataFrame, path) -> None:
    uncertainty = np.hypot(trajectory["x_std"], trajectory["y_std"])
    fig, ax = plt.subplots(figsize=(6.8, 6.0))
    points = ax.scatter(trajectory["x"], trajectory["y"], c=uncertainty,
                        cmap="viridis", s=5, linewidths=0)
    ax.scatter(trajectory["x"].iloc[0], trajectory["y"].iloc[0], marker="o",
               facecolors="white", edgecolors="black", s=38, label="start")
    ax.scatter(trajectory["x"].iloc[-1], trajectory["y"].iloc[-1], marker="s",
               color="#D55E00", edgecolors="black", s=38, label="end")
    ax.set_aspect("equal", adjustable="box")
    ax.set(xlabel="X (m)", ylabel="Y (m)", title="Q3 10 Hz fused trajectory and position uncertainty")
    fig.colorbar(points, ax=ax, label="combined position std (m)")
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    save(fig, path)


def plot_innovations(data: pd.DataFrame, path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(8.2, 8.0), sharex=True)
    for axis_index, component in enumerate(("x", "y")):
        for sensor, color in [(1, "#0072B2"), (2, "#D55E00")]:
            z = data[data["sensor"] == sensor]
            axes[axis_index].plot(z["time_s"], z[f"innovation_{component}"],
                                  color=color, alpha=0.65, linewidth=0.55,
                                  label=f"method {sensor}, {component}")
        axes[axis_index].axhline(0, color="black", linewidth=0.7)
        axes[axis_index].set_ylabel("innovation (m)")
        axes[axis_index].legend(frameon=False, ncol=2)
        axes[axis_index].grid(alpha=0.2)
    axes[2].plot(data["time_s"], data["pre_gate_nis"], color="#009E73", linewidth=0.55)
    axes[2].axhline(chi2.ppf(0.99, 2), color="#D55E00", linestyle="--",
                    label="99% chi-square gate")
    axes[2].set(xlabel="reference time (s)", ylabel="pre-gate NIS")
    axes[2].set_ylim(bottom=0)
    axes[2].legend(frameon=False)
    axes[2].grid(alpha=0.2)
    fig.suptitle("Q3 innovation diagnostics")
    fig.tight_layout()
    save(fig, path)


def plot_tuning(data: pd.DataFrame, selected_q: float, path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.semilogx(data["jerk_spectral_density"], data["diagnostic_score"],
                marker="o", color="#0072B2")
    ax.axvline(selected_q, color="#D55E00", linestyle="--", label=f"selected q={selected_q:g}")
    ax.set(xlabel="jerk spectral density q", ylabel="NIS/whiteness score",
           title="Q3 process-noise selection")
    ax.set_yscale("log")
    ax.grid(alpha=0.25, which="both")
    ax.legend(frameon=False)
    fig.tight_layout()
    save(fig, path)
