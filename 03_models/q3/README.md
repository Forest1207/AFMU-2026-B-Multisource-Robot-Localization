# Q3 Model — 系统偏差检验驱动的鲁棒异步多源状态融合

> 状态：建模思路已整理，待附件 3 数据实算与参数校准。

## 1. 问题定位

问题 3 与问题 2 的核心区别在于：问题 2 已知存在随机噪声与固定系统偏差，而问题 3 面对真实测量数据，必须先判断两种定位方式之间是否存在显著系统偏差，再决定采用何种融合模型。

因此，问题 3 建议建成：

**偏差不敏感的时间粗对齐 → 时间偏差/空间偏差联合辨识 → 系统偏差假设检验 → 根据检验结果选择融合模型 → RTS 平滑 → 输出 10 Hz 轨迹与速度/加速度状态。**

可将整个方法命名为：

**基于系统偏差假设检验的鲁棒异步多源状态融合模型**  
*Robust Asynchronous Multi-source State Fusion Model with Systematic Bias Testing*

---

## 2. 测量模型与可辨识性

设机器人真实二维位置为

$$
\mathbf p(t)=\begin{bmatrix}x(t)\\y(t)\end{bmatrix}.
$$

两种定位方式分别建模为

$$
\mathbf z_{1,i}=\mathbf p(t_{1,i}+\tau_1)+\mathbf b_1+\boldsymbol\varepsilon_{1,i},
$$

$$
\mathbf z_{2,j}=\mathbf p(t_{2,j}+\tau_2)+\mathbf b_2+\boldsymbol\varepsilon_{2,j}.
$$

其中：

- $\tau_1,\tau_2$：两种定位方式的时间偏差；
- $\mathbf b_1,\mathbf b_2$：固定空间系统偏差；
- $\boldsymbol\varepsilon_1,\boldsymbol\varepsilon_2$：随机测量噪声。

仅凭两个定位源且无真值基准时，能够稳定辨识的是相对偏差：

$$
\Delta\tau=\tau_2-\tau_1,
$$

$$
\Delta\mathbf b=\mathbf b_2-\mathbf b_1.
$$

因此规定定位方式 1 为参考系：

$$
\tau_1=0,\qquad \mathbf b_1=\mathbf 0,
$$

所估计的 $\Delta\tau$ 和 $\Delta\mathbf b$ 均解释为“定位方式 2 相对于定位方式 1”的时间偏差与空间系统偏差。

---

## 3. 模块 A：偏差不敏感的时间粗对齐

### 3.1 为什么不直接用位置序列做相关

若存在固定系统偏差

$$
\mathbf z_2(t)=\mathbf p(t)+\mathbf b+\boldsymbol\varepsilon(t),
$$

直接比较位置序列会受到整体平移影响。

一阶差分可消除常量偏差：

$$
\Delta\mathbf z_2
=\mathbf z_2(t+\Delta t)-\mathbf z_2(t)
\approx \Delta\mathbf p+\Delta\boldsymbol\varepsilon.
$$

因此优先使用位移增量或速度特征进行时间配准。

### 3.2 构造速度模长

$$
 v_i(t)=\left\|\frac{\Delta\mathbf z_i}{\Delta t}\right\|.
$$

对两个速度序列做互相关：

$$
R_{12}(\tau)=\sum_k(v_1(t_k)-\bar v_1)(v_2(t_k+\tau)-\bar v_2).
$$

得到时间偏差粗估计

$$
\Delta\tau_0=\arg\max_\tau R_{12}(\tau).
$$

该步骤提供后续精细优化的稳定初值。

---

## 4. 模块 B：时间偏差与空间偏差联合精估计

在粗对齐附近进行一维 Profile Least Squares 搜索。

对任一候选时间偏差 $\tau$，构造同一真实时刻的差值

$$
\mathbf d_k(\tau)=\mathbf z_2(t_k+\tau)-\mathbf z_1(t_k).
$$

若存在固定系统偏差，则

$$
\mathbf d_k=\mathbf b+\boldsymbol\eta_k.
$$

给定 $\tau$ 时，系统偏差的加权估计为

$$
\hat{\mathbf b}(\tau)
=\frac{\sum_k w_k\mathbf d_k(\tau)}{\sum_k w_k}.
$$

构造剖面目标函数

