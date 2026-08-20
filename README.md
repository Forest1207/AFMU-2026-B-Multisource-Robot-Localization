# AFMU-2026-B-Multisource-Robot-Localization

2026 年全国大学生数学建模竞赛校内选拔赛 B 题：**多源融合机器人定位及任务优化**。

本仓库统一保存题目材料、建模思路、数据探索、模型代码、正式结果、论文图件、LaTeX 论文与最终提交文件。

## 四问正式模型

- **Q1**：多插值器连续轨迹 + 互相关粗定位 + 位置 MSE 全局/连续精配准 + 10 Hz 重建；
- **Q2**：Huber 稳健时空标定 + 原始异步事件 Kalman filter + RTS smoother；
- **Q3**：HAC--Wald + moving-block bootstrap + 工程效应阈值 + 稳健 KF/RTS；
- **Q4**：连续准备窗口筛选 + 0.01 s 连续复核 + 目标覆盖/多角度拍照字典序 MILP。

### Q4 重要口径

`result.xlsx` 中初始 9 个编号行**不是任务容量约束**。正式 Q4：

- 不设置 `sum(x) <= 9`；
- 不加入题面未给出的跨任务准备时间互斥；
- 一级最大化目标覆盖数；
- 二级固定覆盖数后最大化有效拍照数；
- 三级固定前两级后最大化总安全裕度；
- 当最优任务超过 9 条时，结果表 A:E 向下扩展，H:L 红色说明/范例保持不变。

该结构参考用户提供的成熟参赛包 Q4，同时保留本仓库更严格的 0.01 s 完整窗口复核。

## 全题统一时间偏差

论文和跨问题比较统一采用

```math
t_{2,aligned}=t_2+\delta.
```

各模型内部已验证的变量符号保持不动，由 `05_results/reporting_conventions.json` 转换成统一报告口径。具体说明见 `01_ideas/time_offset_convention.md`。

## 目录

```text
00_problem/           原始题目、附件输入契约
01_ideas/             建模思路、假设、符号与备选模型
02_data_exploration/  数据探索
03_models/            Q1--Q4 正式模型代码
04_experiments/       实验与敏感性分析
05_results/           各问正式机器结果
06_figures/           正式 PNG/SVG/PDF 图件
07_paper/             论文素材；latex/ 为当前正式论文源
08_delivery/          历史交付/格式转换产物，仅保留追溯
08_submission/        当前正式提交与自动打包目录
09_project_log/       决策、实验、迁移和变更记录
scripts/              全流程、审计、LaTeX、打包脚本
src/                  公共工具函数
```

## 原始附件

二进制官方附件通常不提交到公开仓库。本地运行时放到：

```text
00_problem/attachments/
├── 附件1.xlsx
├── 附件2.xlsx
├── 附件3.xlsx
├── 附件4.xlsx
└── result_template.xlsx   # 也接受本地名 result.xlsx
```

输入契约位于 `00_problem/input_manifest.json`，包含 SHA256、字节数、sheet、行数和字段。正式计算前运行：

```bash
python scripts/audit_inputs.py
```

## 环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

论文编译还需要 TeX Live / MiKTeX 的 XeLaTeX；若安装 `latexmk`，构建脚本会优先使用 `latexmk -xelatex`。

## 一键正式计算

```bash
python scripts/run_formal_pipeline.py
```

该脚本依次：

```text
输入审计
  → Q1
  → Q2
  → Q3
  → Q4
  → Q2/Q3/Q4 正式图
  → Q4 独立验证
  → 全结果审计
```

它不依赖参考包中缺失的 `DATA_FACTS.json` / `DATA_PROFILE.json` 等隐藏工作区文件。

## LaTeX 与图表自动化

当前唯一正式论文源：

```text
07_paper/latex/main.tex
```

核心数值、表格和图引用从正式结果自动生成：

```bash
python scripts/generate_latex_assets.py
python scripts/build_paper.py
```

生成：

```text
07_paper/latex/generated/result_macros.tex
07_paper/latex/generated/table_*.tex
07_paper/latex/generated/figures.tex
08_submission/B题-多源融合机器人定位及任务优化.pdf
```

Q1--Q4 图件直接引用 `06_figures/q*/` 中模型脚本生成的 PDF，不在论文阶段重新绘制。

## 机器审计

```bash
python scripts/audit_results.py
```

审计内容包括：

- Q1--Q3 10 Hz 轨迹有限性、时间递增和步长；
- 统一时间偏差转换；
- 正式图件 PDF 完整性；
- Q4 是否仍残留旧 9 项容量模型；
- Q4 MILP gap、覆盖/拍照基线比较；
- `result.xlsx` 是否写入全部任务并保护红色说明区。

任何关键项失败都会阻止后续论文编译和打包。

## 最终提交打包

```bash
python scripts/package_submission.py
```

输出：

```text
08_submission/AFMU-2026-B-submission.zip
```

包内包含论文、`result.xlsx`、正式代码、LaTeX 源码、关键结果、审计报告、输入契约和 SHA256 文件清单。若赛事要求同时提交官方附件：

```bash
python scripts/package_submission.py --include-inputs
```

## 当前分支状态

`agent/reference-submission-solution` 已完成 Q4 模型结构更正与 LaTeX/图表/审计/打包能力迁移。

**注意：**仓库当前已提交的 `05_results/q4` 数字文件仍来自旧的 9 项模型运行，因此已标记为 stale。新版审计会拒绝旧结果；必须使用官方附件和当前 Q3 正式轨迹重跑 Q4 后，才能生成新的正式论文和提交 ZIP。
