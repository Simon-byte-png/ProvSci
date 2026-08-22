# ProvSci

> 可审计科学数据智能体：从文献和实验结果中挖掘、处理、分类、标注并验证可复现的数据。

ProvSci 是一个面向科研数据生产的 agent-first 项目。它的最小闭环不是“让模型读完论文后写一个答案”，而是：

```text
Document package -> Mine candidates -> Build task/evidence/path -> Verify -> Curate Gold/Silver data
```

每一条进入 Gold 的样本都必须回答四个问题：

1. 结果来自哪一篇文献、哪一页、哪一个表格/段落/图？
2. 它被改写成了什么任务，答案和单位是什么？
3. 从证据到答案经过了哪些可执行步骤？
4. 清空答案后，系统能否只按这条路径重新得到同一个结果？

## 项目状态

当前是 v0.3 工程原型，优先打通多格式输入、结果数据挖掘、可执行 provenance path、确定性验证、语义质量门禁和文献级 benchmark 闭环。

- 已实现：规范化文档包、JSON/CSV/TSV/HTML/Markdown/纯文本/XLSX/JATS 基线适配器、系统 `pdftotext` PDF 基线、section-aware 结果路由、表格数值/文本测量/关系三元组候选挖掘、均值±误差解析、任务与证据生成、白名单 acquisition path、单位解析与换算、确定性验证、语义质量门禁、Gold/Silver 分层、批处理、文献级切分、严格 benchmark、JSONL 输出、CLI、端到端测试。
- 当前输入：JSON/CSV/TSV/HTML/Markdown/纯文本/XLSX/JATS；复杂 PDF 版面建议接入 Docling/GROBID/TATR/Nougat 适配器。
- 默认垂直切片：带单位的表格数值结果，例如浓度、IC50、产率、温度和实验测量值。
- 暂不宣称：通用科学家 agent 或 Science Foundation Model。当前准确定位是可审计的数据智能体原型。

## 公开汇报与完整调研

- **[领域调研与结果数据智能体功能蓝图](docs/领域调研与结果数据智能体功能蓝图.md)**：面向公开仓库的完整长文，系统梳理文档解析、文本/表格/图表抽取、知识图谱、LLM/VLM、多智能体、provenance 与人机协同现状，并详细列出 ProvSci 目标功能、架构、评价体系和路线图。
- [下周交流汇报稿](docs/下周交流汇报稿.md)：15 分钟汇报、5 分钟演示和常见追问的口头表达版本。

## 本阶段研究任务与预期交付

本阶段围绕三个彼此衔接的问题展开，既是 ProvSci 的研究主线，也是下一次组会汇报的主线。

1. **如何优化综述绘图**：把“手工画一张好看的示意图”升级为“从检索、筛选、编码到绘图都可追溯”的综述证据可视化流程。
2. **调研结果数据挖掘与处理智能体的领域现状**：比较传统信息抽取、科学文档解析、知识图谱、LLM/VLM 抽取和 agentic workflow，分析每类方案解决了什么、没有解决什么。
3. **定义希望实现的结果数据智能体**：详细列出输入、挖掘、处理、分类、标注、验证、人工复核、分析、可视化、导出、运维与合规功能，并收敛出可验证的最小闭环。

本阶段不以“接入一个大模型并生成回答”为完成标准，而以下列交付物为标准：

- 一份带来源、比较维度和空白分析的领域调研；
- 一套可以由结构化数据重复生成的综述图，而不是不可复用的截图；
- 一个输入真实文献、输出结构化结果与 provenance 的可运行原型；
- 一组明确的评价指标、失败案例和人工复核队列；
- 一张从 v0.3 原型到多模态、领域化、可扩展系统的路线图。

## 领域现状：从“文献解析工具”到“可审计数据智能体”

### 1. 领域技术版图

