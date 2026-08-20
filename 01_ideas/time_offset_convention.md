# 全题统一时间偏差口径

## 1. 论文与跨问题比较的唯一口径

全题统一定义第二类定位数据映射到第一类参考时钟时所需的**加性时间修正量**为

\[
t_{2,\mathrm{aligned}} = t_2 + \delta.
\]

其中：

- \(\delta>0\)：方式 2 时间戳整体增加，即向后平移；
- \(\delta<0\)：方式 2 时间戳整体减小，即向前平移。

论文、摘要、总表、LaTeX 自动表格和最终答辩一律报告 \(\delta\)，不得混用各代码模块内部的不同符号约定。

## 2. 各问内部变量到统一口径的转换

### Q1

Q1 内部已经使用

\[
t_{2,\mathrm{aligned}}=t_2+\mathrm{time\_offset\_s},
\]

因此

\[
\boxed{\delta_1=\mathrm{time\_offset\_s}}
\]

正式值：

\[
\boxed{\delta_1=-198.4317\ \mathrm{s}}
\]

### Q2

Q2 内部使用

\[
t_{2,\mathrm{corrected}}=t_2-\mathrm{time\_offset\_s},
\]

因此统一论文口径为

\[
\boxed{\delta_2=-\mathrm{time\_offset\_s}}
\]

正式值：

\[
\boxed{\delta_2=-50.1717\ \mathrm{s}}
\]

### Q3

Q3 内部同样使用

\[
t_{2,\mathrm{corrected}}=t_2-\mathrm{time\_offset\_s},
\]

因此

\[
\boxed{\delta_3=-\mathrm{time\_offset\_s}}
\]

正式值：

\[
\boxed{\delta_3=+367.8776\ \mathrm{s}}
\]

## 3. 为什么不强制修改底层代码变量

Q1--Q3 已经完成验证、敏感性分析和正式结果产出。为避免因仅修改符号定义而破坏既有数值链，本项目保留各模块内部变量定义，但在报告层增加统一转换。

原则是：

```text
底层模型：保持已验证实现
报告/论文：统一使用 delta
自动审计：检查 delta 与底层 time_offset_s 的转换关系
```

## 4. 自动化要求

后续所有自动生成的论文表格应从 `05_results/reporting_conventions.json` 读取统一时间偏差，不允许直接把 Q2/Q3 的 `time_offset_s` 原样写进总表。
