# AI4S Biomedical Agent 竞品调研（合集 · 面向 BioClaw 改进）

> 日期：2026-07　|　产品：BioClaw（chat.bioclaw.tech）　|　单文件合集，便于下载分享。

> 本合集由 6 个分文件汇总而成。评分表（第 5 部分）为**公开能力预估、非亲测**，请用第 2 部分题集实跑后校准。


## 目录

- 第 0 部分 · 主报告（结论先行）
- 第 1 部分 · 产品 Mapping 总表
- 第 2 部分 · 评测框架（Rubric + 测试题集）
- 第 3 部分 · 国际竞品详析
- 第 4 部分 · 国内竞品详析
- 第 5 部分 · BioClaw 改进建议



<div style="page-break-before: always;"></div>

---


# 第 0 部分 · 主报告（结论先行）

## AI4S Biomedical Agent 调研报告（面向 BioClaw 改进）

**日期**：2026-07　|　**产品**：BioClaw（chat.bioclaw.tech）　|　**目的**：摸清 AI4S 产品当前能做什么，并给出 BioClaw 的改进方向。

> 本报告由 5 个文件组成，本文件是总览：
> - `00_主报告`（本文，结论先行）
> - `01_产品Mapping总表`（赛道结构 + 对照表 + 能力矩阵）← mentor 要求①
> - `02_评测框架_rubric与测试题集`（打分标准 + 3 难度×8 类型测试题）← mentor 要求②
> - `03_国际竞品详析` / `04_国内竞品详析`（逐产品事实卡片）
> - `05_bioclaw改进建议`（预估评分 + 分优先级改进）← mentor 要求③

---

### 一、一页结论（TL;DR）

1. **赛道分四层**：L1 文献/单点工具 → L2 通用生信 chat agent → L3 垂域深度 agent → L4 自主 AI 科学家。**BioClaw 在 L2**。
2. **AI4S 现在能做到什么**（2026 现状）：
   - L2 已成熟：自然语言→跑生信工具→出图/表/notebook（BioClaw、Biomni、AutoBA 都能做）。
   - L4 正在突破："AI 科学家"（Kosmos、K-Dense、Biomni Lab、英矽 DORA）能自主多轮闭环、读上千篇文献、写数万行代码、生成**新假设**、约 **80% 准确**、单 run ≈ 数月人力。
   - 干湿闭环落地：天鹜、深势、英矽、晶泰已把 AI 设计接到**机器人湿实验**。
   - **共同天花板**：准确率仍 ~80%（1/5 结论不可靠），"超越人类"多为自述基准，代码执行有安全风险，**人类监督不可或缺**。
3. **BioClaw 的位置**：最易用（多 IM+零安装）、最可复现（默认出 notebook）、**唯一做群聊多人协作研究**；但**研究深度、防幻觉溯源、benchmark 背书**弱于第一梯队。
4. **最直接的竞争**：同生态 ClawBio/Claw4Science/OmicClaw、国产 OmicOS、国际 Biomni；上游 Anthropic 官方 Claude for Science 亲自下场（同技术范式）。
5. **改进主线**：短期"跑分+溯源+云版"补信任 → 中期"planner/critic 双环+记忆层"补深度 → 长期"群聊协作+湿实验多模态"筑护城河。

---

### 二、mentor 三项要求的落点

| mentor 要求 | 对应交付 | 关键结论 |
|---|---|---|
| ① 国内外产品 mapping（Omicos/天鹜/Claude science/Biomni/Edison/Kdense…）| `01` + `03` + `04` | 已覆盖 30+ 产品，画出四层赛道结构与能力矩阵；辨清 Omicos=OmicOS、phylo=Biomni 商业公司、Edison=Kosmos |
| ② AI 生成不同难度/类型 prompt + rubric 打分表 | `02` + `05` | 已产出 3 难度×8 生物类型共 24 题 + 8 维 rubric + 记录模板；`05` 给出预估评分表（待实测校准）|
| ③ 指向性 report：bioclaw 能改哪里 | `05` + 本文 | 10 条分优先级建议，核心是"补深度+溯源、守住协作/易用护城河"|

---

### 三、关键辨析（避免踩坑）

- **Omicos** = **OmicOS（源境解码）**，闭源组学 AI 科学家；其开源底座是 **OmicVerse**；姊妹项目 **OmicClaw** 与 BioClaw 形态高度重合 → **最直接国产竞品之一**。
- **Biomni 的 "phylo"** = 从 Biomni 孵化的**商业公司 Phylo**（旗舰 Biomni Lab / IBE，phylo.bio 可免费注册），不是版本代号。
- **Edison** = **Edison Scientific**，产品是 **Kosmos**（FutureHouse 分拆），前 6 run 免费后 $200/run。
- **K-Dense** = Biostate AI 出品，Gemini 2.5 Pro 基座，BixBench 29.2%（"HLE 生物医学第一"**未证实**）。
- **"国产 Claude science"** = 多指 **OpenClaw/NanoClaw agent 生态**在生物医学的衍生（BioClaw 自己就是其中之一；底座 OpenClaw 非国产，生物医学层多为华人/中国团队）。
- 用户提到的 **"智海""Chat2Bio"** 检索**未找到**确切同名产品，疑记忆偏差，建议补出处。

---

### 四、下一步建议（给你执行）

1. **实测校准评分表**：拿 `02` 的 8 题基准集，注册 Biomni Lab（免费）、phylo.bio（免费 pro）、FutureHouse（免费）、K-Dense Web、深势玻尔（限免）实跑，把真实分数填进 `05` 的表，替换预估值。BioClaw 用你们自己网页版跑同一批题。
2. **重点抓 L3 难题**：L1/L2 各家都能做，拉开差距的是 L3（GEO 端到端、多组学整合、假设生成+实验设计）。这几题最能暴露 BioClaw 与"AI 科学家"的差距，也最能指导改进。
3. **先落地 P0 三件事**：跑 benchmark、给结论加可点击溯源、押注零安装云版——三件都是低成本高回报。

