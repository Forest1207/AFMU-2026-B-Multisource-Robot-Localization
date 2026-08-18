# Q1 Time Alignment

## 1. 问题理解

问题一可理解为：机器人存在一条连续、确定的真实二维轨迹，两种定位方式分别以 4 Hz 和 5 Hz 对该轨迹进行无噪声采样。由于两台设备开机时间不同，因此两组数据的时间原点存在固定偏移。

本问的核心任务不是滤波，而是：

1. 建立两组离散轨迹的连续表示；
2. 估计固定时间偏差 `Δt`；
3. 完成统一时间轴上的对齐；
4. 利用对齐后的全部无噪声采样点重建连续轨迹；
5. 以 0.1 s 间隔输出 10 Hz 位置轨迹。

## 2. 基本假设

- 两种定位方式观测同一机器人、同一条真实连续二维轨迹；
- 问题一中不存在随机测量噪声；
- 问题一中仅考虑由设备开机先后造成的固定时间偏移，不引入空间系统偏差；
- 两台设备采样频率稳定，方式 1 为 4 Hz，方式 2 为 5 Hz；
- 仅在有真实观测支撑的时间范围内进行插值，不进行无依据外推。

## 3. 连续轨迹表示

设机器人真实二维轨迹为

```math
\mathbf r(t)=\begin{bmatrix}x(t)\\y(t)\end{bmatrix}.
```

两种定位方式的离散数据分别记为

```math
D_1=\{(t_i^{(1)},x_i^{(1)},y_i^{(1)})\},
```

```math
D_2=\{(t_j^{(2)},x_j^{(2)},y_j^{(2)})\}.
```

分别对 `x(t)` 与 `y(t)` 建立一维插值函数，得到两条连续轨迹

```math
\mathbf r_1(t)=\begin{bmatrix}\hat x_1(t)\\\hat y_1(t)\end{bmatrix},
\qquad
\mathbf r_2(t)=\begin{bmatrix}\hat x_2(t)\\\hat y_2(t)\end{bmatrix}.
```

## 4. 插值模型选择

问题一数据无噪声，因此优先采用插值而非平滑拟合。可比较以下方法：

- Linear interpolation；
- Cubic Spline；
- PCHIP；
- Akima interpolation。

模型选择不只比较原始节点上的拟合误差，而主要比较时间对齐后的跨传感器一致性，例如：

```math
RMSE_m=\sqrt{\frac{1}{N}\sum_k\left\|\mathbf r_{1,m}(t_k)-\mathbf r_{2,m}(t_k-\Delta t_m^*)\right\|_2^2}.
```

同时结合曲线光滑性、局部振荡情况和后续可导性进行选择。若三次样条在对齐 RMSE 与轨迹光滑性方面表现较优，则将 Cubic Spline 作为正式模型。

## 5. 时间偏差的定义

定义两台设备的固定时间偏差为

```math
\Delta t=T_2-T_1,
```

其中 `T_1,T_2` 分别为两台设备的真实开机时刻。

若 `Δt>0`，表示方式 2 比方式 1 晚启动 `Δt` 秒。

对齐后方式 2 的时间轴写为

```math
t_{2,\mathrm{aligned}}=t_2+\Delta t.
```

## 6. 互相关粗对齐算法实现

### 6.1 算法定位

互相关不作为最终时间偏差的高精度求解器，而用于：

1. 给出时间偏差的粗初值 `Δt_0`；
2. 缩小后续最小 MSE 连续优化的搜索区间；
3. 对最终 `Δt*` 提供独立的交叉验证。

由于方式 1 为 4 Hz、方式 2 为 5 Hz，两组原始序列不能直接按数组下标做离散互相关。必须先把两组轨迹转换到一个公共评价时间网格，或者等价地利用连续插值函数在统一时刻取值。

问题一无随机噪声，因此这里的插值只用于构造互相关所需的公共评价序列，不代表已经生成最终 10 Hz 轨迹。

### 6.2 相关特征的选择

直接对原始位置 `x(t), y(t)` 做互相关容易受到轨迹整体趋势影响，因此优先使用能描述“运动节奏”的特征。

推荐优先级为：