| 技术路线 | 典型能力 | 优点 | 主要不足 | ProvSci 的取舍 |
|---|---|---|---|---|
| 规则、模板与传统 NLP | 正则、词典、NER、关系抽取、单位解析 | 快、便宜、结果稳定、易定位错误 | 跨版式和跨领域泛化弱，维护成本高 | 用于数字、单位、路径执行和硬质量门禁 |
| 科学文档结构化 | PDF/JATS/HTML 转段落、表格、图注、参考文献及坐标 | 保留文档层级和版面，是后续抽取的基础 | 复杂表格、扫描件、公式和图表仍易丢失结构 | 采用可替换 adapter；当前基线支持 JATS 等格式，后续接 Docling/GROBID |
| 表格与图表抽取 | 表检测、结构识别、OCR、曲线/图例/坐标轴解析 | 能获取正文摘要之外的大量定量结果 | 合并单元格、脚注、误差线、图例映射和视觉质量导致误差传播 | 表格优先；图表进入带置信度的多模态通道并要求回看证据 |
| 领域信息抽取/知识图谱 | 实体、关系、事件、实验条件和属性标准化 | 便于查询、聚合、关联和跨文献分析 | ontology/schema 设计重，抽取错误会被图结构放大 | 先做结果级 schema 和证据图，再按领域接本体 |
| LLM/VLM 结构化抽取 | 按 schema 抽取文本、表格与图中的复杂字段 | 少样本适配快，能处理长尾表达和多模态输入 | 幻觉、数值漂移、输出不稳定、成本和复现性问题 | 模型负责候选生成与语义判断，不独占最终裁决 |
| RAG/深度研究智能体 | 检索、阅读、规划、综合与引用 | 能覆盖较宽问题并形成研究报告 | 通常优化“回答质量”，未必输出可复算的数据样本 | 把目标从回答改为可验证的数据产品和审计记录 |
| 人机协同数据整理 | 主动学习、低置信复核、修订历史 | 可把专家精力集中在高价值难例 | 审核界面和反馈闭环需要额外工程 | Silver/Human Review 是正式产物，不把失败静默丢弃 |

### 2. 已出现的关键能力

- **文档结构恢复**：GROBID 可把科学 PDF 解析为 TEI XML，并保留章节、引用、图表及坐标；Docling 面向多格式文档提供统一结构表示与结构化抽取能力。
- **跨来源证据整合**：文献知识图谱将论文元数据、实体、关系、数据库和实验信息组织为可查询网络，适合发现跨论文联系。
- **多模态结果挖掘**：新一代系统不只读正文，还从表格、图、图注和补充材料抽取材料组成、性能、实验条件等字段。
- **Agent 化编排**：任务规划、并行阅读、领域子智能体、证据汇总和质量检查开始替代单次模型调用。
- **可执行与验证**：更前沿的方向已从“抽取一段过程描述”走向知识图谱、实验协议或机器可执行步骤，说明 provenance 和 verification 正成为核心问题。

### 3. 仍未解决的共性问题

1. **证据定位不够细**：很多系统只给论文或段落级引用，无法定位到页码、表格行列、图中数据点或补充材料字段。
2. **数值正确不等于语义正确**：抽到 `42` 不代表样本、指标、条件、单位和统计口径匹配；缺一个限定条件就可能形成错误训练样本。
3. **多模态对齐困难**：正文、表、图和补充材料对同一结果的命名和粒度不同，且可能互相矛盾。
4. **缺少可复算路径**：多数工作只评估最终字段是否匹配，没有保存从证据到标准答案的工具步骤和中间值。
5. **评价不完整**：只报告字段 F1 会掩盖文献级泄漏、无效问题、许可不明、重复样本和不可复现路径。
6. **领域迁移代价高**：材料、化学、生物医学和其他领域的实体、单位、实验条件与 ontology 不同，通用 schema 容易过浅。
7. **失败被隐藏**：生产系统必须显式输出低置信、冲突、解析失败和需人工复核的样本，而不是只展示成功案例。

### 4. ProvSci 的研究空白定位

ProvSci 不尝试在所有 PDF 解析指标上取代专用工具，也不把目标限定为某个领域的单一数据库。它聚焦的是已有方案之间缺失的一层：

> 把文献中的结果候选变成带细粒度证据、标准化字段、可执行 acquisition path、确定性验证结果、质量等级和许可状态的数据样本。

系统采用“**模型生成候选，工具执行路径，规则控制入库，专家处理难例**”的混合架构。这样既利用 LLM/VLM 对复杂语义和长尾版式的适应能力，又把单位换算、数值比较、路径合法性、文献级切分和许可门禁放在可测试的确定性组件中。

## 综述绘图优化方案

综述绘图应当直接回答研究问题，而不是在调研完成后再做装饰。建议建立一份统一的 `literature_matrix`，每篇工作一行，至少编码：年份、领域、输入模态、解析器、抽取对象、是否使用 LLM/VLM、是否 agent 化、证据粒度、验证方式、人工参与、数据规模、指标、代码/数据可用性和主要限制。所有综述图都从这份表自动生成。

### 建议的核心图组

