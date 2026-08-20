"""Publication figures for Q4 feasibility and optimized scheduling."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42


def save(fig: plt.Figure, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_trajectory_targets(trajectory: pd.DataFrame, targets: pd.DataFrame,
                            schedule: pd.DataFrame, path: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 6.5))
    ax.plot(trajectory["x"], trajectory["y"], color="#555555", linewidth=1.2,
            label="fixed Q3 trajectory")
    for task, english, marker, color in [
        ("射击", "shooting", "x", "#D55E00"),
        ("拍照", "photography", "^", "#0072B2"),
    ]:
        subset = targets[targets["task"] == task]
        ax.scatter(subset["x_m"], subset["y_m"], marker=marker, color=color,
                   s=34, alpha=0.55, label=f"{english} targets")
    selected_ids = set(schedule["目标编号"])
    chosen = targets[targets["target_id"].isin(selected_ids)]
    ax.scatter(chosen["x_m"], chosen["y_m"], s=115, facecolors="none",
               edgecolors="black", linewidths=1.4, label="covered targets")
    for row in chosen.itertuples(index=False):
        ax.annotate(row.target_id, (row.x_m, row.y_m), xytext=(3, 3),
                    textcoords="offset points", fontsize=7)
    ax.set_aspect("equal", adjustable="box")
    ax.set(xlabel="X (m)", ylabel="Y (m)",
           title="Q4 fixed trajectory, task targets and covered targets")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    save(fig, path)


def plot_candidate_map(candidates: pd.DataFrame, schedule: pd.DataFrame,
                       path: str | Path) -> None:
    order = sorted(candidates["target_id"].unique())
    mapping = {target: index for index, target in enumerate(order)}
    y = candidates["target_id"].map(mapping)
    height = max(6.6, 0.20 * len(order) + 1.4)
    fig, ax = plt.subplots(figsize=(10.2, height))
    points = ax.scatter(candidates["execution_time_s"], y,
                        c=candidates["normalized_margin"], cmap="viridis",
                        s=12, alpha=0.55, rasterized=True)
    ax.scatter(schedule["任务执行时刻(s)"], schedule["目标编号"].map(mapping),
               marker="*", s=95, color="#D55E00", edgecolors="black",
               linewidths=0.45, label="MILP selected")
    ax.set_yticks(np.arange(len(order)), order, fontsize=7)
    ax.set(xlabel="execution time (s)", ylabel="target",
           title="Q4 continuously verified candidate windows")
    ax.grid(alpha=0.15)
    ax.legend(frameon=False)
    fig.colorbar(points, ax=ax, label="minimum normalized margin")
    fig.tight_layout()
    save(fig, path)


def plot_schedule(schedule: pd.DataFrame, path: str | Path) -> None:
    n = len(schedule)
    height = max(5.0, 0.27 * n + 1.6)
    fig, ax = plt.subplots(figsize=(9.5, height))
    for index, row in schedule.reset_index(drop=True).iterrows():
        color = "#D55E00" if row["任务"] == "射击" else "#0072B2"
        start, end = row["开始准备时刻(s)"], row["任务执行时刻(s)"]
        ax.barh(index, end - start, left=start, height=0.55, color=color, alpha=0.8)
        ax.scatter(end, index, color="black", s=20, zorder=3)
    labels = [
        f"{int(row['序号'])}  {row['目标编号']} {'shoot' if row['任务'] == '射击' else 'photo'}"
        for _, row in schedule.reset_index(drop=True).iterrows()
    ]
    ax.set_yticks(np.arange(len(labels)), labels, fontsize=7 if n > 20 else 8)
    ax.invert_yaxis()
    ax.set(xlabel="reference time (s)", ylabel="scheduled task",
           title="Q4 preparation intervals and execution instants")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    save(fig, path)


def plot_margins(schedule: pd.DataFrame, path: str | Path) -> None:
    labels, distance_low, distance_high, speed, acceleration = [], [], [], [], []
    for _, row in schedule.iterrows():
        labels.append(f"{row['目标编号']} {'S' if row['任务'] == '射击' else 'P'}")
        if row["任务"] == "射击":
            dmin, dmax, vmax = 5.0, 30.0, 2.0
        else:
            dmin, dmax, vmax = 10.0, 40.0, 1.5
        width = dmax - dmin
        distance_low.append((row["准备窗最小距离(m)"] - dmin) / width)
        distance_high.append((dmax - row["准备窗最大距离(m)"]) / width)
        speed.append((vmax - row["准备窗最大速度(m/s)"]) / vmax)
        acceleration.append((1.5 - row["准备窗最大加速度(m/s²)"]) / 1.5)
    values = np.array([distance_low, distance_high, speed, acceleration])
    n = len(labels)
    width_inches = max(9.0, 0.34 * n + 2.5)
    fig, ax = plt.subplots(figsize=(width_inches, 5.4))
    bar_width = 0.19
    x = np.arange(n)
    names = ["distance lower", "distance upper", "speed", "acceleration"]
    colors = ["#0072B2", "#56B4E9", "#009E73", "#D55E00"]
    for index, (name, color) in enumerate(zip(names, colors, strict=True)):
        ax.bar(x + (index - 1.5) * bar_width, values[index], width=bar_width,
               label=name, color=color)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, labels, rotation=55 if n > 20 else 28, ha="right",
                  fontsize=7 if n > 20 else 8)
    ax.set(ylabel="normalized constraint margin",
           title="Q4 full-preparation-window constraint margins")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, ncol=4 if n > 20 else 2)
    fig.tight_layout()
    save(fig, path)