---

### 五、信息可信度与存疑项

- 本报告基于公开 web 检索（官网/bioRxiv/GitHub/知乎/公众号/36氪/机器之心等），关键事实交叉验证。
- 多个官网（bioclaw.tech 部分、matvenus.com、部分 NCBI）受网络策略限制，细节来自搜索索引/镜像，建议人工复核一手信息。
- 未证实项已在各文件标注（K-Dense HLE 成绩、Kosmos 基座、多家定价、"智海/Chat2Bio"）。
- `05` 的评分表为**专家预估非亲测**，务必实跑后校准再对外用。


<div style="page-break-before: always;"></div>

---


# 第 1 部分 · 产品 Mapping 总表

## AI4S Biomedical Agent 产品 Mapping 总表

> 时间：2026-07。价格/版本以官网为准，标注"?"为未查到公开信息。
> 阅读方式：先看"一、形态分层图"理解赛道结构，再看"二、总对照表"逐项对比，"三、按任务能力矩阵"看谁能做什么。

---

### 一、形态分层图（赛道结构）

```
                     能力深度 / 自主性  ↑
                                        │
 【L4 自主 AI 科学家】                   │  Kosmos/Edison ·  Biomni Lab/Phylo · K-Dense
 (world model / 多轮闭环 / 生成新假设)    │  英矽 DORA · 深势 SciMaster · FutureHouse Robin
 ────────────────────────────────────────┼─────────────────────────────────────────────
 【L3 垂域深度 Agent】                    │  天鹜 MatwingsVenus(蛋白) · 英矽 ChatPandaGPT(药)
 (单一领域深 + 自研模型/数据 + 干湿闭环)   │  百图 AIGP · OmicOS/OmicClaw(组学)
 ────────────────────────────────────────┼─────────────────────────────────────────────
 【L2 通用生信 Chat Agent】  ★★★★★         │  ★ BioClaw ★ · Biomni(开源版) · AutoBA
 (自然语言→计划→跑工具→出可复现结果)      │  BioMANIA · CellAgent · BioMaster · ClawBio
 ────────────────────────────────────────┼─────────────────────────────────────────────
 【L1 文献/单点工具】                     │  Elicit · Consensus · Scite · FutureHouse(Crow
 (文献检索/综述/引用/单任务)              │  Falcon Owl) · GPTCelltype · STORM
                                        └────────────────────────────────────────────→
                                            工具/嵌入式  ←→  平台/生态         广度
```
**★ BioClaw 定位在 L2（通用生信 chat agent）**，其独特处是"多 IM 平台交付 + 群聊协作 + 零安装网页版"，但在自主性(L4)与垂域深度(L3)上弱于第一梯队。

---

### 二、总对照表

| 产品 | 国别 | 形态层 | 核心能力 | 底层模型 | 数据/工具护城河 | 开源 | 定价 | 交付形态 |
|---|---|---|---|---|---|---|---|---|
| **BioClaw** ★ | 华人 | L2 通用生信 chat | BLAST/QC/比对/变异/单细胞/PyMOL/PubMed/凝胶图 | Claude Agent SDK（可换 OpenRouter/GPT）| 31 工具+95 技能，靠公开库 | ✅MIT | 免费(付模型费) | **多 IM 群聊+网页**，出 notebook |
| **Biomni / Phylo** | 美(Stanford) | L2→L4 | 25 领域通用；假设/协议/多组学 | Claude 默认+多商；自研 Biomni-R0 | 150 工具/105 包/59 库(商用 300+) | ✅Apache2(网页版闭源) | 网页免费/商用? | 网页 Co-pilot，出 notebook |
| **Kosmos / Edison** | 美 | L4 AI 科学家 | world model 多轮闭环，生成新假设 | 未公开 | FutureHouse 谱系积木 | ❌ | 前6run免费后 **$200/run** | 类论文报告，claim 可溯源 |
| **K-Dense / Biostate** | 美 | L4 | 分层多 agent+交叉核查抑幻觉 | Gemini 2.5 Pro | 140 skills+100 库；自有测序数据 | 半(skills 开源) | ? | Web，可发表报告 |
| **Claude for Life Sci / Claude Science** | 美(Anthropic) | L1→L3 嵌入 | 嵌 Benchling/10x；Skills for Science | Claude Sonnet 4.5 | MCP 连接器生态 | 闭(Skills 格式开放) | 企业级? | 嵌既有工具链 |
| **FutureHouse** | 美(非营利) | L1 文献群 | Crow/Falcon/Owl 文献；Robin 编排 | 多(PaperQA2);自研 ether0 | 全文文献+OpenTargets | ✅(引擎) | **免费** | Web+API |
| **OmicOS / OmicClaw** | 国产 | L2/L3 组学 | 组学 AI 科学家，多 agent+provenance | 通用 LLM+scGPT 等 | OmicVerse 开源底座 | OmicVerse✅/OmicOS❌ | 内测? | notebook+证据链 |
| **天鹜 MatwingsVenus** | 国产 | L3 蛋白垂域 | 挖酶/定向进化/从头设计/抗体+干湿闭环 | 自研 Venus 蛋白大模型 | **90 亿蛋白序列**(自研) | 学术✅/商用❌ | ? | 对话+机器人湿实验 |
| **深势 SciMaster** | 国产 | L4 通用科研 | 拆解+检索+人机协同+Uni-Lab 闭环 | 自研 Innovator | Uni-Mol+玻尔生态 | 部分 | 内测免费 | 科研 agent+干湿闭环 |
| **英矽 ChatPandaGPT+DORA** | 国产 | L3→L4 药研 | 平台 copilot+AI Scientist 写论文+机器人 | 自研+Azure | PandaOmics 知识图谱 | DORA✅ | 平台绑定 | 药研全流程 |
| **百图 AIGP / xTrimo** | 国产 | L3 蛋白 | 蛋白设计 F2P/P2P/C2P | 自研 xTrimo 2680 亿参 | xTrimoPGLM 千亿蛋白模型 | 部分开源 | 企业 | 平台+内嵌助手 |
| **Elicit/Consensus/Scite** | 美 | L1 文献 | 综述/证据/引用可信度 | 多 | 1-2 亿论文库 | ❌ | $9-49/月 | Web |

