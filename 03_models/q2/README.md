# Q2：时间对齐、系统偏差估计与多源轨迹融合

本目录实现问题 2 的完整计算流程：

```text
Excel 两类定位数据
  -> 数据清洗
  -> 速度模长互相关粗时间对齐
  -> PCHIP/样条连续化
  -> Δt + (bx, by) 联合最小二乘估计
  -> Huber/IRLS 稳健加权
  -> 系统偏差校正
  -> 噪声方差估计
  -> 逆方差加权融合
  -> 10 Hz 统一轨迹输出
```

## 文件结构

- `data_loader.py`：可配置 Excel 数据读取与字段校验
- `preprocess.py`：排序、去重、缺失处理、速度突变异常点检测
- `coarse_alignment.py`：基于速度模长互相关的粗时间对齐
- `bias_estimation.py`：固定二维系统偏差解析估计、Huber 权重
- `joint_alignment.py`：一维搜索 Δt，并对每个候选 Δt 解析求解 `(bx, by)`
- `sensor_fusion.py`：噪声方差估计与逆方差加权融合
- `run_q2.py`：问题 2 完整命令行入口
- `test_synthetic.py`：合成数据恢复测试

## 参数符号约定

时间偏差采用如下约定：

```python
stream2_aligned(t) = stream2(t + dt)
```

因此 `dt > 0` 表示：为了与方式 1 的时刻 `t` 对齐，需要在方式 2 的时间轴上查询更晚的时刻 `t + dt`。

固定空间偏差定义为：

```text
bias = stream2 - stream1
```

校正方式 2 时使用：

```python
stream2_corrected = stream2_aligned - bias
```

## 联合估计模型

对每个候选时间偏差 `dt`，先在两类轨迹公共时间区间上进行 10 Hz 采样，然后解析估计固定系统偏差：

\[
\hat{\mathbf b}(\Delta t)
=\frac{1}{N}\sum_{k=1}^{N}
\left[\mathbf p_2(t_k+\Delta t)-\mathbf p_1(t_k)\right].
\]

代回得到一维目标函数：

\[
J(\Delta t)
=\frac{1}{N}\sum_k
\left\|
\mathbf p_1(t_k)-\mathbf p_2(t_k+\Delta t)+\hat{\mathbf b}(\Delta t)
\right\|_2^2.
\]

`joint_alignment.py` 使用有界一维优化寻找最优 `dt`。默认执行两次 Huber-IRLS 更新，以减弱离群点对偏差估计的影响。

## 运行方式

假设问题 2 数据位于：

```text
data/raw/附件2.xlsx
```

且两个工作表名称已知，可运行：

```bash
cd 03_models/q2
python run_q2.py ../../data/raw/附件2.xlsx \
  --sheet1 "方式1" \
  --sheet2 "方式2" \
  --output ../../05_results/q2_fused_10hz.csv
```

如果 Excel 字段名称不是默认的：

```text
时间(s)
X坐标(m)
Y坐标(m)
```

可额外传入：

```bash
--time-col "实际时间列名" \
--x-col "实际X列名" \
--y-col "实际Y列名"
```

## 输出

程序控制台输出：

- `coarse_dt`：互相关粗时间偏差
- `dt`：联合最小二乘精估计时间偏差
- `bias_x`, `bias_y`：二维固定相对系统偏差
- `rmse`：校正后两轨迹的重叠区 RMSE
- 两类设备的估计方差与融合权重

CSV 输出字段：

```text
time_s
x_stream1
y_stream1
x_stream2_corrected
y_stream2_corrected
x_fused
y_fused
```

其中 `x_fused, y_fused` 即题目要求的 10 Hz 融合位置轨迹。

## 已知传感器方差时

若题目明确给出两套定位设备在 x/y 方向上的误差方差，应优先使用题目参数，而不是根据两传感器差值反推。

`run_pipeline()` 支持：

```python
known_var1=(var1_x, var1_y)
known_var2=(var2_x, var2_y)
```

若未提供已知方差，目前代码采用对称近似：

\[
R_1=R_2\approx\frac{1}{2}\operatorname{Var}(z_1-z_2^c).
\]

需要注意：在没有外部真值或传感器精度先验时，单凭两条轨迹只能识别噪声方差之和，无法唯一拆分两个设备各自的方差。该近似仅作为默认实现。

## 合成数据测试

运行：

```bash
cd 03_models/q2
python test_synthetic.py
```

测试人为设置：

- 时间偏差 `dt = 0.37 s`
- 固定系统偏差 `b = (0.85, -0.42) m`
- 两套不同强度的高斯定位噪声

程序检查联合估计是否能在合理误差范围内恢复真实参数，并检查逆方差权重计算是否正确。

## 与问题 1 的关系

问题 1：

```text
连续轨迹 + 时间对齐
```

问题 2：

```text
连续轨迹
+ 时间对齐
+ 固定空间偏差辨识
+ 随机误差抑制
+ 多源融合
```

粗时间偏差可以直接使用问题 1 的估计作为 `joint_alignment.py` 的搜索中心；当前目录也提供独立的 `coarse_alignment.py`，便于 Q2 单独运行。
