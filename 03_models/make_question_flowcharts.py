"""Generate compact draw.io-style method flowcharts for Questions 1--3."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle


plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["svg.fonttype"] = "none"

COLORS = {
    "input": "#ECEFF1",
    "process": "#DDF1E4",
    "estimate": "#F8E9C7",
    "model": "#F0EAE0",
    "output": "#F4E1DC",
}
LINE = "#5F6B7A"

SPECS = {
    "q1": {
        "title": "问题一时间配准与轨迹重建流程",
        "nodes": [
            ("两组观测", "4 Hz 与 5 Hz\n二维位置序列", "input"),
            ("连续轨迹", "三次样条表示\n位置与速度", "process"),
            ("全局粗定位", "速度特征归一化\n互相关", "estimate"),
            ("一维精修", "位置均方误差\nBrent 搜索", "model"),
            ("时间轴校正", "平移、公共区间\n同刻观测合并", "process"),
            ("轨迹输出", "10 Hz 二维位置\n不作区间外外推", "output"),
        ],
    },
    "q2": {
        "title": "问题二稳健标定与异步融合流程",
        "nodes": [
            ("含噪观测", "两组异步位置\n观测序列", "input"),
            ("噪声刻画", "三阶差分估计\n测量协方差", "process"),
            ("时间粗配准", "速度特征互相关\n确定搜索邻域", "estimate"),
            ("时空联合标定", "Huber 剖面目标\n估计时间与空间偏差", "model"),
            ("异步滤波", "按事件时刻顺序\n卡尔曼更新", "process"),
            ("平滑与输出", "RTS 平滑\n10 Hz 融合轨迹", "output"),
        ],
    },
    "q3": {
        "title": "问题三偏差检验与选择性融合流程",
        "nodes": [
            ("含噪观测", "两组异步位置\n观测序列", "input"),
            ("时间配准", "稳健目标估计\n时间偏差", "process"),
            ("对齐残差", "构造二维残差\n及效应量", "estimate"),
            ("偏差检验", "Wald 检验与\n移动块 Bootstrap", "model"),
            ("模型选择", "依据显著性与\n工程阈值选状态", "model"),
            ("事件融合", "卡尔曼滤波\n与 RTS 平滑", "process"),
            ("结果输出", "10 Hz 轨迹\n及位置标准差", "output"),
        ],
    },
}


def save_figure(fig: plt.Figure, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".pdf"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def draw_png_pdf_svg(spec: dict, stem: Path) -> None:
    nodes = spec["nodes"]
    fig, ax = plt.subplots(figsize=(12.0, 3.05))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.05)
    ax.axis("off")
    margin, gap = 0.22, 0.20
    width = (12 - 2 * margin - gap * (len(nodes) - 1)) / len(nodes)
    y, height, header = 0.58, 1.62, 0.38
    for index, (title, body, color_key) in enumerate(nodes):
        x = margin + index * (width + gap)
        ax.add_patch(Rectangle((x, y), width, height, facecolor="white",
                               edgecolor=LINE, linewidth=1.15))
        ax.add_patch(Rectangle((x, y + height - header), width, header,
                               facecolor=COLORS[color_key], edgecolor="none"))
        ax.plot([x, x + width], [y + height - header, y + height - header],
                color=LINE, linewidth=0.8)
        ax.text(x + 0.10, y + height - header / 2, title,
                ha="left", va="center", fontsize=10.0, fontweight="bold",
                color="#263238")
        ax.text(x + 0.10, y + height - header - 0.18, body,
                ha="left", va="top", fontsize=9.0, linespacing=1.35,
                color="#263238")
        if index < len(nodes) - 1:
            next_x = margin + (index + 1) * (width + gap)
            ax.add_patch(FancyArrowPatch(
                (x + width, y + height / 2), (next_x, y + height / 2),
                arrowstyle="-|>", mutation_scale=12, color=LINE,
                linewidth=1.15, shrinkA=3, shrinkB=3,
            ))
    ax.text(6, 2.72, spec["title"], ha="center", va="center",
            fontsize=15, fontweight="bold", color="#263238")
    fig.tight_layout(pad=0.25)
    save_figure(fig, stem)


def write_drawio(spec: dict, path: Path) -> None:
    mxfile = ET.Element("mxfile", host="app.diagrams.net", agent="Codex")
    diagram = ET.SubElement(mxfile, "diagram", id=path.stem, name=spec["title"])
    model = ET.SubElement(diagram, "mxGraphModel", dx="1400", dy="360",
                          grid="1", gridSize="10", guides="1", page="1",
                          pageWidth="1400", pageHeight="360", math="1", shadow="0")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    title = ET.SubElement(root, "mxCell", id="title", parent="1", vertex="1",
                          value=spec["title"],
                          style="text;html=1;align=center;verticalAlign=middle;fontSize=22;fontStyle=1;fontColor=#263238;")
    ET.SubElement(title, "mxGeometry", x="350", y="25", width="700", height="40", **{"as": "geometry"})
    nodes = spec["nodes"]
    margin, gap = 35, 22
    width = int((1400 - 2 * margin - gap * (len(nodes) - 1)) / len(nodes))
    for index, (node_title, body, color_key) in enumerate(nodes):
        node_id = f"n{index + 1}"
        x = margin + index * (width + gap)
        node = ET.SubElement(
            root, "mxCell", id=node_id, parent="1", vertex="1",
            value=node_title,
            style=("swimlane;html=1;rounded=0;startSize=34;horizontal=1;"
                   f"fillColor={COLORS[color_key]};swimlaneFillColor=#FFFFFF;"
                   "strokeColor=#5F6B7A;fontStyle=1;fontSize=14;"),
        )
        ET.SubElement(node, "mxGeometry", x=str(x), y="110", width=str(width),
                      height="145", **{"as": "geometry"})
        content = ET.SubElement(
            root, "mxCell", id=f"{node_id}_text", parent=node_id, vertex="1",
            value=body.replace("\n", "<br>"),
            style="text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;fontSize=12;spacing=8;",
        )
        ET.SubElement(content, "mxGeometry", y="34", width=str(width), height="111",
                      **{"as": "geometry"})
        if index:
            edge = ET.SubElement(
                root, "mxCell", id=f"e{index}", parent="1", edge="1",
                source=f"n{index}", target=node_id,
                style=("edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;"
                       "endFill=1;strokeWidth=1.5;strokeColor=#5F6B7A;"),
            )
            ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
    ET.indent(mxfile, space="  ")
    path.write_text(ET.tostring(mxfile, encoding="unicode"), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for question, spec in SPECS.items():
        directory = args.output / question
        stem = directory / "method_flow"
        directory.mkdir(parents=True, exist_ok=True)
        draw_png_pdf_svg(spec, stem)
        write_drawio(spec, stem.with_suffix(".drawio"))
    print("generated draw.io-style flowcharts for Q1--Q3")


if __name__ == "__main__":
    main()