---

### 三、按生物任务能力矩阵（√真执行 / ○文本级 / ✗不支持 / — 未知）

| 任务类型 | BioClaw | Biomni | Kosmos | K-Dense | 天鹜 | OmicOS | 深势SciMaster | 英矽DORA | FutureHouse |
|---|---|---|---|---|---|---|---|---|---|
| 文献检索/综述 | √ | √ | √√ | √ | ○ | √ | √ | √ | √√ |
| 序列分析(BLAST/比对/变异) | √ | √ | √ | √ | ✗ | ○ | ○ | ✗ | ✗ |
| 转录组差异表达 | √ | √ | √ | √ | ✗ | √ | ○ | ○ | ○ |
| 单细胞/空间组学 | √ | √√ | √ | √ | ✗ | √√ | ○ | ○ | ✗ |
| 蛋白/结构生物学 | √(PyMOL/PDB) | √ | ○ | ○ | √√ | ○ | √ | ○ | ✗ |
| 化学信息学/分子设计 | ○(RDKit) | √ | √ | ○ | ✗ | ○ | √√ | √√ | ○(Phoenix) |
| 数据库整合查询 | √ | √√ | √ | √ | √ | √ | √ | √ | √ |
| 湿实验解读(凝胶图) | **√√独有** | ✗ | ✗ | ✗ | ○ | ✗ | ○ | ○ | ✗ |
| 假设生成 | ○ | √ | √√ | √ | √ | √ | √ | √√ | √ |
| 实验设计 | ○ | √ | √ | √ | √√ | √ | √ | √√ | √ |
| **干湿实验闭环(机器人)** | ✗ | ✗ | ✗ | ○ | **√√** | ✗ | **√√** | **√√** | ○ |
| 群聊多人协作交付 | **√√独有** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

**读表结论**：
- BioClaw 在 **L2 生信执行类任务（序列/QC/单细胞/可视化/文献）** 覆盖齐全且能真跑；
- **两个几乎独有的差异化点**：① 湿实验凝胶图多模态解读；② 多 IM 群聊协作交付（"人-机研究协作生态"）；
- **明显短板**：假设生成/实验设计只到"文本级"，无干湿闭环，无自研模型/数据护城河，缺自主长时程推理（L4）。


<div style="page-break-before: always;"></div>

---


# 第 2 部分 · 评测框架（Rubric + 测试题集）

## AI4S Biomedical Agent 评测框架：Rubric + 测试题集

> 用途：对 BioClaw 与各竞品用**同一套题、同一套打分标准**横向评测，产出可比的分数表。
> 建议评测方式：同一 prompt 依次投喂给每个平台，截图保存过程与结果，按下方 rubric 逐项打分（1–5 分），再计算加权总分。

---

### 一、打分维度 Rubric（每项 1–5 分）

| # | 维度 | 含义 | 1 分（差） | 3 分（及格） | 5 分（优秀） | 权重建议 |
|---|------|------|-----------|-------------|-------------|---------|
| R1 | **结果准确性** Correctness | 事实/数值/生物学结论是否正确、无幻觉 | 明显错误或编造 | 大体正确，有小瑕疵 | 完全正确、可复核 | 25% |
| R2 | **完整性与深度** Depth | 是否覆盖任务全部要点、有无洞察 | 只答一半 | 覆盖主要要点 | 全面 + 额外洞察/替代方案 | 15% |
| R3 | **真实执行能力** Execution | 是否**真跑了工具/代码**产出真实结果，而非"口头描述" | 只给文字，没跑 | 跑了但需人工补 | 端到端真实跑通、出图/出表 | 20% |
| R4 | **思考过程透明度** Transparency | 是否展示计划、工具调用、中间步骤、可审计 | 黑箱 | 部分可见 | 全程 trace + 可复核每步 | 10% |
| R5 | **可复现性** Reproducibility | 是否给出代码/notebook/环境/参数，别人能重跑 | 无 | 给了代码片段 | 完整 notebook + 环境 + 数据指针 | 10% |
| R6 | **处理时间** Latency | 从提交到拿到可用结果的耗时 | >10min 或超时 | 2–10min | <2min 且不牺牲质量 | 5% |
| R7 | **引用与可信度** Grounding | 文献/数据库结果是否有真实来源、可点击核对 | 无引用/假引用 | 有引用但不全 | 每条结论可溯源 | 10% |
| R8 | **易用性与交互** UX | 上手门槛、追问、纠错、多轮协作体验 | 难用/易崩 | 可用 | 顺滑、支持追问与纠偏 | 5% |

> 加权总分 = Σ(各维度得分 × 权重)，满分 5。可按团队关注点调整权重（例如更看重"真实执行"就调高 R3）。
> 另记录**定性字段**：① 是否出现幻觉（具体例子）；② 是否卡壳/需人工接管；③ 输出物形态（纯文本 / 图 / 表 / notebook / 报告）；④ 个人主观体验一句话。

---

### 二、测试题集（3 个难度 × 8 个生物类型）

难度定义：
- **L1 简单**：单步、单工具、事实型，几分钟内应完成。
- **L2 中等**：多步、需选择方法/参数、产出图表或结构化结果。
- **L3 复杂**：端到端 pipeline / 多组学整合 / 需推理与实验设计，考验 agent 规划与自我纠错。