$$
J(\tau)=\sum_k w_k\left\|\mathbf d_k(\tau)-\hat{\mathbf b}(\tau)\right\|^2.
$$

最终

$$
\hat\tau=\arg\min_\tau J(\tau),
$$

$$
\hat{\mathbf b}=\hat{\mathbf b}(\hat\tau).
$$

这样可将原本对 $(\tau,b_x,b_y)$ 的联合非线性优化转化为一维时间偏差搜索，并对 $\mathbf b$ 解析求解，提高稳定性。

---

## 5. 模块 C：Huber 残差加权迭代最小二乘

附件 3 为真实测量数据，需考虑异常点、瞬时跳点和非高斯误差。建议延续问题 2 的残差加权思想，使用 Huber 权重。

第 $m$ 次迭代残差定义为

$$
r_k^{(m)}=\left\|\mathbf d_k-\mathbf b^{(m)}\right\|.
$$

Huber 权重：

$$
w_k=
\begin{cases}
1,&r_k\le c,\\
\dfrac{c}{r_k},&r_k>c.
\end{cases}
$$

更新系统偏差

$$
\mathbf b^{(m+1)}=
\frac{\sum_k w_k\mathbf d_k}{\sum_k w_k}.
$$

收敛条件可设置为

$$
\|\mathbf b^{(m+1)}-\mathbf b^{(m)}\|<\varepsilon.
$$

建议同时对时间偏差候选点计算鲁棒目标函数，从而降低局部异常数据对配准结果的影响。

---

## 6. 模块 D：系统偏差存在性检验

完成时间对齐后，对

$$
\mathbf d_k=\begin{bmatrix}d_{x,k}\\d_{y,k}\end{bmatrix}
$$

进行二维系统偏差假设检验。

### 6.1 假设

原假设：

$$
H_0:\mathbf b=\mathbf 0.
$$

即不存在显著固定系统偏差。

备择假设：

$$
H_1:\mathbf b\neq\mathbf 0.
$$

即存在显著固定系统偏差。

### 6.2 推荐主检验：二维 Wald + HAC 协方差

由于轨迹残差具有时间相关性，不建议直接把所有残差视为独立样本做普通 t 检验。

估计平均偏差

$$
\hat{\mathbf b}=\frac1N\sum_{k=1}^{N}\mathbf d_k.
$$

使用 HAC（Newey-West 类）方法估计

$$
\widehat{\operatorname{Cov}}(\hat{\mathbf b}).
$$

构造 Wald 统计量

$$
T=
\hat{\mathbf b}^{T}
\widehat{\operatorname{Cov}}(\hat{\mathbf b})^{-1}
\hat{\mathbf b}.
$$

在 $H_0$ 下近似满足

$$
T\sim\chi^2(2).
$$

取显著性水平 $\alpha=0.05$：

- 若 $p<0.05$，拒绝 $H_0$，认为存在显著系统偏差；
- 若 $p\ge0.05$，不拒绝 $H_0$，表述为“未发现显著固定系统偏差”，而不是“证明不存在偏差”。

### 6.3 稳健性备选：Block Bootstrap

若残差自相关明显或样本分布偏离高斯，可使用 moving/block bootstrap，对连续时间块进行重采样，构造 $b_x,b_y$ 及 $\|\mathbf b\|$ 的置信区间。

---

## 7. 统计显著性 + 工程显著性双判据

仅依赖 p 值可能导致样本量大时将极小偏差判为“统计显著”。因此建议同时评价偏差的工程尺度。

定义偏差模长

$$
\|\hat{\mathbf b}\|=
\sqrt{\hat b_x^2+\hat b_y^2}.
$$

再定义无量纲偏差指数

$$
I_b=\frac{\|\hat{\mathbf b}\|}{\sigma_d},
$$

其中 $\sigma_d$ 为对齐后差值残差的典型随机噪声尺度。

推荐采用双判据：

1. $p<0.05$；
2. $I_b>\gamma$，或 $\|\hat{\mathbf b}\|$ 大于预设工程容差。

只有两者同时满足时，才将其认定为“具有实际意义的系统偏差”。

阈值 $\gamma$ 或工程容差应在实算后结合噪声水平与题目精度需求确定。

---

## 8. 模块 E：固定偏差假设诊断

即使检测到 $\mathbf b\neq0$，也需检查其是否真能视为常量。

