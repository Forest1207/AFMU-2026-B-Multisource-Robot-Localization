# 正式 LaTeX 论文流水线

本目录是 `agent/reference-submission-solution` 分支当前的**唯一正式论文源**。

历史目录中的 `07_paper/final_paper.md`、`08_delivery/` 仍保留用于追溯，但不再作为当前提交版本的 source of truth。

## 设计原则

论文不手工维护核心数值，而是从 `05_results/` 自动生成：

```text
05_results/q1..q4/parameters.json
05_results/reporting_conventions.json
05_results/q4/optimized_schedule.csv
05_results/q1..q4/figure_manifest.json
        ↓
scripts/generate_latex_assets.py
        ↓
07_paper/latex/generated/
  result_macros.tex
  table_*.tex
  figures.tex
        ↓
main.tex
        ↓
XeLaTeX / latexmk
        ↓
08_submission/B题-多源融合机器人定位及任务优化.pdf
```

这样能避免模型结果更新后论文仍保留旧数字。

## Q4 特别门禁

由于仓库历史上存在错误的“模板初始 9 行 = 最多 9 项任务”解释，LaTeX 资产生成器会检查 Q4 `parameters.json` 的 schema：

- 必须存在 `coverage_count`；
- 必须存在 `greedy_coverage_count`；
- `milp.artificial_capacity` 必须为 `null`；
- `milp.cross_task_time_mutex` 必须为 `false`。

若仍是旧版 9 项结果，论文构建会直接失败，防止把旧结论打进最终 PDF。

## 构建

先用官方附件完成正式求解：

```bash
python scripts/run_formal_pipeline.py
```

再编译论文：

```bash
python scripts/build_paper.py
```

脚本优先使用：

```text
latexmk -xelatex
```

若不存在 `latexmk`，则使用 `xelatex` 连续编译两次。

## 图件

Q1--Q4 的正式图均由模型目录中的 `make_figures.py` 生成，并至少保存：

- PNG：快速浏览；
- SVG：后期编辑；
- PDF：LaTeX 正式排版。

`generate_latex_assets.py` 只引用 `06_figures/q*/` 中的正式 PDF，不复制或重新绘制图像。

## 审计

论文编译默认先执行：

```bash
python scripts/audit_results.py
```

只有结果、统一符号、Q4 schema 和正式图件均通过机器审计时才允许继续编译。