> 说明：题目尽量用**公开数据**（NCBI/PDB/GEO/UniProt 的公开 ID），保证各平台都能取到同一数据、结果可比。

#### 类别 A — 文献检索与综述
- **A-L1**：检索 2023 年以来关于 "KRAS G12C inhibitor resistance" 的高影响力论文，给出 5 篇的结构化摘要（标题/期刊/年份/一句话结论/PMID）。
- **A-L2**：就 "single-cell approaches to study tumor microenvironment in pancreatic cancer" 写一段 500 字带引用的小综述，列出主要方法学分歧点。
- **A-L3**：针对 "GLP-1 受体激动剂在神经退行性疾病中的潜在作用" 做一次证据合成：检索、筛选、按证据强度分层，指出目前证据缺口与可验证的假设，并给出每条论断的可点击来源。

#### 类别 B — 序列分析（BLAST / 比对 / 变异）
- **B-L1**：将人 TP53 蛋白序列（UniProt P04637）BLAST 比对 NCBI nr，返回 top 5 hits（物种/得分/E-value）。
- **B-L2**：给定一条未知 300bp DNA 序列（可用一段公开基因片段），判断其可能来源基因与物种，并说明判断依据。
- **B-L3**：从 SRA 下载一个小的公开测序样本（如某 run accession），完成质控→比对参考→变异检出，报告关键变异并解释潜在功能影响。

#### 类别 C — 转录组 / 差异表达
- **C-L1**：给一个差异表达结果 CSV（含 log2FC、p 值），画火山图并标注 top 上/下调基因。
- **C-L2**：对一个公开 bulk RNA-seq 计数矩阵做差异表达分析（DESeq2/PyDESeq2），输出显著基因表并做通路富集（KEGG/GO）。
- **C-L3**：从 GEO 取一个 RNA-seq 数据集（给 GSE 号），从原始/计数矩阵到差异分析、富集、生物学解读，产出一份带图的可复现报告。

#### 类别 D — 单细胞 / 空间组学
- **D-L1**：解释一个已给 scRNA-seq 对象的基本 QC 指标（nGene、mito%），指出应过滤哪些细胞及理由。
- **D-L2**：对一个小的公开 scRNA-seq 数据集做标准流程（预处理→聚类→UMAP→marker 基因），给出聚类图与初步 cell type 注释。
- **D-L3**：对同一组织的 scRNA-seq + 空间转录组做联合分析思路设计并执行关键步骤，回答"某细胞类型的空间分布与某通路活性是否相关"。

#### 类别 E — 蛋白 / 结构生物学
- **E-L1**：从 PDB 取 1M17，用 PyMOL 渲染，展示配体 AQ4 周围 5Å 残基并出图。
- **E-L2**：给定一个蛋白序列，查询/预测其结构（AlphaFold DB 或结构预测），分析活性位点与关键结构域。
- **E-L3**：给一对蛋白-配体，做结合位点分析 + 简单对接/相互作用（氢键/疏水）解读，并提出 2 个可提升亲和力的突变假设及理由。

#### 类别 F — 化学信息学 / 药物
- **F-L1**：给一个 SMILES，计算基本理化性质（MW、logP、TPSA、Lipinski 是否通过）。
- **F-L2**：对一组候选分子做相似性/骨架分析，筛出最可能成药的若干个并说明依据。
- **F-L3**：针对某靶点（如 EGFR）设计一个"从已知抑制剂出发做类似物优化"的计算工作流并执行关键步骤。

#### 类别 G — 数据库查询与知识整合
- **G-L1**：查询 UniProt / KEGG / Ensembl / ClinVar 中某基因（如 BRCA1）的核心信息并结构化汇总。
- **G-L2**：整合 STRINGdb + Reactome + OpenTargets，给出某基因的互作网络、通路与疾病关联证据。
- **G-L3**：围绕一个疾病（如 ALS）跨库整合靶点证据，产出一张"靶点—证据—可成药性"排序表并说明打分逻辑。

#### 类别 H — 湿实验解读 / 实验设计 / 假设生成
- **H-L1**：上传一张 SDS-PAGE / gel 图，判断泳道质量与目标条带是否符合预期。
- **H-L2**：为"验证基因 X 在细胞系中的功能"设计一个包含对照、读出指标、样本量的实验方案。
- **H-L3**：给定一个初步观察（如"某药处理后某通路上调"），自主提出 2–3 个可验证假设，并为每个假设设计可执行的验证实验与预期结果。

---

### 三、评分记录表模板（每个平台复制一份）

| 题号 | R1准确 | R2深度 | R3执行 | R4透明 | R5复现 | R6时间 | R7引用 | R8易用 | 加权总分 | 幻觉? | 是否卡壳 | 输出形态 | 一句话体验 |
|------|-------|-------|-------|-------|-------|-------|-------|-------|---------|------|---------|---------|-----------|
| A-L1 | | | | | | | | | | | | | |
| B-L2 | | | | | | | | | | | | | |
| … | | | | | | | | | | | | | |

> 建议至少每类别各取 1 题（8 题基准集），时间充裕再补 L3 难题（最能拉开差距）。
> 每个平台跑同一批题 → 汇总成"平台 × 题目"总表 → 计算各平台各维度均分，得出雷达图。


<div style="page-break-before: always;"></div>

---


# 第 3 部分 · 国际竞品详析

## 国际 Biomedical / Life-Science AI Agent 竞品详析

> 价格与版本随时间变动，以各官网为准；标"存疑"处需官方进一步确认。