可绘制

$$
d_x(t),\qquad d_y(t)
$$

及其滑动均值，并进一步拟合

$$
d_x(t)=b_x+k_xt+\varepsilon_x,
$$

$$
d_y(t)=b_y+k_yt+\varepsilon_y.
$$

检验

$$
H_0:k_x=k_y=0.
$$

判断：

- 若趋势项不显著：固定偏差模型合理；
- 若趋势项显著：偏差随时间漂移，应升级为慢变随机游走模型

$$
\mathbf b_{k+1}=\mathbf b_k+\mathbf w_{b,k}.
$$

该步骤作为模型诊断和扩展，不必在主模型中无条件引入复杂的时变偏差。

---

## 9. 模块 F：根据偏差检验结果选择融合模型

问题 3 的关键不是始终使用同一个 KF，而是由数据自动决定观测模型。

### 9.1 无显著系统偏差：普通异步多率 KF

为问题 4 同时提供速度和加速度，状态向量建议直接采用二维常加速度（CA）模型：

$$
\mathbf X_k=
\begin{bmatrix}
x_k&y_k&v_{x,k}&v_{y,k}&a_{x,k}&a_{y,k}
\end{bmatrix}^T.
$$

单方向状态转移矩阵

$$
F_1(\Delta t)=
\begin{bmatrix}
1&\Delta t&\frac12\Delta t^2\\
0&1&\Delta t\\
0&0&1
\end{bmatrix}.
$$

二维状态转移由两个方向组合得到。

观测仅包含位置：

$$
\mathbf z_k=H\mathbf X_k+\mathbf v_k.
$$

### 9.2 存在显著固定系统偏差：偏差增广 KF

将相对系统偏差加入状态向量：

$$
\mathbf X_k=
\begin{bmatrix}
x&y&v_x&v_y&a_x&a_y&b_x&b_y
\end{bmatrix}^T.
$$

定位方式 1 的观测矩阵：

$$
H_1=
\begin{bmatrix}
1&0&0&0&0&0&0&0\\
0&1&0&0&0&0&0&0
\end{bmatrix}.
$$

定位方式 2 的观测矩阵：

$$
H_2=
\begin{bmatrix}
1&0&0&0&0&0&1&0\\
0&1&0&0&0&0&0&1
\end{bmatrix}.
$$

若偏差可视为固定，则

$$
b_{x,k+1}=b_{x,k},\qquad b_{y,k+1}=b_{y,k},
$$

并设置很小的偏差过程噪声 $Q_b$。

若固定性检验表明存在缓慢漂移，则适当增大 $Q_b$，使其成为慢变偏差状态。

---

## 10. 直接处理原始异步观测，不先制造 10 Hz 伪观测

不建议先将 4 Hz 和 5 Hz 原始数据分别插值到 10 Hz 后再送入 KF，因为插值点并非新的独立测量，会造成同一原始观测信息被重复利用，使滤波协方差过度收缩。

推荐流程：

1. 时间校正

$$
t_{2,j}^{*}=t_{2,j}+\hat{\Delta\tau};
$$

2. 合并原始观测时间

$$
\mathcal T=\{t_{1,i}\}\cup\{t_{2,j}^{*}\};
$$

3. 按真实事件时间排序运行 Kalman Filter；
4. 每个事件使用对应的真实 $\Delta t$ 更新状态转移矩阵；
5. 若当前仅有传感器 1，则仅做方式 1 更新；若仅有传感器 2，则仅做方式 2 更新；若二者近乎同时到达，则顺序或联合更新。

这属于标准的异步多率状态估计框架，更贴合 4 Hz + 5 Hz 异构定位的题意。

---

## 11. 模块 G：RTS 平滑与 10 Hz 统一状态输出

完成异步 KF 前向滤波后，对离线整段轨迹执行 RTS 后向平滑，以充分利用未来观测改善历史状态估计。

最终建立统一 10 Hz 时间网格：

$$
t_n=t_0+0.1n.
$$

基于平滑后的连续状态预测输出：

$$
\hat{\mathbf p}(t_n)=
\begin{bmatrix}
\hat x(t_n)\\
\hat y(t_n)
\end{bmatrix}.
$$

同时保留

$$
v(t_n)=\sqrt{v_x^2+v_y^2},
$$

