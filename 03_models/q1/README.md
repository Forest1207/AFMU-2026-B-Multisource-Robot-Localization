# Q1 Model — 时间对齐与 10 Hz 轨迹重建

本目录把问题一的完整建模流程拆成可独立检查的程序步骤。

## 文件对应建模步骤

| 文件 | 作用 |
|---|---|
| `data_loader.py` | 读取并校验附件 1 的两类原始采样数据 |
| `interpolation_models.py` | Linear / Cubic Spline / PCHIP / Akima 连续轨迹 |
| `cross_correlation.py` | 异频数据统一网格后做互相关粗对齐，输出多个候选峰 |
| `time_alignment.py` | 构造位置 MSE 目标函数，粗网格搜索 + 有界连续优化 |
| `interpolation_10hz.py` | 修正方式 2 时间轴、合并无噪声采样点、重建 10 Hz 轨迹 |
| `diagnostics.py` | 输出目标函数曲线、轨迹图和对齐残差图 |
| `run_q1.py` | 一键执行整个问题一流程 |
| `test_synthetic.py` | 已知时间偏差的合成数据恢复测试 |

## 附件 1 数据结构

程序按题目附件的实际结构读取：

- Sheet `方式1(4Hz)`：`时间(s)`, `X坐标(m)`, `Y坐标(m)`
- Sheet `方式2(5Hz)`：`时间(s)`, `X坐标(m)`, `Y坐标(m)`

并检查两种方式的采样间隔是否分别为 `0.25 s` 与 `0.20 s`。

## 时间偏差符号约定

统一采用：

```math
t_{2,\mathrm{aligned}} = t_2 + \Delta t.
```

因此：

- `Δt > 0`：方式 2 的时间轴需要向后平移；
- `Δt < 0`：方式 2 的时间轴需要向前平移。

位置对齐目标函数为：

```math
J(\Delta t)
=
\frac{1}{N(\Delta t)}
\sum_{t_k\in\Omega(\Delta t)}
\left\|
\mathbf r_1(t_k)-\mathbf r_2(t_k-\Delta t)
\right\|_2^2.
```

## 为什么互相关只做粗估

机器人轨迹可能出现重复形状或近似周期运动，因此最大互相关峰不一定是真实时间偏差。代码保留多个互相关局部峰，再用位置域 MSE 重新排序；同时执行一次全局粗网格扫描作为安全网。最终结果由连续的 MSE 最小化确定，而不是由互相关峰直接决定。

这避免了“相关性最高但空间位置并未真正重合”的伪对齐。

## 一键运行

在仓库根目录执行：

```bash
python 03_models/q1/run_q1.py \
  --input 00_problem/attachments/附件1.xlsx \
  --output-dir 05_results/q1 \
  --method cubic \
  --compare-interpolators
```

默认正式模型为 `Cubic Spline`。

## 输出

运行后 `05_results/q1/` 包含：

- `parameters.json`：时间偏差、RMSE、搜索范围、互相关候选峰等；
- `trajectory_10hz.csv`：最终 10 Hz 位置轨迹；
- `objective_scan.csv`：粗网格目标函数；
- `interpolation_comparison.csv`：可选的插值模型比较；
- `summary.md`：可直接用于论文结果整理的摘要；
- `objective_scan.png`：`J(Δt)` 曲线；
- `aligned_trajectory.png`：两类数据空间轨迹；
- `alignment_residuals.png`：最优对齐后的 x/y 残差。

## 建议的科学性检查

1. `Δt*` 不应落在可行搜索边界；
2. `J(Δt)` 在 `Δt*` 附近应存在清晰极小值；
3. 公共区间必须足够长；
4. 问题一无噪声，因此最优对齐 RMSE 应接近数值误差；
5. 若互相关第一峰与 MSE 最优点不一致，以位置 MSE 为主，并在论文中解释轨迹重复性造成的伪相关峰；
6. 合并后若出现异常的大时间空洞，程序会拒绝跨空洞插值。

## 合成测试

```bash
python 03_models/q1/test_synthetic.py
```

用于验证已知 `Δt` 能否被算法恢复。
