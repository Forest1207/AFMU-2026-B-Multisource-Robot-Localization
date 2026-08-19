# W2 打包门禁

结论：**PASS**。

## 正式提交件

- PDF：`08_delivery/B题-完整论文.pdf`。
- LaTeX 工程：`08_delivery/完整论文-LaTeX/`。
- 结果工作簿副本：`05_results/q4/result.xlsx`；只填写正式答案区域，原模板保持只读。

## 自动验证

- `evidence/latex_validation.json`：`passed=true`；全文27页、无附录，40个编号公式、19幅图、3张正文表、8条引用。
- XeLaTeX 连续两遍正常退出；无缺失文件、未定义命令、重复标签、未解析交叉引用、字体缺失、Overfull/Underfull 或空白页。
- A4、25 mm 边距、摘要首页、无目录、无承诺书和编号页、页脚连续页码、无队伍/姓名/学校/教师信息。
- 最低栅格图分辨率 730 dpi，高于 300 dpi 门槛；其余主要图件为矢量 PDF。
- `evidence/paper_content_audit.json`：公式、图表、文献、模型与验证项目均通过；`ok=false`仅因通用审计器硬编码要求附录。正式论文按用户要求取消附录，该结构例外已在W1记录，不影响LaTeX与PDF门禁。
- Q1–Q4 最新合成测试与正式验证均通过，见 `evidence/revalidation_q1.txt` 至 `revalidation_q4.txt`。

## 人工视觉检查

使用Poppler将正式PDF全部27页渲染检查，重点复核第五章起始页、四个算法伪代码块、长公式、19幅图、九行日程和参考文献末页；检查记录见 `evidence/pdf_visual_qa.md`，临时渲染图不纳入提交包。

## DOCX 审计副本边界

`08_delivery/B题-论文审计副本.docx` 仅作为内容审计副本：Pandoc 转换清单和原生公式检查通过；当前运行环境缺少 LibreOffice，通用 OOXML 校验器又对 Pandoc 的 PNG 内容类型声明和一处 OMML 样式节点给出兼容性警告，因此不将该 DOCX 宣称为正式版式交付。正式提交格式与版面结论仅以通过 XeLaTeX 严格验证和逐页视觉检查的 PDF 为准。