1. 二维速度向量 `v(t)=[v_x(t),v_y(t)]^T`；
2. 位移增量向量 `Δr_k=r(t_{k+1})-r(t_k)`；
3. 速度模长 `||v(t)||`；
4. 去均值后的二维位置向量，作为辅助验证。

若采用三次样条，可直接对插值函数求导得到

```math
\mathbf v_m(t)
=
\frac{d\mathbf r_m(t)}{dt}
=
\begin{bmatrix}
\hat x'_m(t)\\
\hat y'_m(t)
\end{bmatrix},\qquad m=1,2.
```

二维速度向量比单独使用速度模长保留了更多方向变化信息，因此默认使用二维速度向量构造归一化互相关。

### 6.3 公共相关评价网格

两种原始采样周期分别为

```math
T_1=0.25\ \mathrm{s},\qquad T_2=0.20\ \mathrm{s}.
```

它们的公共细分周期为 `0.05 s`，因此粗对齐阶段可使用

```math
h_c=0.05\ \mathrm{s}
```

作为默认相关评价步长，即等效 20 Hz 公共网格。

这里选择 20 Hz 的目的只是保证两种采样节奏都能在统一网格上表达，并不意味着最终轨迹必须以 20 Hz 输出。最终输出仍按题目要求为 10 Hz。

若后续实验表明 `0.05 s` 的粗分辨率不足，可在互相关峰值附近再用更细网格复核；最终高精度时间偏差仍由第 9 节的连续 MSE 优化得到。

### 6.4 候选时间偏差与公共区间

设候选时间偏差为 `τ`。按照本文约定，方式 2 对齐后的时间为

```math
t_{2,\mathrm{aligned}}=t_2+\tau.
```

因此给定 `τ` 后，两组数据的公共有效时间区间为

```math
I(\tau)
=
\left[
\max(t_{1,\min},\ t_{2,\min}+\tau),
\min(t_{1,\max},\ t_{2,\max}+\tau)
\right].
```

记其长度为

```math
L(\tau)=|I(\tau)|.
```

只有当

```math
L(\tau)\ge L_{\min}
```

时才计算相关系数，以避免极少量重叠数据产生虚假高相关。

在 `I(τ)` 内建立公共评价时刻

```math
\mathcal T_\tau
=
\{t_0,t_0+h_c,t_0+2h_c,\ldots,t_1\}.
```

随后比较

```math
\mathbf v_1(t),\qquad \mathbf v_2(t-\tau),\qquad t\in\mathcal T_\tau.
```

### 6.5 二维归一化互相关函数

为了消除不同时间窗口内均值与尺度变化的影响，对每个候选 `τ` 分别中心化两组特征。

设

```math
\bar{\mathbf v}_1(\tau)
=
\frac{1}{N_\tau}
\sum_{t_k\in\mathcal T_\tau}
\mathbf v_1(t_k),
```

```math
\bar{\mathbf v}_2(\tau)
=
\frac{1}{N_\tau}
\sum_{t_k\in\mathcal T_\tau}
\mathbf v_2(t_k-\tau).
```

定义二维归一化互相关系数

```math
C(\tau)
=
\frac{
\sum_{t_k\in\mathcal T_\tau}
\left(\mathbf v_1(t_k)-\bar{\mathbf v}_1\right)^T
\left(\mathbf v_2(t_k-\tau)-\bar{\mathbf v}_2\right)
}{
\sqrt{
\sum_{t_k\in\mathcal T_\tau}
\left\|\mathbf v_1(t_k)-\bar{\mathbf v}_1\right\|_2^2
}
\sqrt{
\sum_{t_k\in\mathcal T_\tau}
\left\|\mathbf v_2(t_k-\tau)-\bar{\mathbf v}_2\right\|_2^2
}
}.
```

理论上有

```math
-1\le C(\tau)\le 1.
```

正确时间对齐附近应出现显著相关峰值。粗时间偏差定义为

```math
\Delta t_0
=
\arg\max_{\tau\in\mathcal D} C(\tau),
```

其中 `𝒟=[Δt_min,Δt_max]` 为预先设定的合理时间偏差范围。

### 6.6 搜索范围

若题目或数据结构能够给出设备最大可能开机时间差，则直接据此设置

```math
\mathcal D=[-T_{\max},T_{\max}].
```

