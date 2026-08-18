# 方法依据与文献核验记录

核验日期：2026-08-19  
用途：只记录本项目模型部件的原始依据、适用边界和可追溯元数据；不把文献中的结论当作本题实算结果。

## 已核验来源

| ID | 来源 | DOI / 稳定链接 | 本项目用途 | 使用边界 |
|---|---|---|---|---|
| SRC-01 | Huber, P. J. (1964). *Robust Estimation of a Location Parameter*. The Annals of Mathematical Statistics, 35(1), 73–101. | [10.1214/aoms/1177703732](https://doi.org/10.1214/aoms/1177703732) | Q2、Q3 的 Huber 损失与异常值稳健估计依据 | Huber 损失降低离群点影响，不自动消除时间序列相关性；显著性推断另用 HAC 或区块自助法。 |
| SRC-02 | Kalman, R. E. (1960). *A New Approach to Linear Filtering and Prediction Problems*. Journal of Basic Engineering, 82, 35–45. | [CERN 书目记录](https://cds.cern.ch/record/434680) | Q2、Q3 线性状态空间递推滤波依据 | 经典最优性依赖线性—高斯及正确协方差设定；本题需用残差与基线对照检验近似是否可接受。 |
| SRC-03 | Rauch, H. E., Tung, F., & Striebel, C. T. (1965). *Maximum Likelihood Estimates of Linear Dynamic Systems*. AIAA Journal, 3(8), 1445–1450. | [10.2514/3.3166](https://doi.org/10.2514/3.3166) | Q2、Q3 固定区间前向滤波—后向平滑依据 | RTS 是离线固定区间平滑；论文不得把它表述成实时在线输出。 |
| SRC-04 | Newey, W. K., & West, K. D. (1987). *A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix*. Econometrica, 55(3), 703–708. | [NBER 工作论文及出版信息](https://www.nber.org/papers/t0055) | Q3 二维均值偏差 Wald 检验的 HAC 协方差依据 | HAC 只修正渐近协方差；带宽选择必须报告，并以区块自助法交叉验证。 |
| SRC-05 | Künsch, H. R. (1989). *The Jackknife and the Bootstrap for General Stationary Observations*. The Annals of Statistics, 17(3), 1217–1241. | [10.1214/aos/1176347265](https://doi.org/10.1214/aos/1176347265) | Q3 移动区块自助置信区间依据 | 方法要求弱平稳/局部近似平稳；必须报告区块长度敏感性，不能把单一长度当作确定真值。 |
| SRC-06 | Fritsch, F. N., & Carlson, R. E. (1980). *Monotone Piecewise Cubic Interpolation*. SIAM Journal on Numerical Analysis, 17(2), 238–246. | [10.1137/0717021](https://doi.org/10.1137/0717021) | Q1 插值敏感性中的 PCHIP 对照依据 | 单调保形不等价于轨迹动力学最优；本题仅作为数值稳健性对照。 |
| SRC-07 | Hall, D. L., & Llinas, J. (1997). *An Introduction to Multisensor Data Fusion*. Proceedings of the IEEE, 85(1), 6–23. | [10.1109/5.554205](https://doi.org/10.1109/5.554205) | 多源异构数据融合的层次、目标与术语依据 | 综述提供框架，不替代本题参数辨识、可识别性分析和实证检验。 |
| SRC-08 | Huangfu, Q., & Hall, J. A. J. (2018). *Parallelizing the Dual Revised Simplex Method*. Mathematical Programming Computation, 10(1), 119–142. | [10.1007/s12532-017-0130-5](https://doi.org/10.1007/s12532-017-0130-5) | Q4 线性/混合整数优化求解器技术背景 | 本题最终最优性以实际 MILP 状态、目标值、可行性复核为准，不由求解器论文代替。 |

## 证据使用规则

1. 正文引用仅用于解释“为何该数学工具适合该子步骤”，真实时间偏差、系统偏差、轨迹和任务安排全部由附件实算。
2. Q2/Q3 必须分别报告模型假设、残差诊断、基线比较和失败回退；不得仅凭经典论文宣称最优。
3. Q4 必须保留求解器状态、MIP gap（若可用）、硬约束逐条复核和局部高精度复查。
4. 最终参考文献按论文实际引用删减；未在正文使用的来源不得为凑数量而保留。
