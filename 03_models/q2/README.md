# 问题二：稳健时空标定与异步状态融合

本目录实现问题二的可复现主链：

```text
4 Hz / 5 Hz 原始观测
  → 偏差不敏感运动特征粗配准
  → 固定公共评价网格上的 Huber 剖面估计 (Δt, bx, by)
  → 方式2空间偏差校正
  → 原始异步事件上的常加速度 Kalman 滤波
  → 99% NIS 门控稳健降权
  → RTS 固定区间平滑
  → 10 Hz 位置、速度和加速度输出
```

## 符号

- 时间偏差：方式 2 的设备时刻映射到方式 1 参考时钟为
  `t2_corrected = t2 - Δt`；因此方式 1 时刻 `t` 对应方式 2 查询时刻 `t+Δt`。
- 相对空间偏差：`b = z2 - z1`；校正方式 2 使用 `z2_corrected = z2 - b`。
- 所有空间偏差均为两设备之间的**相对偏差**，没有外部真值时不解释为任一设备的绝对误差。

## 关键实现

- `joint_alignment.py`：先在全搜索区间构造共同有效的固定评价网格，再对每个候选时间偏差解析估计二维常偏差，避免候选偏差改变样本集合而移动目标函数。
- `sensor_fusion.py`：利用常加速度局部模型的三阶差分恒等式，分别估计两设备测量协方差；不再把差值方差任意对半拆分。
- `../q3/robust_fusion.py`：在校正后的原始 4 Hz / 5 Hz 事件时刻执行异步 KF 和 RTS；10 Hz 仅为平滑状态重采样，不制造插值伪观测。
- `run_q2.py`：完整主入口；调参阶段关闭协方差膨胀，以“二维门控前 NIS 均值接近 2 + Cholesky 白化创新一阶自相关接近 0”的评分选择白噪声 jerk 强度，选定后再运行稳健门控。
- `test_synthetic.py`：回收已知时间/空间偏差并验证融合 RMSE、有限性和 10 Hz 步长。
- `run_sensitivity.py`：比较插值、IRLS 次数、搜索区间、过程噪声和门控概率。
- `make_figures.py`：生成 PNG/SVG/PDF 三格式正式图及来源清单。

## 正式运行

从本目录运行：

```powershell
..\..\.venv\Scripts\python.exe run_q2.py `
  "D:\MathModeling\School modeling\2026赛题\2026_B题\附件2.xlsx" `
  --sheet1 "方式1(4Hz)" --sheet2 "方式2(5Hz)" `
  --output ..\..\05_results\q2\trajectory_10hz.csv `
  --summary ..\..\05_results\q2\parameters.json `
  --innovations ..\..\05_results\q2\innovations.csv `
  --tuning ..\..\05_results\q2\process_noise_tuning.csv
```

正式输出见 `05_results/q2`，图件见 `06_figures/q2`。最终报告值、精度和验证边界以 `parameters.json`、`sensitivity.csv` 和论文小节为准。