若没有明确先验，则搜索范围应满足两个原则：

1. 足够覆盖可能的启动时间差；
2. 每个候选偏差仍保留足够长的公共轨迹区间。

不建议把整个观测时长都机械地作为搜索范围，因为在极端偏移处公共区间过短，相关峰值缺乏可信度。

### 6.7 峰值判定与多峰处理

不能只记录最大相关系数，还应检查相关曲线 `C(τ)` 的形状。

重点记录：

- 最大峰位置 `Δt_0`；
- 最大相关系数 `C_max`；
- 第二高局部峰 `C_2`；
- 最大峰与次峰的间隔；
- 峰值附近的宽度；
- 对应公共区间长度 `L(Δt_0)`。

若轨迹具有重复或近似周期运动，`C(τ)` 可能出现多个局部峰。此时不应直接把最高峰视为最终时间偏差，而应保留前 `K` 个候选峰：

```math
\{\tau_1,\tau_2,\ldots,\tau_K\},
```

分别送入后续位置 MSE 目标函数精细验证，最终由 `J(Δt)` 决定最优解。

因此互相关承担的是“缩小候选集合”的作用，而不是替代最终最小二乘对齐。

### 6.8 与后续 MSE 优化的衔接

若互相关曲线存在单一显著峰值 `Δt_0`，则设置精细搜索区间

```math
\mathcal D_{\mathrm{fine}}
=
[\Delta t_0-h,\ \Delta t_0+h],
```

其中 `h` 可取若干个粗搜索步长，例如

```math
h=3h_c\sim5h_c.
```

之后在该区间内求解

```math
\Delta t^*
=
\arg\min_{\Delta t\in\mathcal D_{\mathrm{fine}}}
J(\Delta t).
```

若存在多个显著相关峰，则分别围绕各峰建立局部精细区间，比较各区间内的最小位置 MSE，并选择全局最优者。

### 6.9 互相关粗对齐伪代码

```text
Input:
    D1 = {(t1_i, x1_i, y1_i)}       # 4 Hz
    D2 = {(t2_j, x2_j, y2_j)}       # 5 Hz
    search_range = [dt_min, dt_max]
    hc = 0.05 s                      # coarse correlation grid
    L_min                            # minimum valid overlap length

Step 1: construct continuous coordinate functions
    x1(t), y1(t) = interpolation(D1)
    x2(t), y2(t) = interpolation(D2)

Step 2: construct motion features
    vx1(t) = derivative(x1(t))
    vy1(t) = derivative(y1(t))
    vx2(t) = derivative(x2(t))
    vy2(t) = derivative(y2(t))

    v1(t) = [vx1(t), vy1(t)]
    v2(t) = [vx2(t), vy2(t)]

Step 3: enumerate coarse candidate offsets
    candidates = arange(dt_min, dt_max, hc)

    for tau in candidates:

        overlap_start = max(min(t1), min(t2) + tau)
        overlap_end   = min(max(t1), max(t2) + tau)

        if overlap_end - overlap_start < L_min:
            C[tau] = invalid
            continue

        T = arange(overlap_start, overlap_end, hc)

        F1 = v1(T)
        F2 = v2(T - tau)

        # zero-mean normalization
        F1 = F1 - mean(F1, axis=0)
        F2 = F2 - mean(F2, axis=0)

        numerator = sum(dot(F1[k], F2[k]))
        denominator = sqrt(sum(norm(F1[k])^2)
                           * sum(norm(F2[k])^2))

        if denominator is too small:
            C[tau] = invalid
        else:
            C[tau] = numerator / denominator

Step 4: detect correlation peaks
    peaks = local_maxima(C)
    sort peaks by correlation value

    dt0 = peak with largest valid C

Step 5: ambiguity check
    if several peaks have similar correlation:
        keep top-K candidate offsets
    else:
        keep dt0 only

Step 6: create fine-search interval(s)
    for each retained peak tau_k:
        interval_k = [tau_k - h, tau_k + h]

Output:
    coarse offset dt0
    retained candidate peaks
    fine-search interval(s)
    correlation curve C(tau)
```

### 6.10 Python 实现建议

正式代码可放入 `03_models/q1/time_alignment.py`。推荐使用：

