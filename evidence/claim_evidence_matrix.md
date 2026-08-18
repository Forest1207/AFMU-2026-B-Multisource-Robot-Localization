# 主张—证据矩阵

本表只登记可以由仓库内正式产物、复算日志或构建报告直接支持的主张。未列入本表的表述不得作为最终论文的确定性结论。

| 编号 | 论文主张 | 直接证据 | 复核方式与边界 |
|---|---|---|---|
| C-Q1-01 | 方式 2 时间戳按 `t_{2,aligned}=t_2+\Delta t` 校正，估计 `\Delta t=-198.4317 s`。 | `05_results/q1/parameters.json`、`05_results/q1/objective_scan.csv` | `evidence/revalidation_q1.txt` 的独立同坐标匹配得到同一偏差；负号表示时间轴前移。 |
| C-Q1-02 | 问题一输出 221.0–1070.4 s 的 8495 个 10 Hz 轨迹点，全部有限且时间严格递增。 | `05_results/q1/trajectory_10hz.csv` | `parameters.json.validation` 全部通过；不在单传感器支撑域外外推。 |
| C-Q1-03 | 四种插值中 Cubic Spline 的留一重建 RMSE 最低，为 `8.51e-11 m`。 | `05_results/q1/interpolation_comparison.csv`、`06_figures/paper/model_comparison.*` | 比较的是当前数据内部重建误差，不等同于绝对定位误差。 |
| C-Q2-01 | 问题二相对时间偏差约 `50.17 s`，方式 2 相对方式 1 的二维系统偏差约 `(3.467,-1.833) m`。 | `05_results/q2/parameters.json` | 标准逐轴 Huber 目标、固定公共网格及方法敏感性均经 `evidence/gates/P1_q2.md` 独立复核。 |
| C-Q2-02 | 异步 KF/RTS 仅使用原始 4 Hz/5 Hz 事件更新，并输出 8496 个 10 Hz 融合轨迹点。 | `05_results/q2/trajectory_10hz.csv`、`05_results/q2/innovations.csv` | `evidence/revalidation_q2.txt` 中有限性、步长、NIS、白化创新与图件门禁全通过。 |
| C-Q3-01 | 问题三未拒绝“无系统偏差”假设：HAC-Wald `p=0.3511`，工程效应指数 `0.0681<0.25`，两轴块自助置信区间均含 0。 | `05_results/q3/parameters.json`、`06_figures/q3/bias_confidence_interval.*` | 结论是“未发现显著偏差”，不是证明偏差严格为零；区间推断条件于固定配准。 |
| C-Q3-02 | 方式 2 设备时钟相对参考时钟落后约 367.88 s；映射时其时间戳增加 367.88 s。 | `05_results/q3/parameters.json` | 由 `t_{2,corrected}=t_2-time_offset` 且 `time_offset=-367.877619 s` 直接推出。 |
| C-Q3-03 | 问题三输出 3691 个 10 Hz 状态点，滤波、平滑和输出协方差最小特征值均为正。 | `05_results/q3/trajectory_10hz.csv`、`05_results/q3/parameters.json` | `evidence/revalidation_q3.txt` 全通过；非事件时刻是不超过 0.208 s 的短时模型传播近似。 |
| C-Q4-01 | 在结果模板最多 9 行的交付口径下，三阶段 MILP 完成 9 项任务，三阶段求解间隙均为 0。 | `05_results/q4/parameters.json`、`05_results/q4/optimized_schedule.csv` | 独立 MILP 上界证明及复核见 `evidence/gates/P1_q4.md`；最优性限定于明确的候选与建模约定。 |
| C-Q4-02 | 最终日程包含 4 次射击、5 次拍照；最小归一化安全裕度 `0.4241`，高于贪心基线 `0.1010`。 | `05_results/q4/engineering_margins.json`、`06_figures/q4/constraint_margins.*` | `evidence/revalidation_q4.txt` 在 0.001 s 加密网格上复核全部题设约束。 |
| C-Q4-03 | moderate、standard、severe 三种扰动情景各 500 次；整套日程可行率均不低于 95%。 | `05_results/q4/parameters.json` | 扰动尺度与评价口径在论文中显式披露，不外推为任意现实噪声下的保证。 |
| C-PAPER-01 | 正式 PDF 共29页，其中正文含参考文献27页、附录2页；含40个编号公式、19幅图、5张表和8条参考文献。全文只有一个第五章，5.1至5.5连续。 | `evidence/latex_validation.json` | XeLaTeX安全构建零警告，字体嵌入、交叉引用、匿名性、页数和图像分辨率均通过。 |
| C-PAPER-02 | 摘要页、问题重述、统一第五章、九项结果表、参考文献和附录均无裁切、遮挡、乱码或空白页。 | `evidence/pdf_visual_qa.md` | 29页逐页视觉检查；渲染图为临时QA中间件，不纳入提交包。 |
