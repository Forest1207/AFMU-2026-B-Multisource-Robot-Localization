"""Generate the four structural/statistical figures required by the paper audit.

The script only reads versioned result files and writes deterministic figure
triplets under ``06_figures/paper``.  It does not touch any original workbook.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "06_figures" / "paper"
COLORS = {
    "navy": "#24557A",
    "blue": "#4B8BBE",
    "teal": "#2A9D8F",
    "gold": "#E9C46A",
    "orange": "#F4A261",
    "red": "#C95D63",
    "gray": "#66717E",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "svg.fonttype": "none",
        }
    )


def _save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(OUT / f"{stem}.{suffix}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _box(ax: plt.Axes, xy: tuple[float, float], text: str, color: str, width: float = 0.19) -> None:
    x, y = xy
    patch = FancyBboxPatch(
        (x - width / 2, y - 0.075),
        width,
        0.15,
        boxstyle="round,pad=0.015,rounding_size=0.018",
        linewidth=1.1,
        edgecolor=color,
        facecolor="white",
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", color="#263238", linespacing=1.35)


def technical_route() -> None:
    fig, ax = plt.subplots(figsize=(8.6, 2.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    xs = [0.10, 0.30, 0.50, 0.70, 0.90]
    labels = [
        "Raw 4/5 Hz\nobservations",
        "Time alignment\nand calibration",
        "Asynchronous KF\nand RTS smoothing",
        "Bias decision\nand 10 Hz state",
        "Feasible windows\nand MILP schedule",
    ]
    colors = [COLORS["gray"], COLORS["blue"], COLORS["teal"], COLORS["gold"], COLORS["orange"]]
    for x, label, color in zip(xs, labels, colors):
        _box(ax, (x, 0.56), label, color, width=0.17)
    for left, right in zip(xs[:-1], xs[1:]):
        ax.add_patch(
            FancyArrowPatch(
                (left + 0.09, 0.56),
                (right - 0.09, 0.56),
                arrowstyle="-|>",
                mutation_scale=12,
                color=COLORS["navy"],
                linewidth=1.2,
            )
        )
    ax.text(0.5, 0.92, "Technical route: alignment, fusion, inference and scheduling", ha="center", weight="bold")
    ax.text(0.30, 0.18, "Q1", ha="center", color=COLORS["blue"], weight="bold")
    ax.text(0.50, 0.18, "Q2", ha="center", color=COLORS["teal"], weight="bold")
    ax.text(0.70, 0.18, "Q3", ha="center", color="#9B7D1F", weight="bold")
    ax.text(0.90, 0.18, "Q4", ha="center", color=COLORS["orange"], weight="bold")
    _save(fig, "technical_route")


def subproblem_flow() -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    nodes = {
        "q1": ((0.16, 0.72), "Q1  noiseless\ntime offset + 10 Hz", COLORS["blue"]),
        "q2": ((0.50, 0.72), "Q2  noisy data\ntime/bias + fusion", COLORS["teal"]),
        "q3": ((0.84, 0.72), "Q3  actual data\nbias test + state", COLORS["gold"]),
        "q4": ((0.84, 0.28), "Q4  fixed trajectory\nwindows + MILP", COLORS["orange"]),
        "contract": ((0.50, 0.28), "Shared contract\nclock, units, 10 Hz", COLORS["gray"]),
    }
    for xy, label, color in nodes.values():
        _box(ax, xy, label, color, width=0.24)
    arrows = [
        ((0.28, 0.72), (0.38, 0.72), "alignment convention"),
        ((0.62, 0.72), (0.72, 0.72), "robust fusion contract"),
        ((0.84, 0.62), (0.84, 0.39), "state + uncertainty"),
        ((0.62, 0.28), (0.72, 0.28), "validation rules"),
        ((0.50, 0.39), (0.50, 0.61), "shared interface"),
    ]
    for start, end, label in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12, color=COLORS["navy"], linewidth=1.2))
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(mid[0], mid[1] + 0.035, label, ha="center", va="bottom", fontsize=7.5, color=COLORS["gray"])
    ax.text(0.5, 0.94, "Subproblem dependency and evidence flow", ha="center", weight="bold")
    _save(fig, "subproblem_flow")


def model_comparison() -> None:
    data = pd.read_csv(ROOT / "05_results" / "q1" / "interpolation_comparison.csv")
    data = data.sort_values("rmse_m", ascending=False)
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    bars = ax.bar(data["method"], data["rmse_m"], color=[COLORS["gray"], COLORS["orange"], COLORS["teal"], COLORS["blue"]])
    ax.set_yscale("log")
    ax.set_ylabel("Cross-sensor RMSE (m, log scale)")
    ax.set_xlabel("Interpolation model")
    ax.set_title("Q1 interpolation-model comparison")
    ax.grid(axis="y", which="both", linewidth=0.5, alpha=0.35)
    for bar, value in zip(bars, data["rmse_m"]):
        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.45, f"{value:.2e}", ha="center", va="bottom", fontsize=8)
    _save(fig, "model_comparison")


def cumulative_distribution() -> None:
    data = pd.read_csv(ROOT / "05_results" / "q4" / "feasible_tasks.csv")
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    for task, color in (("射击", COLORS["red"]), ("拍照", COLORS["blue"])):
        values = np.sort(data.loc[data["task"] == task, "normalized_margin"].to_numpy(float))
        probability = np.arange(1, len(values) + 1) / len(values)
        label = "Shooting" if task == "射击" else "Photography"
        ax.step(values, probability, where="post", linewidth=1.6, color=color, label=f"{label} (n={len(values)})")
    ax.axvline(0.4240747629, color=COLORS["gold"], linestyle="--", linewidth=1.5, label="Selected minimum = 0.4241")
    ax.set_xlabel("Normalized feasibility margin")
    ax.set_ylabel("Empirical cumulative probability")
    ax.set_title("Q4 candidate-margin empirical CDF")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.01)
    ax.grid(linewidth=0.5, alpha=0.35)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    _save(fig, "candidate_margin_cdf")


def main() -> None:
    _style()
    technical_route()
    subproblem_flow()
    model_comparison()
    cumulative_distribution()


if __name__ == "__main__":
    main()
