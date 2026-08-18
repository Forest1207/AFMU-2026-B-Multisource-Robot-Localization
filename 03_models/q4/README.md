# Q4 固定轨迹射击—拍照任务优化

本目录实现问题四的完整计算链：

```text
Q3 融合轨迹
  -> 10 Hz 平滑状态重构
  -> 目标距离/方位角
  -> 1.5 s / 0.5 s 滑动窗口
  -> 候选任务压缩
  -> 拍照角度冲突图
  -> 三阶段字典序 BILP/MILP
  -> 可选连续时间精修
  -> Excel 结果
```

## 模块

| 文件 | 功能 |
|---|---|
| `trajectory_state.py` | 平滑样条、10 Hz 重采样、速度/加速度重构 |
| `target_geometry.py` | 目标读取、距离、圆周方位角计算 |
| `feasible_windows.py` | 射击/拍照基础条件和连续滑动时间窗 |
| `candidate_generator.py` | 通用候选结构、安全裕度和连续区间压缩 |
| `shooting_model.py` | 射击候选生成、85% 命中概率函数 |
| `photography_model.py` | 拍照候选生成和方位角分箱压缩 |
| `conflict_builder.py` | `<60°` 拍照冲突和可选资源占用冲突 |
| `scheduler.py` | SciPy `milp` 三阶段字典序 0-1 优化 |
| `local_refinement.py` | 10 Hz 离散解附近的 0.01 s 局部精修 |
| `q4_main.py` | 命令行统一入口与 Excel 输出 |
| `test_synthetic.py` | 无真实附件时可运行的合成烟雾测试 |
| `requirements.txt` | Q4 最小依赖 |

## 优化目标

按字典序依次求解：

1. 最大化完成的 `(任务类型, 目标)` 数；
2. 在目标覆盖数最优的前提下最大化有效拍照次数；
3. 在前两项不下降的前提下最大化任务安全裕度。

拍照候选之间若同一目标的圆周方向角差小于 60°，加入

```text
x_i + x_j <= 1
```

作为线性冲突约束。

## 题设与扩展假设

默认模型**不**假设 1.5 s / 0.5 s 准备窗口是排他的设备资源，因为这一点需要最终题意支持。

如果确认机器人在准备某一任务时不能并行准备另一任务，可启用：

```bash
--exclusive-resource
```

此时准备时间窗重叠的候选任务会增加互斥约束。

对于拍照的“提前 0.5 s”，默认按该 0.5 s 内距离、速度、加速度均满足限制处理。如果最终确认 0.5 s 仅表示相机提前转向，可启用：

```bash
--photo-orientation-only
```

## 安装

```bash
cd 03_models/q4
pip install -r requirements.txt
```

## 合成测试

```bash
python test_synthetic.py
```

测试覆盖：

- 匀速轨迹的一阶/二阶导数；
- 滑动时间窗；
- 359°/1° 圆周角差；
- 拍照角度冲突；
- MILP 目标覆盖、拍照数量和射击单选。

## 运行真实数据

若附件 4 的射击/拍照目标在同一个 sheet，并带有 `任务类型` 列：

```bash
python q4_main.py \
  --trajectory ../../05_results/q3_fused_trajectory.xlsx \
  --targets ../../00_problem/attachments/附件4.xlsx \
  --output ../../05_results/q4_result.xlsx
```

默认表头：

```text
轨迹：时间(s), X坐标(m), Y坐标(m)
目标：目标编号, X坐标(m), Y坐标(m), 任务类型
```

如果附件实际表头不同，直接通过参数覆盖：

```bash
python q4_main.py \
  --trajectory path/to/q3.xlsx \
  --targets path/to/附件4.xlsx \
  --time-col 时间 \
  --x-col X \
  --y-col Y \
  --target-id-col 编号 \
  --target-x-col X \
  --target-y-col Y \
  --target-type-col 类型
```

若射击、拍照分别位于不同 sheet，可用：

```bash
--shoot-sheet 射击目标 --photo-sheet 拍照目标
```

这时两个 sheet 不需要 `任务类型` 列。

## 连续时间精修

MILP 主求解仍在题目要求的 10 Hz 网格上进行。若希望在离散最优点附近进一步提高安全裕度：

```bash
--refine --refine-radius 0.1 --refine-step 0.01
```

精修结果只有在仍满足拍照 60° 硬约束时才会被接受。

## 输出

默认输出：

```text
05_results/q4_result.xlsx
```

包含：

- `任务结果`：任务类型、目标编号、时刻、距离、速度、加速度、方位角、安全裕度、准备窗口；
- `汇总`：目标覆盖数、射击次数、有效拍照次数、按单次 85% 命中率计算的期望命中数、安全裕度总和。

> 当前仓库未存放竞赛附件原始 Excel，因此这里完成的是可运行的算法实现和合成测试框架。得到 Q3 最终轨迹与附件 4 的真实列名后，可直接通过命令行参数接入，不需要改动核心模型代码。