| 图 | 要回答的问题 | 数据字段 | 推荐形式 |
|---|---|---|---|
| 技术演化时间线 | 领域如何从规则抽取演化到多模态智能体？ | 年份、路线、里程碑能力 | 分层时间线/河流图 |
| 方法分类图 | 现有工作处于完整流程的哪一段？ | 输入、解析、抽取、验证、输出 | taxonomy 树或泳道图 |
| 系统能力矩阵 | 哪个系统覆盖文本、表格、图、证据和验证？ | 能力布尔值/等级 | 带注释热力图 |
| 数据流与证据链图 | 原始文献如何变成最终数据？ | stage、artifact、provenance | Sankey/流程图 |
| 性能—成本—可审计性图 | 高准确率是否伴随高成本或低可解释性？ | 指标、成本、延迟、审计等级 | 气泡图/Pareto 图 |
| 领域与模态分布图 | 研究是否集中在少数领域和模态？ | 学科、文本/表/图/公式 | 堆叠柱状图 |
| 评价指标覆盖图 | 现有评测关注字段准确率还是可复现性？ | precision/recall/F1/path/license 等 | UpSet 图或热力图 |
| 失败模式图 | 当前系统主要错在哪里？ | OCR、结构、语义、单位、证据、许可 | Pareto 柱状图 |
| ProvSci 定位图 | 本项目相对现有方案新增什么？ | 全链路能力 | 对比矩阵/二维定位图 |

### 绘图质量规范

- 每张图先写一句要验证的命题，再决定图形；不能用图替代结论。
- 主图只保留支持结论的维度，完整数据和补充图放附录。
- 颜色表达同一种语义，采用色盲友好配色；类别不依赖颜色单独区分。
- 轴、单位、样本量、缺失值、统计口径和数据截止日期必须明确。
- 图中每个系统或数据点可回链到文献表中的唯一 ID 和来源。
- 综述编码由两轮检查完成：字段定义校准与抽样复核；争议项保留备注。
- 优先使用脚本生成 SVG/PDF，同时保留 CSV/JSON 和绘图脚本，保证修改数据后可一键重绘。
- 不把不同数据集、不同任务定义或不同容差下的 F1 直接排序；必要时只做定性等级对比。

## 希望实现的完整功能蓝图

下面按用户任务的完整生命周期列出目标能力。标记为“当前”的能力已在 v0.3 形成基线；其余为计划能力，不能在汇报中表述为已经完成。

### A. 任务定义与项目管理

- 用自然语言、字段模板或已有 schema 定义抽取目标、范围和排除条件。
- 将任务转为机器可检查 contract：目标实体、属性、单位、容差、证据粒度、许可要求和验收阈值。
- 支持一次性任务、批量文献任务、持续增量监测和历史版本重跑。
- 保存配置、模型/解析器版本、随机种子、时间戳、输入 hash 和运行环境。
- 估算文献量、token、运行时间、调用成本和人工复核工作量。

### B. 文献发现、去重与获取

- 对接 Crossref、OpenAlex、PubMed、领域数据库与用户本地语料。
- 支持关键词、布尔式、引用网络、相似文献和主动学习式检索。
- DOI、PMID、标题和内容 hash 多级去重；识别预印本与正式版关系。
- 记录检索式、命中、筛选原因、全文可用性和 PRISMA 风格流转统计。
- 检查开放获取、许可证、使用范围与可再分发性；限制材料不进入公开导出。

### C. 多格式文档解析（部分当前）

- 当前支持 JSON、CSV、TSV、HTML、Markdown、纯文本、XLSX、JATS，以及系统 `pdftotext` PDF 基线。
- 计划接入 Docling/GROBID 等布局感知解析器，统一生成 document package。
- 检测原生/扫描 PDF，路由至文本解析、OCR 或 VLM；保存 OCR 置信度。
- 恢复标题、摘要、章节、段落、列表、公式、表格、图、图注、脚注和参考文献。
- 保存页码、字符 span、表格行列、bbox、解析器版本与原始文件 hash。
- 将正文与补充材料、图表与图注、引用标记与参考文献关联。

### D. 结果候选挖掘（部分当前）

- 当前支持表格数值、正文测量值、均值±误差和关系三元组候选。
- 抽取实体、属性、数值、单位、误差、区间、比较、显著性和置信区间。
- 抽取样本、对照、剂量、时间、温度、pH、设备、批次和实验方法等条件。
- 从图中识别坐标轴、单位、图例、曲线、柱、点和误差线，并保留估读误差。
- 从公式抽取变量定义、输入参数和输出关系，生成可安全执行的表达式。
- 对跨段落、跨表格、正文—补充材料证据执行共指与对齐。
- 同一结果的多处表述聚类，保留一致、互补或冲突关系。
- 允许领域插件提供术语表、ontology、抽取模板和专用验证器。

### E. 数据处理与标准化（部分当前）

- 保存 `raw_value`、解析值、标准值和每一步转换，禁止静默覆盖。
- 数字解析、科学计数法、区间、近似值、上下限、均值和误差类型识别。
- 单位规范化、维度检查与换算；处理温标、浓度、百分比和复合单位。
- 实体消歧、同义词归并、缩写解析、数据库 ID 对齐与 ontology 映射。
- 表格宽长转换、层级表头恢复、脚注传播和缺失值语义区分。
- 异常值、重复值、冲突值、不可比口径和跨文献尺度差异检测。
- 有效数字、容差和误差传播策略随任务类型配置。