### 1. Biomni（Stanford SNAP Lab）/ Phylo
- **定位**：首个"通用型"生物医学 AI agent——LLM 推理 + 检索增强规划 + 代码执行，用自然语言把科研任务（文献、假设、协议、数据分析）委托给 AI。
- **能力覆盖**：横跨 25 个生物医学子领域（基因组/测序、单细胞、蛋白结构、CRISPR 筛选、药理 ADMET、分子克隆、GWAS、罕见病诊断、免疫等）。
- **工具生态（精确）**：基础环境 **Biomni-E1 = 150 工具 + 105 软件包 + 59 数据库**（从 ~2500 篇 bioRxiv 挖掘）。商业版 Biomni Lab 扩展至 **300+** 资源（接入 Consensus、COSMIC、Addgene）。
- **底层模型**：默认 Anthropic Claude；开源版支持多提供商；自研 **Biomni-R0**（Qwen-32B/8B 强化学习推理模型，已开源）。
- **开源**：GitHub `snap-stanford/Biomni`，Apache 2.0，7000+ 实验室社区。
- **定价**：网页版 biomni.stanford.edu 免费（禁 PHI）；商业版 Biomni Lab 定价未披露。
- **phylo 辨析**：Phylo 是从 Biomni 孵化的**商业公司**（2026-02 成立，CEO Kexin Huang，联创 Jure Leskovec、Le Cong；$13.5M 种子轮，a16z + Anthropic Anthology Fund 领投）；旗舰产品 **Biomni Lab（Integrated Biology Environment, IBE）**。phylo.bio 可免费注册体验。
- **优势**：覆盖面最广、真正通用、性能强、开源 + 免费 + 活跃社区、顶级背书。
- **局限**：以系统权限执行 LLM 生成代码（安全隐患，须沙箱）；开源版功能落后于在线版；商业版定价不透明。

### 2. Claude for Life Sciences / Claude Science（Anthropic）
- **定位**：2025-10 推出的生命科学垂直方案，把 Claude 嵌入既有实验室笔记/基因组平台/文献库，覆盖"发现→转化→商业化"；强调"活在你已有的工具里"，助手而非自主发现引擎。2026-06 推出独立工作台 **Claude Science**。
- **模型/基准**：Claude Sonnet 4.5；Protocol QA 得 0.83 > 人类 0.79。
- **集成（MCP）**：Benchling（电子实验记录、可审计回溯）、10x Genomics（自然语言单细胞）、PubMed、BioRender、Synapse、ChEMBL、Owkin、ClinicalTrials.gov 等。
- **Agent Skills for Science**：可复用 Skill（指令+脚本+资源），首个 `single-cell-qc`（scverse 最佳实践质控）。
- **定价**：无公开统一定价，企业级、经销售/云伙伴部署（客户如 Sanofi）。
- **优势**：深嵌工具链、答案可回溯审计、Skills+MCP 可复用。
- **局限**：定位"辅助提效"非自主发现；定价不透明。
- **⭐ 与 BioClaw 的直接关系**：BioClaw 底层就是 **Claude Agent SDK + Skills**，与 Claude for Science 的技术范式同源。Anthropic 官方下场做 Skills for Science，意味着 BioClaw 的"Skills 生态"叙事会直接面对官方竞争。

### 3. FutureHouse（非营利，免费平台）
- **定位**：Eric Schmidt 资助、Sam Rodriques 领衔，"造 AI 科学家"；2025-05 上线免费 Web+API。
- **Agent 家族**：
  - **Crow**：通用文献问答 API（基于 PaperQA2，读全文、带引用）。
  - **Falcon**：深度文献综述，接 OpenTargets，出长报告。
  - **Owl**（原 HasAnyone）：先例检索"是否有人做过 X"。
  - **Phoenix**（实验性）：化学合成规划/分子设计（ChemCrow 新版，易出错）。
  - **Finch**：数据分析/差异表达/假设生成（闭测）。
  - **Robin**：编排 Crow+Falcon+Finch 端到端；案例识别 ripasudil 治干性 AMD（发 Nature）。
- **开源**：PaperQA2、ether0（24B）开源；平台免费。
- **优势**：分工清晰可链式、读全文、核心引擎开源、有真实 AI 主导发现案例。
- **局限**：Phoenix 不成熟、Finch 闭测；"超越人类"多为自述基准。

### 4. Edison Scientific / Kosmos（FutureHouse 分拆的营利实体）
- **定位**：面向 R&D 的自主"AI 科学家"，Kosmos 自主完成"文献综述+数据分析+假设生成"多轮闭环，产出类论文报告。
- **核心技术**：**结构化 world model（世界模型）**，处理远超 LLM 上下文的信息，长时程目标一致；每条结论可追溯到代码行/文献段，全程可审计。
- **规模**：单 run 读 ~1500 篇论文、写 >40000 行代码、~200 轮 rollout、约 12 小时 ≈ 6 个月人类科研；人评约 **80% 准确**；报告 7 项发现（3 复现 + 4 新假设）。
- **定价**：学术前 6 次 run 免费，之后 **$200/run**。
- **融资**：$70M 种子轮（估值 ~$2.5 亿，天使含 Jeff Dean），~3 万用户；与药企 Incyte 合作。
- **局限**：约 1/5 陈述不可靠需人类监督；基座不透明；成本高。

### 5. K-Dense AI（Biostate AI）
- **定位**：自主生物医学研究 agent，多智能体协作把研究周期"从数年压缩到数天"。
- **架构**：分层多智能体 + dual-loop；有**交叉核查 agent** 对照可信库验证引用，抑制幻觉、强调可复现可溯源。
- **模型**：构建于 Google **Gemini 2.5 Pro**（非自研基座）。
- **Benchmark**：BixBench **29.2%** > GPT-5(22.9%) / GPT-4o(18%) / Claude 3.5(18%)；清洗子集 BixBench-Verified-50 达 90%。（"HLE 生物医学第一"未能证实，存疑。）
- **背书**：投资含 Dario Amodei、Emily Leproust、Mike Schnall-Levin；与哈佛医学院合作数周完成通常数年的衰老研究。
- **开源**：平台闭源；配套 `scientific-agent-skills`（宣称 16 万+ 科学家、140 skills、100+ 数据库，兼容 Cursor/Claude Code/Codex）。

