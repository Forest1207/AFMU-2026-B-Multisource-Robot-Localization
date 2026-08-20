# 当前正式提交目录

`08_submission/` 是当前分支的正式交付目录；`08_delivery/` 保留历史论文和历史格式转换产物，不作为本分支最终提交源。

## 推荐流程

```bash
# 1. 核验官方附件
python scripts/audit_inputs.py

# 2. 从官方附件重跑 Q1--Q4、图件与 Q4 验证
python scripts/run_formal_pipeline.py

# 3. 审计结果链
python scripts/audit_results.py

# 4. 生成自动 TeX 表格/宏并编译论文
python scripts/build_paper.py

# 5. 生成最终提交包
python scripts/package_submission.py
```

如赛事要求将官方附件也放入代码包：

```bash
python scripts/package_submission.py --include-inputs
```

## 生成内容

```text
08_submission/
├── B题-多源融合机器人定位及任务优化.pdf
├── paper_build.json
├── audit/
│   ├── audit_report.json
│   └── audit_report.md
├── package/
│   ├── B题-多源融合机器人定位及任务优化.pdf
│   ├── result.xlsx
│   ├── audit/
│   ├── reproducible_source/
│   │   ├── requirements.txt
│   │   ├── README.md
│   │   ├── 00_problem/
│   │   ├── 01_ideas/
│   │   ├── 03_models/
│   │   ├── 05_results/
│   │   ├── 06_figures/
│   │   ├── 07_paper/latex/
│   │   └── scripts/
│   ├── README.md
│   └── DELIVERABLES.json
├── AFMU-2026-B-submission.zip
└── package_build.json
```

`reproducible_source/` 保持原仓库相对路径，所以论文图引用、审计脚本和正式流水线无需为 ZIP 单独改路径。若不使用 `--include-inputs`，其中的 `00_problem/attachments/` 只放置说明文件；使用者补入官方附件后即可执行输入审计和完整重算。

ZIP 构建完成后会再次执行：

- CRC 检查；
- ZIP 成员集合与 staging 目录逐项比较；
- ZIP 自身 SHA256 记录。

## Q4 提交口径

正式 `result.xlsx`：

- 不把模板初始 9 行解释为任务上限；
- 当前正式结果共有 **52 条**任务记录，A:E 已自动向下扩展；
- H:L 红色说明/范例保持原样；
- 拍照候选使用 5° 方位角箱；
- MILP 不加入题面未给出的跨任务准备时间互斥；
- MILP 后对每个入选任务执行 ±0.1 s 连续时间精修；
- 所有最终任务时刻通过 0.01 s 完整准备窗口复核；
- 同一拍照目标的所有入选照片满足至少 60° 方位角分离。

当前正式 Q4：覆盖 34 个目标，16 次射击、36 次拍照，共 52 条记录；三阶段 MILP gap 均为 0。`05_results/q4/validation.json` 中所有检查项均已通过。

## 当前状态

新版 Q4 已在官方附件和当前 Q3 正式轨迹上重算完成；Q4 独立验证、跨问题结果审计以及 LaTeX 资产生成检查均已在 GitHub Actions 中返回 PASS。

因此 `05_results/q4/result.xlsx`、`optimized_schedule.csv`、`parameters.json`、`summary.md`、`validation.json` 和 `06_figures/q4/` 已是当前正式 Q4 产物，可进入论文编译与最终打包流程。