```python
from scipy.interpolate import CubicSpline
from scipy.signal import find_peaks
import numpy as np
```

若采用 `CubicSpline`，速度特征可以直接通过样条的一阶导数获得：

```python
sx = CubicSpline(t, x)
sy = CubicSpline(t, y)

vx = sx.derivative(1)
vy = sy.derivative(1)
```

不要直接对 4 Hz 和 5 Hz 两个原始数组调用 `np.correlate` 或 `scipy.signal.correlate`，因为两者采样间隔不同，数组下标的“一个 lag”并不对应同一真实时间长度。

### 6.11 退化情形与备用特征

互相关依赖轨迹中存在足够明显的动态变化。如果机器人长时间做匀速直线运动，则速度向量可能近似常量，中心化后能量过小，导致相关系数失去辨识能力。

可按以下顺序切换备用特征：

1. 去均值二维位置向量；
2. 位移增量向量；
3. 速度模长；
4. 转向角或曲率特征；
5. 多特征联合评分。

例如可定义联合粗对齐评分

```math
S(\tau)
=
w_v C_v(\tau)+w_p C_p(\tau),
```

其中 `C_v` 为速度向量相关系数，`C_p` 为去均值位置向量相关系数，权重满足

```math
w_v+w_p=1.
```

不过问题一数据无噪声时，应优先保持模型简单；只有在单一特征发生退化时才启用联合评分。

### 6.12 互相关阶段输出与可视化

建议保存以下中间结果：

- `tau` 与 `C(tau)` 的完整序列；
- 最大相关峰 `Δt_0`；
- 前若干个局部峰；
- 各候选偏差对应的公共区间长度；
- 粗对齐前后的速度特征叠加图。

论文中至少绘制一张 `C(τ)-τ` 曲线，并标记最大相关峰。它能够直观说明时间偏差的粗估位置及其唯一性。

互相关模块最终逻辑为：

```text
两类异频原始轨迹
    ↓
建立连续插值函数
    ↓
构造速度/位移运动特征
    ↓
统一公共评价网格
    ↓
遍历候选时间偏差 τ
    ↓
计算二维归一化互相关 C(τ)
    ↓
相关峰检测与多峰判断
    ↓
得到粗偏差 Δt_0 / 候选峰集合
    ↓
缩小 MSE 连续优化搜索区间
```

## 7. 时间平移误差目标函数

对任意候选时间偏差 `Δt`，定义两条连续轨迹在公共有效时间区间上的均方位置误差：

```math
J(\Delta t)
=
\frac{1}{N(\Delta t)}
\sum_{t_k\in\Omega(\Delta t)}
\left\|
\mathbf r_1(t_k)-\mathbf r_2(t_k-\Delta t)
\right\|_2^2.
```

其中：

- `Ω(Δt)` 为两条轨迹在时间平移后的公共有效时间区间；
- `N(Δt)` 为该公共区间上的评价样本数。

最优时间偏差定义为

```math
\Delta t^*=\arg\min_{\Delta t}J(\Delta t).
```

## 8. 公共时间区间约束

由于不同 `Δt` 会改变两组数据的重叠区间，若某个候选偏差只产生极少的重叠样本，可能偶然得到较小 MSE，因此需防止伪最优解。

至少采用以下一种约束：

```math
N(\Delta t)\ge N_{\min}.
```

或者在所有候选 `Δt` 共有的固定评价区间上比较目标函数。

正式实现时建议同时记录：

- 公共时间长度；
- 公共样本数；
- 最小 MSE；
- 最优解相对边界的位置。

## 9. 数值求解策略

不建议仅使用固定步长遍历作为最终算法，因为最终精度会受网格步长限制。

建议采用两阶段求解：

### 9.1 粗网格搜索

在合理范围内对 `Δt` 做粗扫描，确定全局最优区域：

```text
for Δt in coarse_grid:
    compute J(Δt)
choose the best interval
```

### 9.2 连续精细优化

在粗搜索得到的最优区间内，采用一维标量优化，例如：

- Brent method；
- Golden-section search。

最终得到高精度估计

```math
\Delta t^*=\arg\min_{\Delta t}J(\Delta t).
```

整体求解链为：

