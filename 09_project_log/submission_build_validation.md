# 正式交付构建验证

## 最终验证结论

当前 `agent/reference-submission-solution` 分支的正式交付链已在干净的 GitHub Actions Ubuntu 环境中实际跑通，而不是仅完成脚本编写。

验证工作流：`.github/workflows/submission-build.yml`

最近一次包含当前论文验证章节的成功运行：

- workflow run id: `32364292913`
- head commit: `1d40214e7351ffd53312cbf13f920db842086b1e`
- conclusion: `success`

全部关键步骤通过：

1. Python 环境与依赖安装；
2. `scripts/audit_results.py` 正式结果审计；
3. XeLaTeX / latexmk / 中文与推荐字体环境安装；
4. `scripts/build_paper.py` 真正编译正式论文 PDF；
5. `scripts/package_submission.py --skip-paper-build` 构建最终 ZIP；
6. ZIP CRC 与 staging 成员集合一致性检查；
7. paper/package build metadata 输出；
8. Actions Artifact 上传。

## LaTeX 构建期间发现并修复的问题

### 1. XeLaTeX 推荐字体缺失

精简安装 TeX Live 时，`hyperref` 所需的 Zapf Dingbats 字体度量 `pzdr.tfm` 未安装。工作流显式加入：

```text
texlive-fonts-recommended
```

避免依赖 apt 的隐式 recommend 行为。

### 2. 自动图件 TeX 的 `\IfFileExists` 闭合错误

旧生成器曾输出类似：

```tex
\IfFileExists{...}{...}{% figure omitted ... }
```

TeX 的 `%` 会将同一行后续内容全部注释，包括第三参数的闭合 `}`，从而造成 runaway argument。

现已固定为空 fallback：

```tex
\IfFileExists{...}{...}{}
```

并在生成器源码中记录该陷阱。

## Actions Artifact

成功运行 `32364292913` 生成：

- artifact name: `AFMU-2026-B-formal-submission`
- artifact id: `9404733827`
- size: `12,043,791 bytes`
- artifact digest: `sha256:11f3af264995e5738c98017590adcf99caf27aba06aa3629874fe7a87d84051c`
- created: `2026-08-20T11:34:28Z`
- expires: `2026-09-03T11:34:26Z`

Artifact 中包括：

- 正式论文 PDF；
- 当前 Q4 `result.xlsx`；
- `AFMU-2026-B-submission.zip`；
- `paper_build.json`；
- `package_build.json`；
- 正式审计报告。

## 当前交付状态

因此目前可以确认：

```text
正式结果
  -> 机器审计 PASS
  -> 自动 TeX 资产生成 PASS
  -> XeLaTeX 真编译 PASS
  -> PDF 生成 PASS
  -> 自包含 reproducible_source 打包 PASS
  -> ZIP CRC / 成员集合复核 PASS
  -> Actions Artifact PASS
```

后续正文编辑只要触及 `07_paper/latex/**`、`scripts/**`、`05_results/**`、`06_figures/**` 或 `08_submission/**`，`submission-build` 会再次执行真实交付验证。
