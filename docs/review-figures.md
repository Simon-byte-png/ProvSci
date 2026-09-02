# 可重复综述矩阵与图（通用场景）

ProvSci 现在把综述比较表和图作为可审计的独立数据资产。默认矩阵位于 [`examples/review/literature_matrix.json`](../examples/review/literature_matrix.json)，当前包含 21 条代表性工作，覆盖科学文档解析、表格识别、科学信息抽取、证据验证、检索增强和 agent 化流程。它们用于定性比较，不是性能排行榜，也不把钙钛矿或公司设备作为 ProvSci 默认领域。

## 一键重绘

在仓库根目录运行：

```bash
PYTHONPATH=src python3 scripts/build_review_figures.py \
  --input examples/review/literature_matrix.json \
  --output work/review-figures
```

也可以直接运行 `sh scripts/run_review_figures.sh work/review-figures`。

输出包括：

- `literature_matrix.normalized.json`：按年份和 ID 排序的规范化矩阵；
- `literature_matrix.csv`：便于人工检查和电子表格分析的扁平视图；
- `literature_summary.json`：按年份、领域、输入模态、证据粒度、验证和限制标签统计；
- `timeline.svg`：技术路线时间线，点位链接回来源 URL；
- `capability_matrix.svg`：文本、表格、图、公式、证据、验证和 agent 化能力矩阵；
- `evidence_chain.svg`：从文献发现到导出的证据链设计图；
- `failure_modes.svg`：由矩阵中定性限制标签生成的风险分布图；
- `manifest.json`：输入路径、产物清单和“图为定性统计”的声明。

脚本只使用 Python 标准库，因此不需要安装绘图库。SVG 中的来源链接和矩阵中的 `id` 允许从图回到文献记录；实际论文性能、许可和版本仍需在提交或产品使用前按来源重新核验。

## 编码约定

每条记录至少编码年份、工作类型、输入模态、解析器/模型族、抽取对象、LLM/VLM 与 agent 标记、证据粒度、验证方式、人工参与、数据规模描述、指标名称、代码/数据开放性、限制标签和 ProvSci 取舍。`reported_metrics` 只记录指标名称或定性说明，不复制未经统一任务定义和独立复核的数字。年份含 `year_basis`，对项目起始年或仓库快照明确标注近似性质。

图中的计数是矩阵字段的编码覆盖信号：例如 `failure_modes.svg` 的 `evidence` 计数表示多少工作在限制说明中提到证据风险，不表示失败率。后续若补充可比 benchmark，应新增独立字段并保留数据集、容差、模型和运行日期，不能覆盖当前定性记录。

## 与 ProvSci 通用场景的关系

矩阵帮助冻结通用 `scientific_quantitative_result_v1` 的边界：解析器负责恢复证据，候选挖掘负责发现结果，标准化负责单位/条件，白名单 acquisition path 负责可重放，verifier 和许可门禁决定 Gold/Silver/Human Review。领域 profile（如生物医学细胞活性）可以在同一 provenance 链路上追加，而不改变默认 ResultCard schema。
