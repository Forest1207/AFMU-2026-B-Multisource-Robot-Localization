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
04_experiments/       实验与敏感性分析
05_results/           各问正式结果
06_figures/           论文与分析图
07_paper/             论文分章节草稿
08_submission/        最终提交材料
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
- `00_problem/attachments/result_template.xlsx`

> 原始附件只读保存；所有处理后数据和结果均写入其他目录，避免污染原始数据。

## 环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

## 工作原则

1. 每个问题先记录假设与识别策略，再实现代码。
2. 所有关键参数和结果保存在 `05_results/`，避免只存在 notebook 中。
3. 图表统一从可复现脚本生成。
4. 重要模型选择、失败尝试和版本变化记录在 `09_project_log/`。
5. 最终 `result.xlsx` 不修改题目模板中的红色文字。