### 6. 文献型科研 Agent
| | Elicit | Consensus | Scite |
|---|---|---|---|
| 侧重 | 系统综述/数据提取 | 快速证据检索 | 引用可信度 |
| 杀手锏 | PRISMA 综述工作流 | Consensus Meter | Smart Citations |
| 规模 | 138M 论文 | 200M+ 论文 | 1.6B 引用 |
| 免费层 | 5000 credits | 无限检索+~20cr/月 | 7 天试用 |
| 入门付费 | $12/月起 | ~$9/月 | $12/月起 |

### 7. 其他值得关注
- **Owkin**：agentic + 因果 AI + 联邦学习；K Navigator 科研 copilot（学术免费，2650 万文献 + 19 数据库 + MOSAIC 空间多组学）。
- **Isomorphic Labs**：DeepMind 分拆制药，AlphaFold 3 商业化（闭源）。
- **结构预测开源**：Chai-1（Chai Discovery，开源）、Boltz-1/2（MIT，开源，AF3 级）。
- **Google AI Co-Scientist**：Gemini 多 agent 假设生成（Generation/Reflection/Ranking + Elo 进化，发 Nature）。
- **STORM**（Stanford OVAL）：自动写维基式综述，开源。

### 国际梯队总览
- **第一梯队（通用自主"AI 科学家"）**：Biomni/Phylo、Kosmos/Edison、K-Dense。共性：多轮闭环、可溯源、抑制幻觉、对标压缩数月/数年工作。
- **第二梯队（大厂/平台生态）**：Claude for Life Sciences（嵌入式提效）、FutureHouse（开源风向标）、Owkin、Google Co-Scientist。
- **第三梯队（专用/文献）**：Elicit/Consensus/Scite；结构预测 AF3/Boltz/Chai；综述 STORM。
- **共同短板**：多数"超越人类"为自述基准缺第三方复核；自主 agent 准确率仍 ~80%（1/5 不可靠）；代码执行有安全风险，人类监督不可或缺。


<div style="page-break-before: always;"></div>

---


# 第 4 部分 · 国内竞品详析

## 国内 Biomedical / Life-Science AI Agent 竞品详析

> 凡未查实项标"未查到"，不编造。部分官网被网络策略拦截，细节来自搜索索引，建议人工复核一手信息。

### 一、Omicos 辨析（重要）
**你查的 "Omicos" = OmicOS（中文"源境解码" / 英文 Primordecode），与 OmicVerse 同源但不同物。**
- **OmicOS**：闭源、内测中的**组学 AI 科学家 agent**。多 Agent 协作（Leader 拆解 + QC/注释/整合/轨迹/报告 specialist），调用 OmicVerse 工具链，全程 provenance 可追溯，交付 notebook + 图 + 证据链。覆盖单细胞/空间/bulk/多组学。底层用通用 LLM 作大脑 + 整合 scGPT/Geneformer/scFoundation 等单细胞大模型。自评 BiomniBench 81.2%。**闭源、closed beta、定价未查到。**
- **OmicVerse**：OmicOS 的开源底座（GPL-3.0，`pip install omicverse`，免费），多组学 Python 框架，V2 新增 agent 式工作流 J.A.R.V.I.S. 与 MCP 工具服务。发 Nature Communications 2024。
- **团队**：曾泽华（北京科技大学 / 112 Lab）。姊妹项目 **OmicClaw**（基于 OmicVerse 的自然语言多组学 agent）——**命名与形态与 BioClaw 高度重合，是最直接的国产同类竞品之一。**
- 来源：omicos.cn · omicverse.com · github.com/Starlitnightly/omicverse

### 二、天鹜科技 MatwingsVenus（晓鹜）
- **定位**：上海交大洪亮团队的 AI 蛋白设计公司，MatwingsVenus 是**对话式蛋白质研发智能体平台**（2026.4.24 发布，matvenus.com）。
- **公司**：上海天鹜科技，2021 成立，A 轮超亿元、启明创投领投；自称中国最大 AI 蛋白设计服务商。
- **能力**：自然语言 → Agent 拆解调度 挖酶/定向进化/从头设计/binder/抗体设计；整合 200+ 蛋白工具、50+ 专家、百亿级标签蛋白数据；打通质粒订购 + 机器人湿实验，"对话式干湿闭环"。
- **模型/数据**：自研蛋白大模型（Venus 系列）；数据集 Venus-Pod 近 **90 亿条蛋白序列**（号称全球最大）。参数量未披露。
- **开源**：学术侧 `ai4protein` 开源 VenusFactory/VenusREM/ProSST；商用 MatwingsVenus 闭源 SaaS。**定价未查到。**
- **⭐ 与 bioclaw 关系**：垂域（蛋白）对话 agent，任务窄但深，且有干湿闭环与自研数据护城河——是"深而窄"的对照，凸显 bioclaw"广而浅"。

### 三、"国产 Claude science / 生信 agent" 生态（小红书/知乎语境）
**关键背景**：网友说的这批产品多是 **2026 初爆火的 OpenClaw / NanoClaw agent 生态**在生物医学的衍生。底座 OpenClaw（奥地利）非国产，但一批华人/中国团队在其上做了生物医学层。
| 产品 | 定位 | 国产? |
|---|---|---|
| **BioClaw** | OpenClaw+Claude Agent SDK 的对话式生信助手（**你们的产品**，最典型形态）| 华人团队(Runchuan-BU，合著含侯廷军/浙大、刘琦/同济) |
| **ClawBio** | 生信原生、本地优先的开源技能库，可脱离聊天界面 | 部分华人 |
| **Claw4Science** | 生信 Agent "App Store"，聚合 91 项目/2230 技能 | 华人 |
| **OpenClaw-Medical-Skills** | 最大开源医学技能库（869 技能，~2.7k Star）| **国产**(FreedomIntelligence 港中深系) |
| **STELLA** | 自进化生物医学 agent（BioClaw 上游）| 非国产(Princeton+Stanford) |
| **Nanobot** | 4000 行轻量 agent，QQ/钉钉/飞书全覆盖 | **真国产**(港大 HKUDS) |
> "智海""Chat2Bio" 多轮检索**未找到**确切同名产品，疑为名称记忆偏差（相近的真实项目：Talk2Biomodels、ChatNT、DrBioRight）。