### F. 分类、标注与数据建模（部分当前）

- 当前支持任务类型、证据层级、质量层级与失败模式等核心字段。
- 对领域、任务类型、模态、结果类型、难度、许可和敏感性分类。
- 生成 numeric QA、table lookup、relation、comparison、formula reasoning 和拒答样本。
- 标注问题、标准答案、显示答案、单位、容差、证据定位和必要上下文。
- 生成正例、困难负例、证据不足例、冲突例和路径污染测试例。
- 支持数据卡、样本卡、批次卡和字段级修订历史。

### G. Provenance 与可执行路径（当前核心）

- 每个结果保存 `doc_id -> evidence locator -> transformation -> answer` 链路。
- acquisition path 只允许白名单动作，显式声明参数、输入依赖、中间输出和版本。
- 路径动作覆盖定位表格单元格/文本 span、解析数值、单位转换、聚合、比较与公式计算。
- 清空标准答案后，从原始证据重新执行路径，得到独立的 replay answer。
- 生成样本级 lineage 图和运行日志，允许人工回看每一步。

### H. 验证、质量门禁与不确定性（当前核心）

- 当前可检查路径合法性、依赖完整性、数值容差、单位兼容性、证据存在性和语义门禁。
- 区分解析置信度、模型置信度、规则验证结果和专家判断，避免合成一个虚假总分。
- 对文本、表格、图和跨模态结果采用不同验证策略。
- 执行交叉来源一致性、正文—补充材料一致性和重复实验一致性检查。
- 对高风险或低置信样本启用双模型/双解析器复核，但最终仍以可检查证据为准。
- 输出失败原因、受影响字段和建议修复动作；失败样本进入重试或人工队列。

### I. 人工复核与持续学习

- 按风险、信息增益和预计修复成本排序复核队列。
- 审核界面并排展示原文证据、结构化字段、路径步骤、验证结果和冲突来源。
- 支持接受、修改、拒绝、标记许可问题和请求重新解析。
- 保存审核者、时间、字段级差异和理由，形成可审计修订记录。
- 从修订样本生成规则测试、few-shot 示例或标注集，但版本升级后必须回归评测。

### J. 数据集管理、分析与综述可视化（部分当前）

- 当前支持 Gold/Silver、人审队列、JSONL 输出、文献级切分和严格 benchmark。
- 支持数据集版本、增量合并、去重、冻结、回滚和差异比较。
- 以 `doc_id` 分割 train/dev/test，检测引用网络和近邻问题导致的泄漏。
- 仪表板展示文献覆盖、领域/模态/单位分布、产出率、失败率和许可覆盖。
- 从同一结构化结果生成综述表、趋势图、证据网络、森林图/效应图（条件满足时）和交互式过滤视图。
- 图上数据点可回链到样本、证据和原文；导出图时同时导出数据与生成配置。

### K. 输出、接口与集成

- 导出 JSONL、CSV、Parquet、知识图谱和面向模型训练的标准数据格式。
- 提供 CLI、Python API、批处理 manifest、REST API 与工作流事件接口。
- 生成可读研究报告、方法附录、数据字典、质量报告和 PRISMA 风格流程记录。
- 对接对象存储、任务队列、数据库、标注平台和实验追踪系统。

### L. 安全、许可、隐私与运维

- 内容 hash、不可变输入、运行 manifest 和依赖版本保证可重复构建。
- 密钥与原始受限文献不写入仓库；导出前执行许可证和敏感信息门禁。
- 对模型输出做 schema 校验、注入隔离和工具白名单限制。
- 监控吞吐、延迟、费用、错误、重试、数据漂移和质量回归。
- 支持本地/私有部署、最小权限、审计日志和按项目隔离数据。

## 近期实现优先级

### P0：先把“可信闭环”做扎实

1. 固化真实开放文献 benchmark，并增加人工标注的小型 Gold 集。
2. 把表格数值抽取的表头、脚注、条件绑定和单位处理做成强基线。
3. 让每条 Gold 样本都能从证据定位独立 replay，并报告 Path Reproducibility。
4. 完善 human review 输出和失败案例分析。
5. 建立 `literature_matrix` 与脚本化综述图生成流程。

### P1：补齐科学 PDF 与多模态

1. 接入布局感知 PDF 解析器，保存 bbox 和解析器对比结果。
2. 增加图表筛选、图例/坐标轴解析和 VLM 图数据抽取。
3. 对正文、表格、图和补充材料进行结果级对齐与冲突检测。
4. 选一个具体学科建立领域 schema、术语表和端到端 benchmark。

### P2：形成可用的数据生产系统

1. 增加检索、增量运行、复核界面、数据集版本和 API。
2. 建立成本—质量路由，小模型/规则处理简单样本，大模型处理难例。
3. 支持多人审核、一致性统计、主动学习和回归评测。
4. 通过持续运行验证吞吐、可靠性、可维护性和许可合规。

