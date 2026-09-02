# ProvSci 下一阶段要求

本文件冻结 2026-08-29 之后 ProvSci 数据结果智能体的工作范围。综述论文、钙钛矿/分子材料、公司生产设备和长程智能体状态维护算法不属于 ProvSci 第一版验收条件。

## 一句话目标

把公开科学文献中的结果数据变成带来源、证据、条件、单位、处理路径和验证状态的结构化数据，而不是只生成看起来合理的回答。

## 当前基线

仓库是 v0.3 工程原型，已经具备多格式输入适配、结果段路由、表格/文本/关系候选挖掘、数值与单位解析、acquisition path、确定性 verifier、Gold/Silver/Human Review 分层、批处理、JSONL、CLI、benchmark 和本地单用户审核工作台。当前 benchmark 证明流程可运行，但数据规模小，复杂 PDF、图表、外部来源获取、多人协作和批量复核仍未完成。

## P0：可汇报、可复现

1. 先选定一个非钙钛矿、领域无关的具体结果形态，并冻结字段和 ResultCard schema；领域专用 profile 后续再按需细化。
2. 使用真实、许可清晰的公开文献扩充人工核验样本，记录结果、证据位置、条件、单位和失败原因。
3. 重新运行 demo、benchmark、real-smoke，输出结果表和典型失败案例。
4. 完成从文献导入到 Gold/Silver/Human Review 的端到端演示，并确保按 README 可复现。

本阶段默认场景为 `scientific_quantitative_result_v1`：先处理公开科学文献、实验报告和结构化实验资料中的带单位定量结果（如浓度、IC50、产率、温度、时间、响应率和一般实验测量值），并绑定实体、指标与局部实验条件。生物医学细胞活性保留为一个可选的领域 profile 和回归样例，后续可在不改动 provenance 核心的前提下细化。

## P1：核心缺口

- 接入可替换的 Docling/GROBID/TATR/Nougat 等解析器，增强 PDF、表格、图注和补充材料；
- 记录 DOI/URL/版本/hash、获取时间和许可证；
- 扩大实验条件、文本关系、补充材料和图文结果候选；
- 增加歧义修复、重复/冲突检测、失败重试和人工复核入口；
- 增加批量处理、透明检索、CSV/JSON/数据卡导出，并保留实体—关系—证据结构。

截至 2026-08-29，已形成两项增量：

- `DocumentAdapter` 协议允许 Docling/GROBID/TATR/Nougat 等可选解析器返回统一 `DocumentPackage`，不把重型依赖写进核心运行时；
- 人工复核入口 `provsci review` 以 append-only `review_decisions.jsonl` 记录 accept/modify/reject；修改会重新执行 verifier，拒绝样本进入 `rejected.jsonl`，并重新物化 Gold/Silver/Human Review 结果。
- `provsci review-queue` 将活动 Human Review 样本按失败风险排序并给出建议动作；它是派生视图，不改变 append-only 审计记录。
- 外部补充材料可由 `fetch-supplement` 在 HTTP(S)、大小上限和 hash 记录约束下获取；完成运行可由 `retry` 在新目录按 fallback/指定策略重跑，并记录前次摘要 hash。
- `attach-supplement` 会在新 JSON 文档包中解析并附着下载的 CSV/TSV/HTML/文本/JATS/PDF 基线内容，保留文章和附件 hash；它不覆盖原始输入，附着后的包仍需经过 verifier 和许可门禁。
- 提供可选 `DoclingAdapter`，懒加载 Docling 并转换结构化文本、页码、bbox、表格和图注；核心运行时不强制安装重型依赖，未安装时显式报错。
- P2 已有固定 manifest 的模块消融脚本 `run_p2.sh`：分别报告 quality、verifier、license、evidence 和 acquisition_path 门禁的诊断差异；当前固定集没有篡改 path/evidence 样本，因此验证门禁的消融结果需谨慎解释。
- `run_adversarial.sh` 额外从干净候选派生受控污染样本，重新执行 verifier，覆盖答案、证据、缺失路径和非法 path action 的拒绝测试；它是诊断 benchmark，不会修改 Gold manifest。
- JSONL/CSV 结果旁新增 `data_card.json`，汇总样本、文献、领域、指标、模态、许可和失败模式；它不替代逐条 provenance。
- 本地单用户审核工作台 `provsci review-ui` / `provsci review-serve` 已完成：静态快照和 loopback 服务并排展示来源、证据、ResultCard、路径、验证和许可；提交仍走 append-only 决策、verifier 和许可证门禁，不暴露运行目录文件。
- 增加了结构化曲线点 baseline：figure 可携带轴标签/单位与 series/points，`multimodal` 策略会生成点级 locator 和 `extract_figure_point` 可执行路径；像素级图像估读、OCR/VLM 仍未完成。
- 增加通用 `fetch-url` 来源获取：HTTP(S) 重定向、大小上限、最终 URL、Content-Type、下载日期、SHA-256 版本和 JATS 的许可证/文献元数据都会写入 manifest-ready 记录；未知许可仍不能进入 Gold。

多人协作、权限管理和批量复核仍属于后续 P1/A2 工作。

## P2：论文/产品判断

固定测试集，报告准确率、召回率、证据定位、单位/条件匹配、验证通过率、Gold 比例、成本、耗时和失败类型；与规则基线、基础 LLM 或专用工具对比，并做证据、验证和质量门禁消融。根据规模、质量和实验结果判断方法论文、数据库论文或专用数据产品路线。

## Gold 最低要求

每条 Gold 至少包含：

```text
结果 / 单位 / 条件
来源 / 证据位置 / 原文片段
任务类型 / 处理步骤 / 可执行路径
验证状态 / 质量等级 / 许可信息
```

不能确认的结果不得硬塞进 Gold，必须进入 Silver 或 Human Review，并保留 `failure_mode`、受影响字段和建议修复动作。评测除答案匹配外，还必须检查证据支持、条件对应、路径 replay、重复 ID、文献级切分和许可覆盖。

## 完成判据

给定一篇真实公开文献，系统能够稳定完成：

```text
文献导入 → 结果候选发现 → 证据定位 → 结构化 ResultCard
→ 处理路径记录 → 程序验证 → Gold/Silver/Human Review 分流
→ 可检索、可导出的结果
```

代码、样例、评测脚本和结果表可被他人重跑；系统明确区分可信数据、需要人工确认的数据和暂时无法回答的问题。

## 和会议中其他任务的边界

- **综述文章**：你负责继续修改、补图、完善现状分析并选择期刊投稿。它是独立论文任务，不是 ProvSci 的验收条件。
- **长程智能体状态维护算法**：学姐负责核心研究方案，包括图结构、规范图/行为图/观测图和状态依赖维护。方案确定后，你配合代码复现、Benchmark、对比实验和消融实验；不需要现在把这套算法并入 ProvSci。
- **钙钛矿与公司生产设备**：是另一条应用方向，不是你当前 ProvSci 的默认数据领域，也不应直接写成你的个人待办。