### 四、国内 AI4S 大厂 agent
**真正做实"通用对话式科研 Agent"的只有两家：深势 SciMaster、英矽 ChatPandaGPT+DORA。**

- **深势科技 DP Technology**：**SciMaster**（2025.7，全球首个"通用科研智能体"，基座 Innovator，问题拆解+检索+人机协同+调 Uni-Lab MCP 干湿闭环，内测免费）；**Bohrium 玻尔**（"科研界 HuggingFace"，200+ 科研 App + 1.6 亿论文检索）；**Uni-Mol**（分子大模型，被 AlphaFold3 列为 benchmark）。全流程最完整，但通用定位在单一生物垂类深度不如药企平台。
- **英矽智能 Insilico**（本组对话 agent 最完整）：**ChatPandaGPT**（业界首个把 LLM 对话集成进药物发现平台）；**Science42:DORA**（2025.3，多智能体 AI Scientist，自动做研究+写论文草稿带可溯源引用，已开源）；平台 PandaOmics/Chemistry42/inClinico + 机器人闭环。唯一同时具备"copilot + AI Scientist + 机器人闭环 + 真实管线验证"。
- **百图生科 BioMap**：xTrimo（2680 亿参数跨模态生物大模型）、xTrimoPGLM（千亿蛋白语言模型，2025 开源）、AIGP、BioMap OS。但**未查到独立通用对话 agent**，仍是"平台+内嵌助手"。赛诺菲合作。
- **智谱 AI**：AutoGLM 沉思/2.0（GLM-4.5 通用深研 agent，医疗仅落地行业之一）——**通用底座竞争者，非生物专用竞品**。
- **华深智药 HeliXon**（清华彭健）：HeliXonAI/Helixon Design（抗体设计），HX001 全球首个 AI 设计临床新冠抗体。**无 agent 形态**，是专业计算工具。
- **晶泰科技 XtalPi**：AI+机器人自主实验平台、XtalFold。其"agent"指机器人自动化编排，**未查到对话 agent**。

### 五、生信分析类 AI copilot（学术界同类，功能高度重叠）
- **单细胞对话 copilot**（最成熟）：**CellAgent**（首个单细胞多智能体，ICLR 2026，开源）、**CellWhisperer**（"与细胞对话"，Nat. Biotech. 2025，开源）、**GPTCelltype**（GPT-4 细胞注释 R 包）、**CompBioAgent**。
- **通用生信 agent**：**AutoBA**（KAUST，首个全自动生信 agent，开源）、**BioMANIA**（对话执行 Scanpy，开源）、**Biomni**、**DrBioRight 2.0**（癌症蛋白质组学对话，Nat. Commun. 2025）、**BioMaster**（港科广多智能体）、**BRAD**。
- **国产 AI 生信平台**：GeneLLM/BioFord（津渡生科，15 亿参数多组学大模型）、衍因科技、ChatDD（水木分子/清华 AIR，开源 BioMedGPT）。
- **传统云生信（点选式非对话）**：微生信、SangerBox、Hiplot、仙桃学术、OmicShare、百迈客云。

### 六、与"通用 biomedical chat agent（bioclaw 类）"最直接竞争的产品（相似度排序）
1. **BioClaw 生态本身**（ClawBio / Claw4Science / OpenClaw-Medical-Skills）——同生态同形态，最直接同类。
2. **OmicOS / OmicClaw**——闭源组学 chat agent，OmicClaw 与 bioclaw 命名+定位高度重合，**最直接国产竞争者之一**。
3. **Biomni**（国际）——形态几乎一致的开源通用生物医学 chat agent，最重要国际对标。
4. **AutoBA / BioMANIA / DrBioRight / BioMaster / CellAgent**——"自然语言→计划→代码→执行→可复现报告"学术同类。
5. **深势 SciMaster**——形态最接近但定位"通用科研"，生物医学是子集，降维竞争。
6. **MatwingsVenus / ChatDD**——垂域（蛋白/药研）对话 agent，深而窄的垂类竞争。


<div style="page-break-before: always;"></div>

---


# 第 5 部分 · BioClaw 改进建议

## BioClaw 改进建议 + 预估评分对比

### 一、预估横向评分表（基于公开能力，★待实测校准）

> ⚠️ 下表是**基于公开资料/文档的专家预估**，非亲测结果。真正的分数请用 `02_评测框架` 的题集实跑后填入。
> 打分 1–5，维度见 rubric（R1 准确 / R2 深度 / R3 真执行 / R4 透明 / R5 复现 / R6 速度 / R7 引用 / R8 易用）。

| 平台 | R1准确 | R2深度 | R3执行 | R4透明 | R5复现 | R6速度 | R7引用 | R8易用 | 加权总分* |
|---|---|---|---|---|---|---|---|---|---|
| **BioClaw** | 3.5 | 3 | 4 | 4 | **5** | 4 | 3 | **4.5** | ~3.8 |
| Biomni(网页) | 4 | 4.5 | 4.5 | 3.5 | 4 | 3 | 4 | 4 | ~4.1 |
| Kosmos/Edison | **4.5** | **5** | **5** | **5** | 4.5 | 1.5 | **5** | 3 | ~4.4 |
| K-Dense | 4 | 4.5 | 4.5 | 4.5 | 4.5 | 2.5 | 4.5 | 3.5 | ~4.2 |
| OmicOS(组学) | 4 | 4 | 4 | 4.5 | 4.5 | 3 | 4 | 3 | ~4.0 |
| 天鹜(蛋白) | 4.5 | 4.5 | 5(含湿) | 4 | 4 | 2 | 3 | 3.5 | ~4.1 |
| 深势 SciMaster | 4 | 4.5 | 4.5 | 4 | 4 | 3 | 4 | 3.5 | ~4.0 |
| FutureHouse | 4 | 3.5 | 2.5(文献强/分析弱) | 4 | 3 | 4 | **5** | 4.5 | ~3.8 |

