# Experiment Log

记录每次正式实验的输入、参数、输出和结论。

## 2026-08-19 — Q1 正式运行

- 输入：`附件1.xlsx`，SHA-256 `eb9dbdefb6d566b7d4396d7d0ad09e816afb43146ae7ad5e13882a745a9ba577`。
- 命令：`python 03_models/q1/run_q1.py --input 00_problem/attachments/附件1.xlsx --output-dir 05_results/q1 --figure-dir 06_figures/q1 --method cubic --compare-interpolators`。
- 环境：Python 3.12，NumPy 2.5.2，Pandas 3.0.5，SciPy 1.18.0，Matplotlib 3.11.1。
- 结果：`Δt=-198.4316999986 s`，报告值 `-198.4317 s`；公共区间 RMSE `8.514815e-11 m`；输出 8495 行，区间 `[221.0,1070.4] s`。
- 独立一致性：700 组共同采样时刻的最大坐标差为 0。
- 插值对比：Cubic Spline 的 RMSE 最低；Linear、PCHIP、Akima 均得到相同四位小数偏差。
- 敏感性：8 个预设情景的原始偏差极差 `3.558e-09 s`，报告值不变。
- 图审计：4 张 PNG 均约 300 DPI，配套可编辑 SVG 与 PDF，严格审计通过。
