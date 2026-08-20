# 问题四结果状态：需要按新版正式模型重算

> **STALE / DO NOT CITE**
>
> 本目录当前已提交的 `parameters.json`、`optimized_schedule.csv`、`result.xlsx` 与部分图件来自旧版 Q4 模型。旧版错误地把 `result.xlsx` 的 9 个初始空白行解释为任务容量，并加入了题面未给出的跨任务准备时间互斥约束。因此旧的“4 次射击 + 5 次拍照 = 9 项”结果不再作为正式结论，论文生成和提交审计会主动拒绝该旧 schema。

## 新版正式模型

新版 `03_models/q4/` 已改为：

1. **不设置 9 项容量约束**；
2. **不设置跨任务准备时间互斥**；
3. 一级最大化 `(任务类型, 目标编号)` 覆盖数；
4. 固定一级最优值后最大化满足 60° 角差的有效拍照数；
5. 固定前两级最优值后最大化总归一化安全裕度；
6. 射击同一目标至多选择一次；
7. 10 Hz 初筛后的候选仍在 0.01 s 网格对完整准备窗口连续复核；
8. `result.xlsx` 的 A:E 区域允许向下扩展，原表头及 H:L 红色说明/范例保持不变。

该结构吸收参考提交包问题四的正确 MILP 思路，同时保留本仓库更严格的连续窗口验证。

## 参考包基准（仅用于算法对照）

参考提交包在其自身问题三轨迹上得到：

- 覆盖目标：27；
- 射击：13 次；
- 拍照：23 次；
- 任务记录：36 条；
- 逐目标贪心基线：覆盖 27 个目标、13 次射击、14 次拍照。

这些数字**不是本仓库新版 Q4 的正式结果**，因为本仓库问题三融合轨迹与参考包不同。

## 如何生成新版正式结果

将官方附件放入 `00_problem/attachments/` 后，在仓库根目录运行：

```bash
python scripts/run_formal_pipeline.py --skip-q1 --skip-q2 --skip-q3
```

或只运行 Q4：

```bash
python 03_models/q4/run_q4.py \
  --trajectory 05_results/q3/trajectory_10hz.csv \
  --targets 00_problem/attachments/附件4.xlsx \
  --template 00_problem/attachments/result_template.xlsx \
  --results 05_results/q4

python 03_models/q4/make_figures.py \
  --trajectory 05_results/q3/trajectory_10hz.csv \
  --targets 00_problem/attachments/附件4.xlsx \
  --results 05_results/q4 \
  --figures 06_figures/q4

python 03_models/q4/validation.py \
  --trajectory 05_results/q3/trajectory_10hz.csv \
  --targets 00_problem/attachments/附件4.xlsx \
  --template 00_problem/attachments/result_template.xlsx \
  --results 05_results/q4 \
  --figures 06_figures/q4 \
  --output 05_results/q4/validation.json
```

只有新版 `parameters.json` 包含 `coverage_count`、`greedy_coverage_count`，且 `milp.artificial_capacity = null`、`milp.cross_task_time_mutex = false` 后，`scripts/audit_results.py` 才会放行 LaTeX 编译与提交打包。