*加权按 R1:25% R2:15% R3:20% R4:10% R5:10% R6:5% R7:10% R8:5%。

**读表结论**：
- BioClaw 的**相对强项**：R5 可复现（自动出 notebook，业界少见做到默认）、R8 易用（多 IM + 零安装网页，门槛最低）、R6 速度（轻任务快）。
- BioClaw 的**相对弱项**：R2 深度、R7 引用可信度、R1 复杂任务准确性——这三项正是 L4 "AI 科学家"们的护城河。
- **一句话**：BioClaw 是"最易用、最可复现的生信工具聊天层"，但离"能做深度研究的 AI 科学家"还有一档。

---

### 二、BioClaw 的核心竞争定位诊断

**它是什么**：OpenClaw/NanoClaw 生态里、用 Claude Agent SDK + Skills 把生信 CLI 工具"聊天化"的交付层。护城河在**交互形态**（多 IM 群聊 + 零安装 + 可复现 notebook），不在模型/数据/自主推理。

**它面对的三面夹击**：
1. **同生态同类**（ClawBio、Claw4Science、OmicClaw）——技术栈几乎相同，差异化窗口很窄，比的是技能质量与运营。
2. **开源通用对标 Biomni**——覆盖更广（25 领域/150 工具）、有自研推理模型、有顶级背书，是"更强的同形态"。
3. **官方下场 Claude for Science**——Anthropic 自己做 Skills for Science + MCP 连接器，与 BioClaw 技术范式同源，是"上游变对手"。

**结论**：BioClaw 不能在"工具多少"上赢（打不过 Biomni/官方），必须在**独有的交互与协作形态**上做深，并向上补"研究推理深度"。

---

### 三、改进方向（按优先级）

#### P0 · 立刻能做、性价比最高
1. **发布 benchmark 分数建立可信度**。竞品都有硬数字（Biomni: LAB-Bench SeqQA 81.9%；K-Dense: BixBench 29.2%；OmicOS: BiomniBench 81.2%）。BioClaw 目前**没有公开跑分**。用 `02_评测框架` + BixBench/LAB-Bench 跑一版，写进 README——这是最低成本的信任背书。
2. **补"引用可信度/防幻觉"能力（R7/R1）**。学 K-Dense 的**交叉核查 agent**、Kosmos 的**claim→代码行/文献段可溯源**。BioClaw 已有 notebook 可复现，但缺"每条结论可点击溯源"。在报告输出里给每个数值/结论挂上工具调用/PubMed 链接。
3. **做深零安装云版本**（`chat.bioclaw.tech` 已上线，继续押注）。竞品里最易用的 Biomni Lab、K-Dense Web 都是零 setup 云端；BioClaw 本地版要 Docker+Node，门槛偏高，云版是拉平差距的关键。

#### P1 · 3–6 个月，补研究深度（从 L2 → L3/L4）
4. **从"工具调用"升级到"研究推理"**。当前假设生成/实验设计只到文本级。引入 **planner + critic 双环**（K-Dense dual-loop / OmicOS 的 Leader+specialist），支持多组学整合、长时程多步任务，把 L3 复杂题跑通。
5. **加一个轻量 world-model / 上下文记忆层**。Kosmos 的核心差异就是跨 200 轮保持目标一致。BioClaw 现在 idle 后新容器就丢上下文——对复杂研究是硬伤。做持久化项目记忆（每个 group/thread 一个可积累的研究状态）。
6. **技能质量治理**。Claw4Science 论文自己指出生态"技能质量参差、命名混乱"。BioClaw 应对内置/Hub 技能做**测试用例 + 质量分级 + 版本锁定**，把"技能多"变成"技能靠谱"。

#### P2 · 中长期，做独有护城河
7. **把"群聊协作研究"做成杀手锏**。这是全场**唯一**在 IM 群里做多人-机协作研究的产品（论文标题就是 "Human-Bot Research Collaboration Ecosystems"）。深挖：多人分工、@不同专家 agent、实验室共享 workspace、结果沉淀为团队知识库。国内实验室重度用微信/飞书，这是本土化独有优势。
8. **深化湿实验多模态**（凝胶图已独有）。扩展到 Western blot 定量、菌落计数、显微图像、qPCR 曲线解读——"手机拍一张实验图就能问"是 C 端科研人员的强需求，竞品普遍没有。
9. **考虑接一个垂域深度**（择一）：与开源蛋白/组学模型（如 Boltz、OmicVerse、scGPT）深度集成，在某一垂类做到"能出真结论"，避免样样通样样松。
10. **数据安全与合规**。若要进临床/医院场景，需解决 PHI 处理、容器代码执行安全（这是 Biomni 被诟病的点：以系统权限跑 LLM 生成代码）。做好沙箱与审计是 To B 前提。

#### 一句话给 mentor 的汇报结论
> BioClaw 目前是"**最易用、最可复现、唯一群聊协作**的生信工具聊天层"，在 L2 执行类任务已可用；但对比 Biomni（更广）、Kosmos/K-Dense（更深、能自主研究、可溯源）、天鹜/深势（有自研数据与干湿闭环），BioClaw 缺**研究推理深度、防幻觉溯源、benchmark 背书**。短期靠"跑分 + 溯源 + 云版"补信任，中期靠"planner/critic 双环 + 记忆层"补深度，长期靠"群聊协作 + 湿实验多模态"做别人做不了的护城河。
