# AFMU-2026-B-Multisource-Robot-Localization

2026 年全国大学生数学建模竞赛校内选拔赛 B 题：**多源融合机器人定位及任务优化**。

本仓库用于统一保存题目原始材料、建模思路、数据探索、模型代码、实验结果、论文素材和最终提交文件。

## 题目结构

- 问题 1：无噪声条件下，两种定位方式的时间对齐，并输出 10 Hz 轨迹。
- 问题 2：含随机噪声和固定系统偏差时，联合估计时间偏差、系统偏差并融合输出 10 Hz 轨迹。
- 问题 3：对实际测量数据判断系统偏差是否存在，再完成对齐与融合。
- 问题 4：沿附件 3 轨迹执行模拟射击和拍照扫描任务，进行可行窗口识别与任务调度优化，填写 `result.xlsx`。

## 目录

```text
00_problem/           原始题目与附件
01_ideas/             建模思路、假设、符号与备选模型
02_data_exploration/  数据探索 notebook、脚本与报告
03_models/            四问核心模型代码
04_experiments/       全流程复现 Notebook、实验与敏感性分析
05_results/           各问正式结果
06_figures/           论文与分析图
07_paper/             论文分章节草稿
08_delivery/          最新 PDF、完整 LaTeX 体系与交付说明
08_submission/        提交材料
09_project_log/       决策、实验、失败尝试与变更记录
src/                  公共工具函数
```

## 原始数据说明

原始二进制题目附件应放置于：

- `00_problem/problem_statement/2026_B题.docx`
- `00_problem/problem_statement/校内选拔赛通知.pdf`
- `00_problem/attachments/附件1.xlsx`
- `00_problem/attachments/附件2.xlsx`
- `00_problem/attachments/附件3.xlsx`
- `00_problem/attachments/附件4.xlsx`
- `00_problem/attachments/result.xlsx`

> 原始附件只读保存；所有处理后数据和结果均写入其他目录，避免污染原始数据。

## 环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

## 一键复现

从仓库根目录打开并按顺序执行
`04_experiments/reproduce_all_results.ipynb`。Notebook 从四个原始附件开始，
依次重算四问主结果、问题一至三的灵敏度分析、问题二至四的机器校验和全部正式图件。
复现产物写入 `04_experiments/reproduction_run/`，不会覆盖权威结果或原始附件。

最后一个代码单元比较 20 项论文关键结论：连续参数使用明确容差，轨迹行数、
问题三偏差状态、问题四任务数及工作簿填充行数要求完全一致。当前完整执行结果为
20/20 通过；问题四在无固定次数上限下得到 40 项任务，其中射击 14 项、拍照 26 项，
贪心算法给出 38 项可行下界。

命令行环境安装后也可直接执行：

```bash
jupyter nbconvert --to notebook --execute \
  04_experiments/reproduce_all_results.ipynb \
  --ExecutePreprocessor.timeout=-1 \
  --output reproduce_all_results.executed.ipynb
```

正式结果位于 `05_results/q1` 至 `05_results/q4`，图件位于
`06_figures/`，最新论文及完整 LaTeX 源码位于 `08_delivery/`。

## 工作原则

1. 每个问题先记录假设与识别策略，再实现代码。
2. 所有关键参数和结果保存在 `05_results/`，避免只存在 notebook 中。
3. 图表统一从可复现脚本生成。
4. 重要模型选择、失败尝试和版本变化记录在 `09_project_log/`。
5. 最终 `result.xlsx` 不修改题目模板中的红色文字。