$$
a(t_n)=\sqrt{a_x^2+a_y^2}.
$$

建议问题 3 内部完整输出字段：

```text
t, x, y, vx, vy, speed, ax, ay, acceleration
```

这组状态可直接作为问题 4 的输入，用于射击/拍照的距离、速度、加速度及连续可行时间窗判断。

---

## 12. 模型诊断与评价指标

问题 3 实算后至少保留下列诊断量：

### 时间配准
- 粗估计 $\Delta\tau_0$；
- 精估计 $\hat{\Delta\tau}$；
- 配准前后速度/位移增量相关系数；
- 目标函数 $J(\tau)$ 曲线及最小值附近稳定性。

### 系统偏差
- $\hat b_x,\hat b_y$；
- $\|\hat{\mathbf b}\|$；
- Wald 统计量与 p 值；
- HAC 标准误 / Bootstrap 置信区间；
- 工程偏差指数 $I_b$；
- 偏差随时间趋势检验结果。

### 融合质量
- 两种原始观测相对融合轨迹的残差 RMSE；
- 创新序列均值是否接近 0；
- 创新序列自相关性；
- 归一化创新平方 NIS（可选）；
- 融合前后轨迹平滑性；
- 速度、加速度的物理合理性。

由于附件 3 无真实轨迹真值，不能将“对某一传感器的误差更小”直接等同于绝对定位精度更高，应以内部一致性、残差统计性质和模型诊断作为主要评价依据。

---

## 13. 推荐流程图

```text
附件3：4 Hz / 5 Hz 原始实际定位数据
                │
                ▼
        数据质量与异常点检查
                │
                ▼
    一阶差分 / 速度特征互相关
                │
                ▼
          时间偏差粗估计
                │
                ▼
 Profile + Huber 加权迭代最小二乘
                │
                ▼
   Δt_hat, b_x_hat, b_y_hat
                │
                ▼
       H0: b = 0 vs H1: b ≠ 0
                │
                ▼
      Wald + HAC / Block Bootstrap
                │
          ┌─────┴─────┐
          │           │
        无偏差       有偏差
          │           │
          ▼           ▼
     普通多率KF   偏差增广多率KF
          │           │
          └─────┬─────┘
                ▼
          创新残差诊断
                │
                ▼
             RTS平滑
                │
                ▼
     10 Hz: x, y, v, a 状态轨迹
                │
                ▼
            供问题4使用
```

---

## 14. 论文中的核心亮点表述

问题 3 建议突出以下三点，而不是简单描述为“迭代最小二乘 + Kalman Filter”：

1. **偏差不变时间对齐**：利用一阶差分/速度特征抵消固定空间偏差对时间同步的干扰；
2. **检验驱动的融合结构选择**：先统计判断系统偏差是否存在，再决定使用普通 KF 或偏差增广 KF，避免无条件增加状态维数；
3. **原始异步多率融合**：直接在真实 4 Hz/5 Hz 时间戳上进行状态更新，避免先插值至 10 Hz 所产生的伪观测与信息重复利用。

辅助亮点：

- Huber 残差加权提高对异常测量的鲁棒性；
- HAC/Block Bootstrap 处理时间相关残差下的偏差显著性判断；
- 统计显著性与工程显著性联合判定；
- RTS 平滑输出 10 Hz 的位置、速度和加速度，为问题 4 形成无缝接口。

---

## 15. 下一步实现顺序

建议按以下顺序开发当前目录中的代码：

1. `bias_test.py`
   - 原始 4 Hz/5 Hz 数据读取；
   - 差分/速度构造；
   - 互相关时间偏差粗估；
   - Profile + Huber 参数精估；
   - HAC Wald 检验；
   - Block Bootstrap 稳健性检验；
   - 偏差固定性/趋势诊断。

2. `robust_fusion.py`
   - CA 状态空间模型；
   - 原始异步事件时间 KF；
   - 无偏差/偏差增广两种观测模型；
   - RTS smoother；
   - 10 Hz 状态重采样输出；
   - 创新残差与 NIS 等诊断。

3. 实验输出
   - 参数估计表；
   - 偏差检验表；
   - 时间配准目标函数图；
   - 配准前后轨迹图；
   - 系统偏差残差图；
   - 融合轨迹与速度/加速度图；
   - 最终 10 Hz 状态表，供 Q4 调用。
