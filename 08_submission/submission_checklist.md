# Submission Checklist

## A. 正式数值与模型

- [ ] Q1--Q3 时间偏差在论文层统一采用 `t2_aligned = t2 + delta` 口径。
- [ ] `05_results/q1/parameters.json`、`q2/parameters.json`、`q3/parameters.json` 与 `05_results/reporting_conventions.json` 转换一致。
- [ ] Q4 已使用新版**无 9 项容量、无跨任务准备时间互斥**模型重新计算。
- [ ] Q4 `parameters.json` 含 `coverage_count` 与 `greedy_coverage_count`。
- [ ] Q4 `milp.artificial_capacity` 为 `null`。
- [ ] Q4 `milp.cross_task_time_mutex` 为 `false`。
- [ ] 同一射击目标至多一次；同一拍照目标任意两张照片方位角差至少 60°。
- [ ] 所有最终 Q4 两位小数任务时刻均通过 0.01 s 完整准备窗口复核。

## B. 原始数据与可复现性

- [ ] 官方附件已放入 `00_problem/attachments/`。
- [ ] `python scripts/audit_inputs.py` 返回 PASS。
- [ ] 附件 SHA256、sheet、行数和字段与 `00_problem/input_manifest.json` 一致。
- [ ] `python scripts/run_formal_pipeline.py` 从官方附件完成全流程且无异常退出。

## C. 图表与论文

- [ ] Q1--Q4 `figure_manifest.json` 中声明的正式 PDF 图件均存在。
- [ ] 图表编号、单位、坐标轴、图注完整。
- [ ] `python scripts/generate_latex_assets.py` 成功，论文中的核心数值均由 `05_results` 自动注入。
- [ ] 当前正式论文源为 `07_paper/latex/main.tex`，不再以历史 `07_paper/final_paper.md` 或 `08_delivery/` 为提交源。
- [ ] `python scripts/build_paper.py` 成功生成 `08_submission/B题-多源融合机器人定位及任务优化.pdf`。
- [ ] 论文包含摘要、问题重述、模型假设、符号说明、模型建立与求解、检验与结果分析、评价与改进。

## D. 机器审计

- [ ] `python scripts/audit_results.py` 返回 PASS。
- [ ] Q1--Q3 10 Hz 轨迹严格递增、有限且时间步长正确。
- [ ] Q4 三阶段 MILP gap 均为 0（或求解器明确给出精确最优状态）。
- [ ] Q4 Excel 中所有优化任务均已写入，任务数超过模板初始 9 行时 A:E 已正确向下扩展。
- [ ] `result.xlsx` 表头与 H:L 红色说明/范例未被修改。
- [ ] `08_submission/audit/audit_report.json` 与 `.md` 均为 PASS。

## E. 最终打包

- [ ] `python scripts/package_submission.py` 成功。
- [ ] `08_submission/AFMU-2026-B-submission.zip` 已生成。
- [ ] ZIP 内含论文 PDF、`result.xlsx`、正式代码、LaTeX 源码、关键结果、审计报告和复现清单。
- [ ] `DELIVERABLES.json` 包含每个交付文件的 SHA256 与大小。
- [ ] 若赛事要求提交原始附件，使用 `--include-inputs` 重新打包；否则不在提交 ZIP 中重复分发官方附件。
- [ ] 最终按赛事规则将文件名替换为“题号 + 队号 + 队长姓名”等要求的命名。