## 研究评价框架

不能只用“抽取准确率”评价整个智能体。建议至少报告：

- **文档层**：解析成功率、结构/表格恢复率、bbox 或定位准确率；
- **字段层**：precision、recall、F1、数值误差、单位准确率、条件完整率；
- **证据层**：Evidence Precision/Recall、定位粒度、证据充分性；
- **路径层**：Path Validity、Path Reproducibility、重放结果一致率；
- **样本层**：问题独立可答率、语义正确率、去重后有效样本数；
- **数据集层**：文献泄漏率、领域覆盖、模态覆盖、许可覆盖、Gold Yield；
- **系统层**：每篇耗时、每个有效样本成本、失败恢复率、人工复核时间；
- **鲁棒性**：版式变化、OCR 噪声、单位歧义、跨领域迁移和对抗性证据表现。

所有指标都应同时给出总体值、按文献/模态/领域分组值、置信区间或样本量，以及失败案例，而不是只展示最佳平均分。

## 参考项目与资料

- [GROBID](https://github.com/kermitt2/grobid)：科学 PDF 到结构化 TEI、引用与版面坐标的成熟基线。
- [Docling](https://github.com/docling-project/docling)：多格式文档统一表示、OCR/表格/结构化抽取工具链。
- [FAIR and Interactive Data Graphics from a Scientific Knowledge Graph](https://www.nature.com/articles/s41597-022-01352-z)：知识图谱、SPARQL 与 Vega-Lite 结合的可追溯科学可视化思路。
- [Agent-based multimodal information extraction for nanomaterials](https://www.nature.com/articles/s41524-025-01674-7)：科学图表多模态抽取与 agent 化方案及其复杂图形上的局限。
- [A comprehensive large-scale biomedical knowledge graph for AI-powered data-driven biomedical research](https://www.nature.com/articles/s42256-025-01014-w)：大规模生物医学文献信息抽取、知识整合与严格评测案例。
- [Verification and execution of the scientific literature via chemputation augmented by large language models](https://www.nature.com/articles/s42004-026-01993-w)：从化学文献抽取知识并走向机器可执行与验证的案例。

> 资料清单用于建立技术版图，不代表这些工作的指标可直接横向比较；正式综述应记录检索日期、纳排标准、任务定义、数据集和评价口径。

## 为什么做 ProvSci

科学数据后训练的瓶颈不只在模型能否生成答案，也在于训练样本是否有可靠来源、清晰变换和可复算结果。ProvSci 将数据生产拆成多个可以独立测试的环节：

- **Mine**：从文本、表格和后续的图表中发现可用结果。
- **Process**：统一数字、单位、条件、字段和文档元数据。
- **Classify**：识别任务类型、学科、数据层级、难度、许可和失败模式。
- **Annotate**：生成问题、答案、证据定位和结构化获取路径。
- **Verify**：用确定性工具重跑路径，不依赖“答案看起来像真的”。
- **Curate**：去重、许可过滤、质量分层、文献级切分并写入数据集。

这套设计既服务于数据结果挖掘，也为后续的 path-supervised scientific reasoning 提供训练数据基础。

## 目标用户与核心工作流

### 目标用户

- 需要从论文、实验报告和补充材料中批量整理数据的科研团队
- 需要构建科学问答、数值推理和工具调用训练集的模型团队
- 需要审计每个数据点来源和变换过程的数据工程/合规团队
- 需要分析数据质量、结果分布和可复现率的项目负责人

### 一条结果的生命周期

```text
原始文献
  -> 规范化文档包（页码、段落、表格、图、公式、hash、许可）
  -> 候选结果（claim + evidence locator）
  -> 数据处理（数字/单位/条件/字段标准化）
  -> 任务标注（numeric_qa / table_lookup / relation / ...）
  -> acquisition_path（白名单工具步骤）
  -> verifier 重跑
  -> Gold / Silver / Bronze / Corpus-Raw
  -> train/dev/test（按文献 doc_id 隔离）
```

## 功能蓝图

ProvSci 的长期目标是通用的科研结果数据智能体。下面的功能按数据生命周期组织，v0 只实现其中最小可验证子集。

### 1. 数据接入与文档理解

- 支持 PDF、HTML、Markdown、纯文本、CSV、Excel、JSON 和补充材料压缩包
- 记录 DOI、标题、作者、年份、来源 URL、下载时间、文件 hash 和版本
- 解析页码、段落、章节、表格、表注、图注、公式和补充材料引用
- 保留版面坐标 bbox，允许后续回到原文核验
- 识别扫描 PDF 并进入 OCR 队列，保留 OCR 置信度
- 统一编码、数字格式、希腊字母、上下标、科学计数法和特殊单位
- 记录解析器版本，保证同一文档可重复重建

### 2. 数据结果挖掘

- 从表格单元格抽取数值、单位、误差、范围和显著性标记
- 从正文抽取“升高/降低/大于/小于/相关/优于”等比较关系
- 从方法和结果段落抽取实验条件、样本、对照、时间点和测量指标
- 从公式和给定参数生成可计算候选
- 从图注和图表中定位潜在数据点，v1 接入读图工具
- 将同一结果在摘要、正文、表格、图和补充材料中的表述对齐
- 生成结果级候选，而不是直接把整篇文献变成不可审计的文本摘要

### 3. 数据处理与标准化

- 数值解析：整数、小数、科学计数法、约数、区间、均值 ± 误差
- 单位标准化与换算：质量、体积、浓度、温度、时间、比例等
- 字段标准化：样本名、化合物名、基因/蛋白名、实验指标和条件字段
- 条件结构化：温度、pH、剂量、时间、缓冲液、设备和实验批次
- 误差传播、有效数字和容差策略
- 缺失值、异常值、重复值和矛盾值检测
- 表格转长表/宽表、列类型推断和 schema 映射
- 保留 raw value 与 normalized value，禁止无记录的覆盖式清洗

### 4. 分类与路由

- 任务类型：`numeric_qa`、`table_lookup`、`relation`、`mcq`、`open_reason`
- 数据模态：文本、表格、图、公式、补充材料
- 学科与子领域分类，可接本体和受控词表
- 结果类型分类：测量值、比较关系、预测值、参数、条件、统计量
- 难度估计：步骤数、单位转换、跨证据引用、模型通过率
- 许可分类：可公开、仅内部研究、限制未知、不可派生
- 质量路由：自动入 Gold、进入 Silver、人工复核、丢弃
- 失败模式：OCR 低置信、单位歧义、问题不充分、证据冲突、路径不可执行等

### 5. 结构化标注

- 生成独立可作答的问题，保留必要条件，不泄漏表格答案以外的捷径
- 标注标准答案、显示答案、规范化值、单位、容差和置信度
- 标注证据页码、表号、行列、段落 span 和可选 bbox
- 生成有序 acquisition path，并记录工具、参数、输出和依赖关系
- 支持正例、负例、拒答例和路径污染例
- 支持人工修订、字段级审阅和修订历史
- 生成数据卡、样本卡、批次卡和可追溯审计日志

### 6. 验证与质量门禁

- 重新执行路径，比较重算结果与标准答案
- 检查路径动作是否在白名单中、参数是否完整、依赖是否存在
- 对数值执行绝对/相对容差比较，对单位执行维度兼容性检查
- 对关系题执行规则校验，对公式题执行安全表达式求值
- 检查 evidence 与 acquisition path 是否同时存在
- 检查许可是否允许衍生训练或再分发
- 统计 Path Reproducibility、Evidence Precision、Fabrication Rate、Yield 和 License Coverage
- 验证失败时保留样本与 failure_mode，进入 regenerate 或 human review 队列

### 7. 数据集管理与分析

- Gold：路径验证通过且许可清晰
- Silver：有证据但路径弱、许可待确认或需要人工复核
- Bronze：仅模型生成、无可靠 provenance，默认不进入主训练集
- Corpus-Raw：原始全文和结构化科学语料，与 QA 数据集分开管理
- 以 `doc_id` 为单位切分 train/dev/test，防止同文献泄漏
- 近邻题去重、同证据多问检测和跨版本合并
- 统计文献覆盖、领域分布、单位分布、失败原因和每文献产出
- 输出 JSONL/Parquet 数据集与可复现运行清单

### 8. 智能体交互与协作

- 自然语言指定研究问题、数据范围和目标字段
- 预览候选结果后批量接受、驳回或送人工复核
- 追问“这个数来自哪里”“换成 nM”“哪些样本可复算”
- 展示从原文到答案的证据链和每一步工具输出
- 支持任务队列、暂停/恢复、失败重试和人工接管
- 为每次运行生成 run id、配置快照、模型版本和工具版本

## v0 实现范围

本仓库当前用一个规范化 JSON 文档包模拟解析器输出，先将核心闭环做成可测试的纯 Python 模块：

```text
src/provsci/
  adapters.py     # JSON/CSV/HTML/text/XLSX/JATS/PDF 基线输入适配器
  models.py       # 文档、候选、样本、path 和验证结果模型
  classify.py     # 结果类型、模态、难度和处理操作标注
  miner.py        # 表格数值候选挖掘与任务/证据/path 生成
  path.py         # 白名单 acquisition path 执行器
  verifier.py     # 确定性结果验证
  pipeline.py     # ingest -> mine -> verify -> curate
  batch.py        # 多文献处理、文献级 split、重复检测
  evaluate.py     # benchmark manifest 和指标输出
  agent.py        # 可直接调用的 run/ask agent facade
  cli.py          # 命令行入口
```

v0 的支持动作：

- `extract_table_cell`
- `read_text_span`
- `parse_number_unit`
- `extract_number_unit`
- `unit_convert`
- `arith_eval`
- `extract_relation`

任何不在白名单中的动作都会失败，不能通过 verifier。

每个样本还会显式记录 `task.classification` 和 `processing`：当前规则分类器区分测量值与比较关系，记录证据模态、任务难度、执行过的处理操作，并保留原始值、标准化值和可选的 uncertainty。文本结果会优先绑定 metric/entity；关系结果会绑定 subject/predicate/object。缺少这些语义字段的样本不能进入 Gold，会进入 `human_review.jsonl`。

## 快速开始

项目只依赖 Python 3.9+ 标准库。

```bash
PYTHONPATH=src python3 -m provsci.cli run \
  --input examples/documents/biophysics_demo.json \
  --output work/demo-run
```

运行后会生成：

- `work/demo-run/all.jsonl`：所有挖掘出的样本及验证结果
- `work/demo-run/gold.jsonl`：验证通过且许可可用的 Gold 样本
- `work/demo-run/silver.jsonl`：未满足 Gold 门禁的样本
- `work/demo-run/human_review.jsonl`：需要人工处理的语义不完整、重复或安全风险样本
- `work/demo-run/summary.json`：样本数、通过率和失败模式

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

也可以直接运行：

```bash
./scripts/run_demo.sh
./scripts/run_tests.sh
```

运行一次后，用自然语言查询已验证结果：

```bash
PYTHONPATH=src python3 -m provsci.cli ask \
  --results work/demo-run \
  --question "Compound B IC50" \
  --limit 3
```

`ask` 只返回 `verification.status=pass` 的样本，并保留 evidence、acquisition path 和 verification trace；当前是透明词法检索基线，后续可替换为检索/LLM 排序器，但不能绕过 verifier。

运行 benchmark 快捷脚本：

```bash
./scripts/run_benchmark.sh
```

运行多格式 benchmark：

```bash
PYTHONPATH=src python3 -m provsci.cli evaluate \
  --manifest examples/benchmark/manifest.json \
  --output work/benchmark
```

benchmark 会输出候选数/Gold 数/Silver 数一致率、claim precision/recall、Path Reproducibility、evidence/license coverage、重复 sample ID 和文献级 split 信息。当前包含 4 个本地 fixture 文档和 1 篇 CC-BY PMC/JATS 真实论文、23 条人工整理结果 claim；它仍不是大规模科学 leaderboard，但能对真实开放论文做严格的 value/unit/metric/entity 和 relation triple 对照。
真实 smoke 脚本会额外读取 4 篇 CC-BY PMC/JATS 论文，当前 result-focused 运行结果为 201 条候选、201 条 Gold、0 条 review、Path Reproducibility 1.0；该 smoke 主要验证运行稳定性和审计不变量，严格语义分数仍以带人工 claim 的 manifest 为准。

当前策略：`table_only` 是窄表格基线，`full` 是高召回但可能有噪声的对照，`result_focused` 是默认策略，会利用 JATS section 路由、条件值过滤和语义质量门禁；`multimodal` 额外读取 JATS figure alt-text，并通过 `figure` evidence 和 `read_figure_alt_text` path 做图文结果扩展。

## 输入文档包

解析器暂时不属于 v0 核心。输入采用稳定的中间格式，后续 PDF/HTML 适配器只需要产出同样结构：

```json
{
  "doc_id": "doi:10.1234/demo",
  "title": "A reproducible numeric result",
  "year": 2024,
  "license": "CC-BY-4.0",
  "local_path": "raw/demo.pdf",
  "paragraphs": [
    {"id": "p1", "page": 1, "text": "..."}
  ],
  "tables": [
    {
      "id": "Table 1",
      "page": 2,
      "caption": "Measured values",
      "columns": ["Sample", "IC50"],
      "rows": [
        {"Sample": "Compound A", "IC50": "12.5 uM"}
      ]
    }
  ]
}
```

完整逻辑样本 schema 见 [`schemas/sample_schema.json`](schemas/sample_schema.json)。schema 中的硬约束是：没有 evidence、没有 acquisition path 或验证状态不是 `pass` 的样本不能进入 Gold；数据切分必须按文献隔离。

## 样本示例

```json
{
  "id": "provscidemo-c1",
  "source": {
    "doc_id": "doi:10.1234/demo",
    "title": "A reproducible numeric result",
    "year": 2024,
    "license": "CC-BY-4.0",
    "local_path": "raw/demo.pdf",
    "page_span": [2, 2],
    "source_hash": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "task": {
    "type": "numeric_qa",
    "subject": "biophysics",
    "question": "What is the reported IC50 for Compound A?",
    "answer": {"value": 12.5, "unit": "uM", "display": "12.5 uM"},
    "classification": {"result_type": "measurement", "modalities": ["table"], "task_family": "numeric_qa", "difficulty": 0.31, "classifier": "rules_v0.1"}
  },
  "evidence": [{
    "modality": "table",
    "locator": {"page": 2, "table_id": "Table 1", "row": "Compound A", "col": "IC50"},
    "span_text": "12.5 uM"
  }],
  "acquisition_path": [{
    "step_id": 1,
    "action": "extract_table_cell",
    "tool": "table_parser",
    "args": {"page": 2, "table_id": "Table 1", "row_key": "Compound A", "col": "IC50"},
    "output": "12.5 uM",
    "depends_on": []
  }, {
    "step_id": 2,
    "action": "parse_number_unit",
    "tool": "number_unit_parser",
    "args": {"value_from": 1},
    "output": {"value": 12.5, "unit": "uM"},
    "depends_on": [1]
  }],
  "processing": {"operations": ["table_cell_extraction", "number_unit_parsing"], "raw_value_preserved": true, "normalization": "number_unit_v0.1"},
  "verification": {"status": "pass", "evidence_checked": true, "tolerance": {"rel": 0.02, "abs": null}},
  "quality": {"needs_human_review": false, "failure_mode": null},
  "split": "train"
}
```

## 质量指标与验收目标

| 指标 | 定义 | v0/v1 目标 |
| --- | --- | --- |
| Path Reproducibility | 按 path 重跑后与答案一致的比例 | Gold >= 85% |
| Evidence Precision | 人审证据确实支持答案的比例 | 抽检 >= 90% |
| Fabrication Rate | 无证据或证据不支持却入库的比例 | <= 2% |
| License Coverage | 许可字段完整且可判定的比例 | 100% 进入 Gold |
| Doc-level split integrity | 同一 doc_id 是否跨 split | 0 泄漏 |

## 路线图

### A0：Schema 与验证器

- [x] 冻结样本 schema 和白名单动作
- [x] 表格数值和文本关系结果的端到端闭环
- [x] Gold/Silver gate、失败模式和 JSONL 输出
- [x] JSON/CSV/HTML/XLSX 基线适配器与文献级 benchmark
- [ ] 100 条人工金牌样本与误差分析

### A1：单垂直域扩展

- [ ] 接入 Docling/GROBID/TATR/Nougat 的可选 PDF 解析路径
- [ ] 选择物理实验数值或生物医学剂量-效应子域
- [ ] 支持文本关系、实验条件和补充材料
- [ ] 20 -> 200 篇文献，至少 300 条 Gold

### A2：规模化与人工协同

- [ ] 候选审阅工作台与批量复核
- [ ] 去重、文献级切分和数据质量看板
- [ ] 失败样本自动重写/重试
- [ ] 1,000 条以上 Gold，抽检复现率 >= 85%

### B/C：推理模型与基础模型

- [ ] Path-aware SFT：答案 + 证据 + 路径
- [ ] Verifier-consistent RL 与拒答校准
- [ ] 许可清晰的科学语料配比与小规模 CPT

## 仓库协作说明

目标远程仓库为 [Simon-byte-png/ProvSci](https://github.com/Simon-byte-png/ProvSci)。当前版本先作为一个独立、可迁移的本地工程包保存，远程仓库同步不影响本地运行。接入远程仓库时，应保留已有改动，并按以下顺序合并：

1. 确认远程仓库的主分支、Python/Node 技术栈和已有数据目录。
2. 将本 README、`schemas/`、`src/provsci/`、`tests/` 和 `examples/` 合并到对应 ownership boundary。
3. 把当前 JSON 中间格式适配到仓库现有的 PDF/HTML ingest 层。
4. 用真实的 10 篇许可清晰文献跑出第一批失败分析，再决定接入模型服务。

完整的项目战略规划归档在 [`docs/provsci-plan-v0.1.md`](docs/provsci-plan-v0.1.md)；论文和开源项目比较见 [`docs/research-comparison.md`](docs/research-comparison.md)。
外部 parser/agent 的本地可执行性和公平对照边界见 [`docs/external-baseline-feasibility.md`](docs/external-baseline-feasibility.md)。

## 许可与合规

代码与样本数据的许可必须分开管理。每条样本至少记录原文许可、是否允许衍生训练、是否允许再分发和审计时间。内部可训练集合不等于可公开发布集合；NC 内容默认只用于内部研究和报告，不重新许可。

## 命名

- 数据引擎：`SciHarvest`
- 推理模型：`ProvSci-Reason`
- 科学基座模型（中长期）：`ProvSci-Base`

当前项目只使用 `ProvSci` / `SciHarvest` 作为数据智能体和数据引擎名称。
