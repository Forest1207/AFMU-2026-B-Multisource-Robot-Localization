"""Publication figures for Q4 feasibility and optimized scheduling."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle

plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def save(fig: plt.Figure, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def plot_optimization_framework(path: str | Path) -> None:
    """Draw the mathematical solution framework for Q4 scheduling."""
    fig, ax = plt.subplots(figsize=(12.2, 7.0))
    ax.set_xlim(0, 12.2)
    ax.set_ylim(0, 7.0)
    ax.axis("off")

    colors = {
        "input": "#D9EAF7",
        "candidate": "#DDF1E4",
        "baseline": "#F8E9C7",
        "optimization": "#E9E2F3",
        "output": "#F4E1DC",
        "line": "#5F6B7A",
        "muted": "#66757F",
    }

    def box(x: float, y: float, w: float, h: float, title: str,
            lines: list[str], fill: str, fontsize: float = 9.2) -> None:
        header_h = 0.34
        ax.add_patch(Rectangle((x, y), w, h, facecolor="white",
                               edgecolor=colors["line"], linewidth=1.05))
        ax.add_patch(Rectangle((x, y + h - header_h), w, header_h,
                               facecolor=fill, edgecolor="none"))
        ax.plot([x, x + w], [y + h - header_h, y + h - header_h],
                color=colors["line"], linewidth=0.75)
        ax.text(x + 0.12, y + h - header_h / 2, title, ha="left", va="center",
                fontsize=9.8, fontweight="bold", color="#263238")
        ax.text(x + 0.12, y + h - 0.49, "\n".join(lines), ha="left", va="top",
                fontsize=fontsize, color="#263238", linespacing=1.28)

    def arrow(x1: float, y1: float, x2: float, y2: float,
              label: str | None = None, bend: float = 0.0) -> None:
        patch = FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
            linewidth=1.15, color=colors["line"],
            connectionstyle=f"arc3,rad={bend}", shrinkA=2, shrinkB=2,
        )
        ax.add_patch(patch)
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.10, label,
                    ha="center", va="bottom", fontsize=8.4,
                    color=colors["muted"],
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.8})

    def routed_arrow(points: list[tuple[float, float]],
                     label: str | None = None,
                     label_xy: tuple[float, float] | None = None) -> None:
        for start, end in zip(points[:-2], points[1:-1], strict=True):
            ax.plot([start[0], end[0]], [start[1], end[1]],
                    color=colors["line"], linewidth=1.15)
        start, end = points[-2], points[-1]
        arrow(start[0], start[1], end[0], end[1])
        if label and label_xy:
            ax.text(label_xy[0], label_xy[1], label, ha="center", va="center",
                    fontsize=8.4, color=colors["muted"],
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.8})

    ax.text(6.1, 6.72, "问题四固定轨迹任务调度的求解与优化框架",
            ha="center", va="center", fontsize=15, fontweight="bold",
            color="#172126")

    ax.text(1.25, 6.25, "输入与状态", ha="center", fontsize=10.5,
            fontweight="bold", color="#315B73")
    box(0.20, 4.90, 2.10, 1.05, "轨迹状态", [r"$\mathbf{s}(t)=(\mathbf{p},v,a)$", "问题三输出的 10 Hz 状态"], colors["input"])
    box(0.20, 3.55, 2.10, 1.05, "任务对象", [r"目标坐标 $\mathbf{g}_j$", "射击与拍照任务类型"], colors["input"])
    box(0.20, 2.20, 2.10, 1.05, "规则参数", [r"$L_s,L_p,\varepsilon$", "距离、速度、加速度、角差"], colors["input"])

    ax.text(3.85, 6.25, "候选构造", ha="center", fontsize=10.5,
            fontweight="bold", color="#2D6A4F")
    box(2.75, 4.75, 2.20, 1.20, "完整准备窗筛选",
        [r"$I_c=[t_c-L_k,t_c]$", "窗口内各时刻均满足物理约束"], colors["candidate"])
    box(2.75, 3.20, 2.20, 1.20, "候选压缩",
        [r"时间步长 $h_c$", r"方向角分箱 $\Delta\theta$", "保留高裕度代表点"], colors["candidate"])
    box(2.75, 1.65, 2.20, 1.20, "细网格复核",
        [r"复核步长 $h_f$", r"计算 $m_c$，形成 $\mathcal{C}$"], colors["candidate"])

    ax.text(7.25, 6.25, "基线与精确优化", ha="center", fontsize=10.5,
            fontweight="bold", color="#6A4C78")
    box(5.55, 4.75, 1.95, 1.20, "贪心基线",
        ["按执行时刻扫描", r"得到下界 $N_G$"], colors["baseline"])
    box(7.85, 4.75, 2.15, 1.20, "冲突建模",
        ["资源区间最大团", "射击唯一性", r"拍照角差冲突集 $\mathcal{A}$"], colors["optimization"], 8.8)
    box(5.55, 3.20, 2.05, 1.20, "第一级：任务数",
        [r"$N^*=\max\sum_c x_c$", r"$x_c\in\{0,1\}$"], colors["optimization"])
    box(7.95, 3.20, 2.05, 1.20, "第二级：最差裕度",
        [r"$z^*=\max\min_{x_c=1}m_c$", r"固定 $\sum_cx_c=N^*$"], colors["optimization"])
    box(6.75, 1.65, 2.05, 1.20, "第三级：总体裕度",
        [r"$\max\sum_c m_cx_c$", r"固定 $N^*$ 与 $z^*$"], colors["optimization"])

    ax.text(11.05, 6.25, "输出与复核", ha="center", fontsize=10.5,
            fontweight="bold", color="#8A4F45")
    box(10.45, 4.45, 1.55, 1.50, "时刻输出",
        ["执行时刻舍入", "按时间排序"], colors["output"], 8.8)
    box(10.45, 2.55, 1.55, 1.35, "可行性复核",
        ["完整准备窗", "任务间冲突", "角差与唯一性"], colors["output"], 8.6)
    box(10.45, 0.95, 1.55, 1.05, "最终日程",
        [r"$N^*,z^*$ 与任务表"], colors["output"], 8.8)

    routed_arrow([(2.30, 5.42), (2.53, 5.42), (2.53, 5.35), (2.75, 5.35)])
    routed_arrow([(2.30, 4.07), (2.48, 4.07), (2.48, 5.15), (2.75, 5.15)])
    routed_arrow([(2.30, 2.72), (2.43, 2.72), (2.43, 4.95), (2.75, 4.95)])
    arrow(3.85, 4.75, 3.85, 4.40)
    arrow(3.85, 3.20, 3.85, 2.85)
    routed_arrow([(4.95, 2.25), (5.20, 2.25), (5.20, 5.35), (5.55, 5.35)],
                 "候选集", (5.20, 3.65))
    routed_arrow([(4.95, 2.25), (5.20, 2.25), (5.20, 6.06),
                  (8.92, 6.06), (8.92, 5.95)], "候选冲突", (7.15, 6.06))
    arrow(6.52, 4.75, 6.52, 4.40, label="下界")
    routed_arrow([(8.92, 4.75), (8.92, 4.57), (6.58, 4.57), (6.58, 4.40)])
    arrow(7.60, 3.80, 7.95, 3.80)
    arrow(6.58, 3.20, 7.25, 2.85)
    arrow(8.97, 3.20, 8.30, 2.85)
    routed_arrow([(8.80, 2.18), (10.18, 2.18), (10.18, 5.20), (10.45, 5.20)])
    arrow(11.22, 4.45, 11.22, 3.90)
    arrow(11.22, 2.55, 11.22, 2.00)

    ax.text(6.1, 0.38,
            "词典序优先级：任务总数  >  最小安全裕度  >  总安全裕度",
            ha="center", va="center", fontsize=10.2, fontweight="bold",
            color="#37474F")
    fig.tight_layout(pad=0.35)
    save(fig, path)


def plot_trajectory_targets(trajectory: pd.DataFrame, targets: pd.DataFrame,
                            schedule: pd.DataFrame, path: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 6.3))
    ax.plot(trajectory["x"], trajectory["y"], color="#555555", linewidth=1.2,
            label="fixed Q3 trajectory")
    for task, english, marker, color in [("射击", "shooting", "x", "#D55E00"), ("拍照", "photography", "^", "#0072B2")]:
        subset = targets[targets["task"] == task]
        ax.scatter(subset["x_m"], subset["y_m"], marker=marker, color=color,
                   s=34, alpha=0.55, label=f"{english} targets")
    selected_ids = set(schedule["目标编号"])
    chosen = targets[targets["target_id"].isin(selected_ids)]
    ax.scatter(chosen["x_m"], chosen["y_m"], s=115, facecolors="none",
               edgecolors="black", linewidths=1.5, label="selected targets")
    for row in chosen.itertuples(index=False):
        ax.annotate(row.target_id, (row.x_m, row.y_m), xytext=(3, 3),
                    textcoords="offset points", fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    ax.set(xlabel="X (m)", ylabel="Y (m)",
           title="Q4 fixed trajectory, task targets and selected schedule")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    save(fig, path)


def plot_candidate_map(candidates: pd.DataFrame, schedule: pd.DataFrame,
                       path: str | Path) -> None:
    order = sorted(candidates["target_id"].unique())
    mapping = {target: index for index, target in enumerate(order)}
    y = candidates["target_id"].map(mapping)
    fig, ax = plt.subplots(figsize=(10.0, 6.6))
    points = ax.scatter(candidates["execution_time_s"], y,
                        c=candidates["normalized_margin"], cmap="viridis",
                        s=12, alpha=0.55, rasterized=True)
    ax.scatter(schedule["任务执行时刻(s)"], schedule["目标编号"].map(mapping),
               marker="*", s=110, color="#D55E00", edgecolors="black",
               linewidths=0.5, label="MILP selected")
    ax.set_yticks(np.arange(len(order)), order, fontsize=7)
    ax.set(xlabel="execution time (s)", ylabel="target",
           title="Q4 continuously verified candidate windows")
    ax.grid(alpha=0.15)
    ax.legend(frameon=False)
    fig.colorbar(points, ax=ax, label="minimum normalized margin")
    fig.tight_layout()
    save(fig, path)


def plot_schedule(schedule: pd.DataFrame, path: str | Path) -> None:
    labels = [f"{int(row['序号'])}  {row['目标编号']} {'shoot' if row['任务'] == '射击' else 'photo'}"
              for _, row in schedule.iterrows()]
    windows = [(444.0, 536.5), (748.0, 765.0), (806.0, 811.0)]
    fig, axes = plt.subplots(
        1, 3, figsize=(11.0, max(7.0, 0.27 * len(schedule))), sharey=True,
        gridspec_kw={"width_ratios": [3.8, 1.35, 0.85], "wspace": 0.06},
    )
    for ax, (left, right) in zip(axes, windows, strict=True):
        for index, row in schedule.iterrows():
            color = "#D55E00" if row["任务"] == "射击" else "#0072B2"
            start, end = row["开始准备时刻(s)"], row["任务执行时刻(s)"]
            ax.barh(index, end - start, left=start, height=0.55,
                    color=color, alpha=0.82, clip_on=True)
            if left <= end <= right:
                ax.scatter(end, index, color="black", s=18, zorder=3)
        ax.set_xlim(left, right)
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("time (s)")
    axes[0].set_yticks(np.arange(len(labels)), labels, fontsize=7)
    axes[0].invert_yaxis()
    axes[0].set_ylabel("scheduled task")
    for ax in axes[1:]:
        ax.tick_params(axis="y", left=False, labelleft=False)
    for left_ax, right_ax in zip(axes[:-1], axes[1:], strict=True):
        left_ax.spines["right"].set_visible(False)
        right_ax.spines["left"].set_visible(False)
        left_ax.tick_params(right=False)
        right_ax.tick_params(left=False)
        kwargs = dict(color="black", clip_on=False, linewidth=0.8)
        left_ax.plot((0.988, 1.012), (-0.008, 0.008), transform=left_ax.transAxes, **kwargs)
        left_ax.plot((0.988, 1.012), (0.992, 1.008), transform=left_ax.transAxes, **kwargs)
        right_ax.plot((-0.012, 0.012), (-0.008, 0.008), transform=right_ax.transAxes, **kwargs)
        right_ax.plot((-0.012, 0.012), (0.992, 1.008), transform=right_ax.transAxes, **kwargs)
    fig.suptitle("Q4 preparation intervals and execution instants", y=0.985)
    fig.subplots_adjust(left=0.20, right=0.98, top=0.95, bottom=0.07)
    save(fig, path)


def plot_margins(schedule: pd.DataFrame, path: str | Path) -> None:
    labels, distance_low, distance_high, speed, acceleration = [], [], [], [], []
    for _, row in schedule.iterrows():
        labels.append(f"{row['目标编号']} {'shoot' if row['任务'] == '射击' else 'photo'}")
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
    fig, ax = plt.subplots(figsize=(max(12.0, 0.34 * len(labels)), 5.8))
    width = 0.19
    x = np.arange(len(labels))
    names = ["distance lower", "distance upper", "speed", "acceleration"]
    colors = ["#0072B2", "#56B4E9", "#009E73", "#D55E00"]
    for index, (name, color) in enumerate(zip(names, colors, strict=True)):
        ax.bar(x + (index - 1.5) * width, values[index], width=width,
               label=name, color=color)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, labels, rotation=28, ha="right")
    ax.set(ylabel="normalized constraint margin",
           title="Q4 full-preparation-window constraint margins")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    save(fig, path)
