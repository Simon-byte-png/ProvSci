# ProvSci P0 结果表（2026-08-29）

运行入口：`./scripts/run_p0.sh work/p0-final`。运行输出放在指定的 `work/` 子目录，该目录是生成物，不纳入源码包；结果可由同一命令重建。当前校验目录为 `work/p0-generic-final-v3/`。

## 固定人工 Gold manifest

数据集为 `examples/benchmark/p0-gold-manifest.json`，包含 2 篇真实 CC-BY PMC/JATS 文献，按通用 `scientific_quantitative_result_v1` profile 运行；当前文献内容来自生物医学，只作为真实样例而非产品领域限制，共 52 条人工核验 claim。所有输入都记录了 source URL、许可证来源、获取日期和运行时 SHA-256。

| 策略 | 候选数一致率 | Gold 数一致率 | Claim Recall | Claim Precision | Path Reproducibility | Evidence Coverage | License Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| `table_only` | 0.0000 | 0.0000 | 0.1154 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `full` | 0.0000 | 0.0000 | 1.0000 | 0.3152 | 1.0000 | 1.0000 | 1.0000 |
| `result_focused`（默认） | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

`result_focused` 的 52 条预测与人工 claim 完全匹配：46 条通过 Gold 门禁，6 条关系候选因主客体跨度不稳定进入 Silver/Human Review。`full` 保留高召回对照，但会把方法/条件和叙述噪声一起抽出；这正是需要语义路由和质量门禁的可复现实证。

benchmark JSON 还会记录 `table_value_match_rate`、`evidence_locator_precision/recall`、失败类型、重复/冲突计数和 `comparison_protocol`；在 P0 的 `result_focused` 结果中，表格值/单位/指标/实体匹配率以及证据定位精确率和召回率均为 1.0。这里的定位指标是与人工 manifest 的页/段落/表格行列 locator 对齐，不等同于大规模人工证据充分性评审。

P0 manifest 额外标注了 6 条表格 IC50 的处理时间条件（12/24/36 h），`result_focused` 的 `condition_match_rate` 为 1.0。每次运行还会报告 `runtime_seconds`、`candidate_rate_per_second` 和 `estimated_cost_usd`；当前实现为纯本地确定性流水线，没有模型调用，因此成本基线为 0 美元，不能替代后续模型/外部 parser 的真实成本评估。

## 运行产物

| 运行 | 文献数 | 候选 | Gold | Silver | Human Review | Path Reproducibility |
|---|---:|---:|---:|---:|---:|---:|
| demo | 1 | 6 | 6 | 0 | 0 | 1.0000 |
| P0 人工 benchmark（默认策略） | 2 | 52 | 46 | 6 | 6 | 1.0000 |
| 四篇真实文献 smoke（默认策略） | 4 | 192 | 186 | 6 | 6 | 1.0000 |

默认策略同时输出重复组统计：P0 人工 benchmark 识别 6 个跨表格/正文一致结果组（12 条样本），四篇 smoke 在当前表格标签和条件传播规则下识别 7 组（16 条样本）；系统不静默删除任一证据来源。当前两组运行均识别到 0 个跨证据冲突组。冲突检测按同一文献的 metric/entity/unit/condition 聚合，但只有来自不同表格行、段落、图或补充材料上下文的不同值才会进入冲突队列；同一段剂量/时间序列和同一表格行的均值/误差列暂不强行判为冲突。

冲突回归样例位于 `tests/test_pipeline.py::PipelineTests::test_conflicting_values_are_routed_to_human_review`：两个表格在同一实体和 IC50 单位下报告不同值时，两个样本均保留原始证据、标记 `conflicting_values`，并分流到 Silver/Human Review。

四篇 smoke 文献中 `PMC2010468` 没有被当前结果路由识别出的结果候选；它仍保留在 smoke manifest 中，用于验证“无候选”不是运行崩溃。该 smoke 是管线健康检查，不等价于人工精度 benchmark。

## 已知限制

- 两篇人工 Gold 文献仍是小规模样本，不能代表跨学科或复杂 PDF 的总体性能。
- 当前 JATS 页码均为规范化包中的 `0`，复杂 PDF 的页码/bbox 解析仍是 P1 工作。
- 关系抽取已能显式分流难例，但主客体规范化仍需要领域模型或人工修订。
- `result_cards.csv` 是扁平分析视图，审计复现应使用同目录的 `result_cards.jsonl`（含证据和 acquisition path）。

## 增量来源审计（不并入当前 Gold manifest）

`work/sources-v1/PMC13046741.nxml` 和 `work/sources-v1/PMC13288017.nxml` 已通过通用 profile 做独立 smoke：前者 22 条候选、8 条自动 Gold、14 条因实体/问题不充分进入 Human Review；后者 20 条候选全部保留为 Silver/Human Review，其中许可证未知和跨段冲突尚未解决。它们暂不计入 52 条人工 Gold，避免把自动结果或许可不明结果误报为人工标注。

另外，表格行标签现在识别 `hPMTs`/`Analyte` 等科学列名，并只把明确的时间表头或 caption 时间传播为条件；这让 `PMC9857184` 的表格实体和 48 h 条件可定位，但其完整 140 条候选仍需要逐项人工抽查后才能扩充 Gold manifest。
