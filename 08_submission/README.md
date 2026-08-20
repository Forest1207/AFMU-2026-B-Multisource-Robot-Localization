# 当前正式提交目录

`08_submission/` 是当前分支的正式交付目录；`08_delivery/` 保留历史论文和历史格式转换产物，不作为本分支最终提交源。

## 推荐流程

```bash
# 1. 核验官方附件
python scripts/audit_inputs.py

# 2. 从官方附件重跑 Q1--Q4、图件与 Q4 验证
python scripts/run_formal_pipeline.py

# 3. 审计结果链
python scripts/audit_results.py

# 4. 生成自动 TeX 表格/宏并编译论文
python scripts/build_paper.py

# 5. 生成最终提交包
python scripts/package_submission.py
```

如赛事要求将官方附件也放入代码包：

```bash
python scripts/package_submission.py --include-inputs
```

## 生成内容

正常完成后包含：

```text
08_submission/
├── B题-多源融合机器人定位及任务优化.pdf
├── paper_build.json
├── audit/
│   ├── audit_report.json
│   └── audit_report.md
├── package/
│   ├── paper/
│   ├── result.xlsx
│   ├── code/
│   ├── formal_results/
│   ├── reproducibility/
│   ├── audit/
│   ├── README.md
│   └── DELIVERABLES.json
├── AFMU-2026-B-submission.zip
└── package_build.json
```

## Q4 提交口径

正式 `result.xlsx`：

- 不把模板初始 9 行解释为任务上限；
- 当最优任务数超过 9 条时，结果表 A:E 自动向下扩展；
- H:L 红色说明/范例保持原样；
- 所有最终任务时刻须通过 0.01 s 完整准备窗口复核；
- 正式 MILP 不加入题面未给出的跨任务准备时间互斥约束。

## 当前状态警告

在新版 Q4 用官方附件重新运行之前，仓库中旧的 9 项 `05_results/q4` 二进制/CSV 结果是历史产物。`audit_results.py` 与 `generate_latex_assets.py` 会拒绝这些旧结果，因此不能误打包成正式提交文件。