```text
互相关粗估
    ↓
粗网格搜索
    ↓
锁定最优区间
    ↓
Brent / 黄金分割连续精细优化
    ↓
Δt*
```

## 10. 最优解有效性检验

得到 `Δt*` 后，不直接接受结果，而需进行有效性检验。

### 10.1 边界检验

最优解不应无解释地落在搜索边界：

```math
\Delta t^*\notin\{\Delta t_{\min},\Delta t_{\max}\}.
```

若落在边界，应扩展搜索区间重新计算。

### 10.2 唯一性检验

绘制 `J(Δt)` 曲线，检查 `Δt*` 附近是否存在明显、稳定的唯一极小值。

理想情况下：

```math
J(\Delta t^*)\ll J(\Delta t),\quad \Delta t\neq\Delta t^*.
```

### 10.3 重叠区间检验

确保

```math
N(\Delta t^*)\ge N_{\min},
```

避免由于重叠数据过少造成伪最优。

### 10.4 无噪声一致性检验

问题一无随机噪声，因此正确对齐后两组轨迹的位置残差应接近数值误差：

```math
RMSE(\Delta t^*)
=
\sqrt{
\frac{1}{N}
\sum_k
\left\|
\mathbf r_1(t_k)-\mathbf r_2(t_k-\Delta t^*)
\right\|_2^2
}
\approx 0.
```

## 11. 时间轴校正与数据合并

得到 `Δt*` 后，将方式 2 的时间修正为

```math
t_j^{(2,\mathrm{aligned})}=t_j^{(2)}+\Delta t^*.
```

构造统一数据集：

```math
D=D_1\cup D_2^{\mathrm{aligned}}.
```

随后：

1. 按统一时间轴排序；
2. 检查完全重复时间点；
3. 若同一真实时刻存在两种观测，验证坐标一致性；
4. 对全部对齐后的无噪声采样点重新建立连续轨迹。

## 12. 10 Hz 轨迹重建

在可靠时间区间内构造统一输出时间序列：

```math
t_k=t_{\mathrm{start}}+0.1k.
```

在最终连续轨迹上计算

```math
\hat{\mathbf r}(t_k)=
\begin{bmatrix}
\hat x(t_k)\\
\hat y(t_k)
\end{bmatrix}.
```

最终输出格式为：

```text
time, x, y
```

输出频率为 10 Hz。

## 13. 推荐完整流程

```text
问题1
  │
  ├── 无随机噪声，仅存在固定时间不同步
  │
  ↓
读取两类原始采样数据
  │
  ↓
插值模型选择实验
  │
  ↓
分别构造连续轨迹 r1(t), r2(t)
  │
  ├────────────→ 互相关粗估时间偏差 Δt_0
  │                         │
  │                         ↓
  │                 缩小时间偏差搜索区间
  │                         │
  ↓                         ↓
构造目标函数 J(Δt) ←────────┘
  │
  ↓
粗网格搜索
  │
  ↓
Brent / 黄金分割连续精细优化
  │
  ↓
得到最优时间偏差 Δt*
  │
  ↓
最优解有效性检验
  │
  ├── 边界检验
  ├── 唯一性检验
  ├── 重叠区间检验
  └── RMSE≈0 一致性检验
  │
  ↓
修正方式2时间轴
  │
  ↓
合并两类对齐后的无噪声采样点
  │
  ↓
重新构造连续真实轨迹
  │
  ↓
按 0.1 s 间隔采样
  │
  ↓
输出 10 Hz 位置轨迹
```

## 14. 实现注意事项

1. 不要先把两组数据都插值到 10 Hz 再估计时间偏差；应先用原始采样数据估计 `Δt`，完成对齐后再生成最终 10 Hz 轨迹。
2. 插值只用于连续轨迹重建，不应在无观测支撑区域进行随意外推。
3. 若互相关估计与最小 MSE 优化结果明显不一致，应检查轨迹周期性、搜索范围或插值模型。
4. 应保存 `J(Δt)` 曲线、`C(τ)` 曲线、对齐前后轨迹对比图和残差图，作为论文中的模型检验依据。
5. 问题一的“融合”本质上更接近对齐后联合增加采样密度，而不是问题二、三中的随机噪声意义下的统计融合。
