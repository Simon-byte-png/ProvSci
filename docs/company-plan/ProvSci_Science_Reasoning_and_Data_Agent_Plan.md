# ProvSci：可审计科学数据智能体 × 科学推理大模型 × 科学基础大模型

> 版本：v0.1
> 日期：2026-08-11
> 负责人：金若凡（Ruofan Jin）
> 工作区：`/home/ubuntu/file2/jrf`
> 状态：战略规划定稿，待选垂直域后进入工程原型

---

## 0. 执行摘要

### 0.1 我们要做什么

本项目同时推进三条互相咬合的线：

1. **SciHarvest / ProvSci-Agent（抢先主线）**
   从科学文献中自动抽取、改写、标注训练数据，并强制附带**可验证的获取路径（acquisition path / provenance）**。
2. **科学推理大模型（同步主线）**
   在大模型底座上做 fine-tune / RL，使模型不仅给出答案，还能给出**可检查的推理与证据路径**。
3. **科学基础大模型（中长期主线）**
   以可审计科学数据飞轮为核心，做继续预训练与后训练，形成可扩展的科学基座模型。

### 0.2 一句话主张

> 科学大模型的瓶颈不只是“怎么蒸馏教师”，而是**训练数据能否从文献中自动获得，并留下可核验的获取与变换路径**。我们用 provenance-native 数据智能体造数据，再用 path-supervised 目标训推理模型，最终长成科学基础大模型。

### 0.3 与近邻工作的差异（尤其相对 VG-OPD / cropd）

| 维度 | 本项目 ProvSci |
|---|---|
| 数据来源 | **从文献主动生产数据** |
| 标注重点 | **答案 + 证据定位 + 获取路径 + 复算轨迹** |
| 可信机制 | verifier 验证「**路径能否复现结果**」 |
| 模型故事 | **Path-supervised scientific reasoning** |
| 上限 | **数据引擎 → 推理模型 → 科学基座** |

**结论**：先交出可演示的数据智能体与机制主表。

### 0.4 90 天成功标准（可检验）

1. 垂直域跑通：PDF → 抽取 → path → verifier 复现 → 入库。
2. 产出 **≥1,000** 条金牌样本（条条含 provenance；抽检复现率 ≥ 85%）。
3. 完成推理模型 v0：同尺寸下，相对普通 SFT/GRPO，在「答案准确率 + 路径可复现率」双指标上显著更好。
4. 形成可对外的技术报告 / demo：上传文献，返回可验证数据卡。
5. 明确科学基座 v1 的数据配比、许可策略与算力预算。

---

## 1. 背景与问题定义

### 1.1 科学大模型的真实瓶颈

当前科学 LLM 后训练常见路径：

- 收集题库 / 合成题；
- SFT → RL（GRPO 等）；
- 用 rubric 或 LLM-as-judge 打分；
- 或多专家蒸馏合并。

这些路径在数学/代码上有效，在科学上会遇到：

1. **监督不可靠**：开放题难自动判定，judge 本身会错。
2. **数据不可审计**：不知道标签从哪来、经过哪些变换。
3. **幻觉可被蒸馏**：教师/标注模型的错误会被学生吸收。
4. **能力互扰**：数值、符号、机制、证据等轴混训易此消彼长。
5. **难以上升为基座**：没有可持续扩张的、带许可与 provenance 的科学语料引擎。

### 1.2 我们重新定义的问题

不只问：

> 如何把一个 4B 模型在 GPQA 上刷高？

而问：

> 如何建立一个**可扩展、可审计、可复现**的科学数据与模型飞轮，使科学推理能力与科学基础能力能够持续变强？

拆成三个可研究问题（RQ）：

- **RQ1（数据智能体）**：能否从文献自动得到带 provenance 的可验证科学样本，且路径复现率显著高于“直接让 LLM 出题”？
- **RQ2（推理模型）**：path-supervision / path-consistent RL 是否比纯答案监督更能提升科学推理的正确性与可核验性？
- **RQ3（基础模型）**：以 provenance 科学语料做继续预训练，是否在科学理解、数值 grounding、工具使用上优于仅后训练的同尺寸模型？

---

## 2. 总体架构

```text
                    ┌──────────────────────────────┐
                    │  文献 / 补充材料 / 图表 / 表   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     SciHarvest Agent Stack    │
                    │  Parse → Mine → Path → Verify │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │   ProvSci Dataset (金牌库)     │
                    │  answer + evidence + path + log │
                    └───────┬───────────────┬───────┘
                            │               │
              ┌─────────────▼──┐     ┌──────▼──────────────┐
              │ Reasoning LM   │     │ Foundation pretrain │
              │ path-supervised│     │ + mixture corpus    │
              │ SFT / RL       │     │ (中长期)             │
              └─────────────┬──┘     └──────┬──────────────┘
                            │               │
                            └───────┬───────┘
                                    ▼
                         Sci Foundation Model v1
                         (可审计科学基座)
```

三层资产：

1. **Agent 层**：生产数据的系统能力。
2. **Data 层**：带 provenance 的可训练样本与语料。
3. **Model 层**：推理模型与基础模型。

---

## 3. 线 A：智能体制造数据计划（SciHarvest / ProvSci-Agent）

### 3.1 目标

构建一个文献驱动的科学数据标注智能体，使其能够：

1. 从 PDF/HTML/补充材料中定位科学事实；
2. 改写为可用于训练的问答 / 命题 / 数值预测样本；
3. 生成**获取路径**（如何从文献得到该结果）；
4. 用工具与规则**重跑路径**，验证是否复现；
5. 只把复现成功的样本写入金牌训练集。

### 3.2 非目标（v0 明确不做）

- 不做万能“科学家 Agent”或全学科自动综述；
- 不追求第一周就到 100 万条；
- 不以 LLM 自评作为唯一质量标准；
- 不把无 provenance 的合成题当作主数据。

### 3.3 垂直域选择（先打穿一个）

v0 必须单域突破。候选：

| 域 | 数据形态 | 优势 | 风险 |
|---|---|---|---|
| **A. 物理实验数值 / 表** | 表格、误差、单位 | 易规则验证 | 版面复杂 |
| **B. 化学热力学 / 反应条件** | 表、条件、产率 | 工业与论文丰富 | 单位与条件歧义 |
| **C. 生物医学剂量-效应 / 浓度** | 曲线、IC50、浓度 | 与 biolab 资产接近 | 读图难、伦理/许可 |

**默认建议**：若 `p_biolab` 已有文献与实验语境，优先 **C 的可数值子集**（浓度、IC50、fold-change 等可复算项）或 **A**；最终在启动会确定一个。

选择标准：

1. 终值可用规则/计算复核；
2. 文献充足且许可可追踪；
3. 获取路径可用有限工具实现（表抽取、单位换算、算术/符号、基础读图）。

### 3.4 数据 Schema（核心，必须先冻结）

每条金牌样本建议 JSON 如下（逻辑字段，工程可落 JSONL/Parquet）：

```jsonc
{
  "id": "provscipdf-000123-c2",
  "source": {
    "doc_id": "doi:10.xxxx/xxxxx",
    "title": "...",
    "year": 2024,
    "license": "CC-BY-4.0",
    "local_path": "raw/pdfs/....pdf",
    "page_span": [4, 5]
  },
  "task": {
    "type": "numeric_qa",          // numeric_qa | table_lookup | relation | mcq | open_reason
    "subject": "biophysics",
    "question": "...",
    "answer": {"value": 12.5, "unit": "uM", "display": "12.5 μM"},
    "difficulty": 0.37
  },
  "evidence": [
    {
      "modality": "table",          // text | table | figure | equation | supplement
      "locator": {"page": 4, "table_id": "Table 2", "row": 3, "col": "IC50"},
      "span_text": "...",
      "bbox": [..]                  // 可选
    }
  ],
  "acquisition_path": [
    {
      "step_id": 1,
      "action": "extract_table_cell",
      "tool": "table_parser",
      "args": {"page": 4, "table_id": "Table 2", "row_key": "Compound 7", "col": "IC50"},
      "output": "12.5 μM",
      "depends_on": []
    },
    {
      "step_id": 2,
      "action": "unit_normalize",
      "tool": "pint",
      "args": {"value": "12.5 μM", "to": "M"},
      "output": "1.25e-5 M",
      "depends_on": [1]
    }
  ],
  "verification": {
    "status": "pass",               // pass | fail | unknown
    "recomputed": {"value": 1.25e-5, "unit": "M"},
    "tolerance": {"rel": 0.02, "abs": null},
    "verifier_version": "provverify_v0.1",
    "checked_at": "2026-08-11T00:00:00Z"
  },
  "quality": {
    "needs_human_review": false,
    "failure_mode": null,           // ocr_low_conf | unit_ambiguous | underspecified | ...
    "annotator": "agent_v0",
    "prompt_ver": "harvest_v0.2"
  },
  "split": "train"                  // train|dev|test；test 文献级隔离
}
```

**硬约束**：

- 无 `evidence` 不得入库；
- 无 `acquisition_path` 不得入金牌库；
- `verification.status != pass` 不得入金牌库（可进 silver/raw 供分析）；
- train/dev/test **按文献 doc_id 隔离**，禁止同文跨 split 泄漏。

### 3.5 Agent 模块设计

#### M1. Document Ingest
- 输入：PDF / HTML / 补充 zip
- 输出：规范化文档包（文本块、表、图、公式候选、页码、hash）
- 工具：PDF parser、版面分析、表格抽取、基础 OCR

#### M2. Claim / Candidate Miner
- 从文档中提出“可变成训练样本”的候选：
  - 表中数值单元格；
  - 明确比较关系（A > B、升高 X 倍）；
  - 可由方程+给定参数算出的量；
  - 图中可读点（v1 再加强）。
- 输出：candidate claims + 粗证据定位

#### M3. Task Writer
- 将 claim 改写为训练任务（问答/填空/计算题）
- 要求：问题可独立作答；不泄漏路径之外的捷径；保留单位与条件

#### M4. Path Builder（关键差异点）
- 生成有序 `acquisition_path`
- 只允许白名单动作：
  - `read_text_span`
  - `extract_table_cell`
  - `parse_number_unit`
  - `unit_convert`
  - `arith_eval`
  - `sympy_eval`
  - `read_figure_point`（可后置）
  - `lookup_condition`（温度、pH 等）
- 禁止“凭记忆知道答案”之类不可执行步骤

#### M5. Path Verifier
- **不看标准答案文本是否像人对**，而是：
  1. 清空最终答案；
  2. 按 path 逐步调用工具；
  3. 比较重算结果与声称答案是否在容差内。
- 失败则进入 regenerate / human queue，并记录 `failure_mode`

#### M6. Curator / Gate
- 去重（近邻题、同证据多问）
- 许可过滤
- 难度估计（模型 pass rate）
- 分层抽样进入 train/dev/test

### 3.6 质量指标（Agent）

| 指标 | 定义 | v0 目标 |
|---|---|---|
| Path Reproducibility | path 重跑后与答案一致的比例 | ≥ 85%（金牌库） |
| Evidence Precision | 人审：证据是否真支撑答案 | ≥ 90%（抽检 n≥200） |
| Fabrication Rate | 无证据或证据不支持却入库 | ≤ 2% |
| Cost Ratio | 单条金牌成本 / 纯人工标注成本 | ≤ 0.3 |
| Yield | 每篇文献平均金牌条数 | 监控，不硬定 |

### 3.7 数据分层

- **Gold**：path 验证通过 + 许可清晰
- **Silver**：有证据但 path 弱 / 需人工
- **Bronze**：仅 LLM 合成、无可靠 provenance（**默认不进主训**）
- **Corpus-Raw**：论文全文/结构化表，供基础模型预训练（与 QA 金牌库分开管）

### 3.8 许可与合规（Day 1 起强制）

每条样本必须记录：

- 文献许可（CC-BY / NC / 出版社政策 / 未知）；
- 是否允许衍生训练；
- 是否允许再分发。

发布策略：

- 研究内部可训集合 ≠ 可公开再分发集合；
- 公开 artifact 优先 CC-BY / 出版社允许的子集；
- 对 NC 内容仅研究报告，不 relicense。

### 3.9 Agent 工程里程碑

| 阶段 | 时间 | 交付 |
|---|---|---|
| A0 Schema & 工具白名单 | 第 1 周 | schema、评测脚本、100 条人工金牌 |
| A1 Vertical v0 | 第 2–4 周 | 单域 20→200 篇闭环，≥300 gold |
| A2 Scale to 1k–5k | 第 5–8 周 | 自动评测看板、demo、失败分析 |
| A3 Multi-modal path | 第 9–12 周 | 图读数/补充材料；跨域试点 |
| A4 Public preview | 第 12 周前后 | 技术报告 + 可复现 demo |

### 3.10 与 Dr.SCI 的关系（利用但不依赖）

Dr.SCI（论文约 100 万题；本机复现约 89 万）是有价值的**对照与弱监督资源**，但不是本项目护城河。

可用方式：

- 作为 reasoning LM 的辅助训练/对照基线；
- 学习其 verifiable / open-ended 划分与难度思想；
- **不**把“复现 Dr.SCI 标注”当主线。

本机已有复现快照（供对照，不属于本项目主产出）：

- `/home/ubuntu/cropd/cropd/data/raw/drsci/`
- `Dr_SCI_verifiable.parquet`（414,746）
- `Dr_SCI_open-ended.parquet`（约 476k）

详见文末附录 B。

---

## 4. 线 B：科学推理大模型计划

### 4.1 目标

在开源大模型底座上，训练一个**科学推理模型**，使其：

1. 在科学问答 / 计算 / 解释任务上准确；
2. 能产出与答案一致的可检查路径（工具轨迹或结构化步骤）；
3. 在无可靠证据时会弃答或降置信，而不是编造。

### 4.2 模型定位（务必准确）

- **是**：Scientific Reasoning Model（后训练强化的科学推理模型）
- **不是**：立刻宣称 Science Foundation Model
- **将来**：作为科学基座的推理能力头部 / 对齐阶段

推荐命名空间：

- 数据引擎：`SciHarvest`
- 推理模型：`ProvSci-Reason-4B/7B`
- 基座模型：`ProvSci-Base-7B/14B`（中后期）

### 4.3 底座选择

| 阶段 | 底座 | 原因 |
|---|---|---|
| v0 | Qwen3-4B-Base 或同等可商用/可研究底座 | 迭代快、单卡可训、便于对照 |
| v1 | 7B 级 | 质量与成本平衡 |
| v2 | 14B 级（若算力允许） | 冲基座叙事 |

原则：

- 优先有 **Base** 权重（冷启动故事干净）；
- tokenizer 固定，便于 path token 对齐；
- 训练栈可复现（建议 verl / 自维护训练脚本双轨，避免被单一仓绑定）。

### 4.4 训练配方（Path-Supervised Scientific Reasoning）

#### Stage B0：数据准备
- Gold provenance QA（主）
- 干净可验证公开子集（辅）
- 负例：path 矛盾、单位错误、证据不足（用于拒答/校准）

#### Stage B1：Path-Aware SFT
不只学最终答案，学：

1. 最终答案（`\\boxed{}` 或结构化字段）；
2. 结构化 path（可工具化步骤）；
3. evidence cite（页码/表号/条件）。

损失：

- 答案 token CE
- path token CE（或工具调用序列 CE）
- 可选：evidence 引用格式约束

#### Stage B2：Verifier-Consistent RL
奖励建议固定为可加总轴（避免不稳定）：

- `r_final`：终答正确
- `r_path`：路径可被 verifier 复现
- `r_ground`：关键证据引用可定位
- `r_format`：格式合法
- `r_abstain`：应弃答时弃答的奖励 / 乱答惩罚

算法：GRPO / PPO 类均可；**先求奖励干净，再求算法花哨**。

#### Stage B3：可靠性强化（可作论文机制贡献）
- **Poisoned-path curriculum**：故意污染路径，训练拒绝；
- **Counterfactual repair**：仅当外部 verifier 确认 Δ>δ 时采纳修复段（可吸收 VG-OPD 思想，但教师来自 path-verifier，不必先上四专家）。

### 4.5 对照实验（推理模型论文主表）

必须有：

1. Base / instruct 零样本
2. 普通答案-only SFT
3. 普通 GRPO（仅终答奖励）
4. Path-SFT（我们）
5. Path-SFT + Verifier RL（我们）
6. 强基线：Dr.SCI 风格 rubric RL 或公开科学推理模型（若可复现）

主指标：

- 学科基准：GPQA 子集、域内 held-out 文献题、SciBench 类（按域选）
- **Path Reproducibility@Model**：模型输出路径可复现率
- 拒答校准：Evidence 不足集上的 false-answer 率
- 数据效率：达同一准确率所需样本数

### 4.6 推理模型里程碑

| 阶段 | 时间 | 交付 |
|---|---|---|
| B0 训练数据 v0 | 与 A1 同步 | 可用 train/dev/test |
| B1 SFT v0 | 第 4–6 周 | ProvSci-Reason SFT ckpt |
| B2 RL v0 | 第 6–9 周 | 主表初版 |
| B3 放大 | 第 9–12 周 | 7B 或更多域 |

---

## 5. 线 C：科学基础大模型计划

### 5.1 目标

构建面向科学的基础模型（Science Foundation Model），强调：

1. 广泛科学文本/符号/表格理解；
2. 数值与单位 grounding；
3. 可接工具与检索；
4. 可继续用 ProvSci 数据做对齐与推理强化。

### 5.2 什么时候才配叫“基础模型”

同时满足：

1. 有**持续预训练**（不是只 SFT/RL）；
2. 有规模化、许可清晰的科学语料配比；
3. 在多项科学理解/推理基准上相对同尺寸通用基座有稳定增益；
4. 能作为下游（推理、实验规划、文献QA）的统一底座。

否则对外只称 Reasoning Model，避免名实不符。

### 5.3 数据配比（v1 草案）

| 组分 | 比例起点 | 来源 | 作用 |
|---|---:|---|---|
| 科学全文/教材/综述 | 40–50% | 许可可得开放获取 | 知识与语言 |
| 结构化表/知识单元 | 10–15% | SciHarvest 表抽取 | 数值 grounding |
| Provenance QA / 题解 | 15–25% | Gold/Silver | 推理格式 |
| 通用高质量混合 | 15–25% | 开源通用语料 | 防灾难性遗忘 |
| 代码/公式/工具轨迹 | 5–10% | 公开+自产 | 符号与工具 |

### 5.4 训练阶段

1. **CPT（Continued Pre-Training）**：7B/14B，科学配比语料；
2. **IT/SFT**：指令与 path-aware 数据；
3. **RRHF/RL**：verifier-consistent 推理对齐；
4. **Tool-augmented 可选**：检索文献证据、计算器、单位系统。

### 5.5 基础模型里程碑

| 阶段 | 时间 | 交付 |
|---|---|---|
| C0 语料清单与许可矩阵 | 第 3–6 周 | 可抓取源与过滤规则 |
| C1 小规模 CPT 可行性 | 第 8–12 周 | 7B 1:1 对照实验 |
| C2 Base v1 | 3–6 个月 | ProvSci-Base 对外内部版 |
| C3 Scale | 6–12 个月 | 更大尺度/更多模态 |

---

## 6. 三条线如何同步而不互相拖死

### 6.1 资源分配建议（单卡 H100 场景）

| 时段 | GPU 用途 | 人/工程重心 |
|---|---|---|
| 第 1–4 周 | 70% Agent 研发与小规模推理，少打大型 serve | Schema、垂直域、人工金牌 |
| 第 5–8 周 | 50% 推理训练 / 50% Agent 扩量 | SFT/RL + 1k gold |
| 第 9–12 周 | 60% 模型实验 / 40% Agent 多域 | 主表、技术报告、CPT 预研 |

**原则**：不要把唯一 H100 长期锁在“大模型全量标注服务”上；Agent 的 verifier 应以 CPU/小模型工具为主，大模型只做候选生成与疑难例。

### 6.2 与本机其他项目的边界

| 路径 | 关系 |
|---|---|
| `/home/ubuntu/file2/jrf/p_antibody` | 抗体 MatchCDR，独立课题；可共享工程纪律，不共享主张 |
| `/home/ubuntu/file2/jrf/p_biolab` | 潜在垂直域与文献来源；可对接 SciHarvest |
| `/home/ubuntu/file2/jrf/agent-literature-review` 等 | 可复用文献代理件，不直接当数据引擎 |
| `/home/ubuntu/cropd/cropd` | 并行的 VG-OPD 线；可借鉴 verifier/verl，**不作为本项目主仓** |

### 6.3 仓库建议

新建独立仓（示例名）：

```text
/home/ubuntu/file2/jrf/p_provsci/
  README.md
  docs/                              # 本计划可同步一份
  schemas/sample_schema.json
  agent/                             # ingest/mine/path/verify
  data/                              # raw/processed/gold/splits
  training/                          # sft/rl configs
  eval/
  demos/
```

本文件为总计划源文档，工程仓落地后在 `docs/` 链回此文件或同步副本。

---

## 7. 评测体系（统一看板）

### 7.1 数据智能体评测

- Path Reproducibility
- Evidence Precision@Human
- Fabrication Rate
- Doc-level Yield
- License Coverage

### 7.2 推理模型评测

- 域内 held-out 文献题（最重要，防刷题库）
- 公开科学基准子集
- Path Reproducibility@Model
- Abstention / Calibration
- Poisoned-path Resistance

### 7.3 基础模型评测

- 科学理解（知识、表格、公式）
- 科学推理（上列）
- 工具使用
- 通用能力回归（MMLU 子集等，防崩）

### 7.4 泄漏控制

- 文献级隔离；
- n-gram + embedding 对测试文献查重；
- 任何“从测试文献自动抽题”只能进 test 生成器，不进训练。

---

## 8. 风险登记与对策

| ID | 风险 | 等级 | 对策 |
|---|---|---|---|
| R1 | PDF 版面/表格抽取失败率高 | 高 | 先表模型论文；人工工具链；失败样本分流 |
| R2 | 路径被 LLM 编得“看起来合理”但不可执行 | 高 | 白名单动作 + 强制重跑；无工具输出不记 pass |
| R3 | 许可导致数据不能发布 | 高 | Day1 license 字段；公开子集与内训子集分离 |
| R4 | 与 VG-OPD 叙事撞车/权属不清 | 中高 | 独立仓与独立主张；合作边界书面化 |
| R5 | 单卡算力被其他任务长期占用 | 高 | Agent 少依赖大模型常驻；训练分时预约 |
| R6 | 垂直域选错导致难验证 | 中 | 2 周内可切换域；以可复算性为第一标准 |
| R7 | 过早宣称 foundation model | 中 | 对外分期命名；CPT 完成前只称 reasoning |
| R8 | 评测被公开题库污染 | 中 | held-out 文献题为主指标 |

---

## 附录 A. 术语表

| 术语 | 含义 |
|---|---|
| Provenance / Acquisition Path | 从文献证据逐步变换得到答案的可执行路径 |
| Gold sample | path 验证通过且许可清晰的高置信训练样本 |
| Path Reproducibility | 按路径重跑后得到一致结果的比例 |
| Path-supervised training | 训练时监督答案与路径（及证据引用） |
| SciHarvest | 文献数据生产智能体代号 |
| ProvSci-Reason | 科学推理模型代号 |
| ProvSci-Base | 科学基础模型代号 |
| VG-OPD | 近邻并行工作：verifier-gated 多专家 on-policy 蒸馏 |

## 附录 B. Dr.SCI 数据速查（对照资源，非本项目主产出）

- 论文：Improving Data and Reward Design for Scientific Reasoning in LLMs（arXiv:2602.08321）
- 论文规模：约 1,006,701 题；可验证约 461k / 开放题约 545k
- 本机复现：`MiniByte-666/Dr.SCI` → `/home/ubuntu/cropd/cropd/data/raw/drsci/`
  - verifiable：414,746
  - open-ended：约 475,759
- 上游：WebInstruct-Verified、NaturalReasoning、MegaScience、RaR-Science
- 许可：复现仓 MIT 标签不可直接采信；存在大量 NC 上游
- 对本项目：可作基线与弱监督，**主线仍是文献 provenance 数据引擎**

## 附录 C. 与 VG-OPD 可借鉴 / 不采纳清单

**可借鉴**
- 确定性 verifier 思想（numeric/unit、sympy、rule）
- 固定 reward 轴，避免不稳定 key
- poisoned-teacher / reliability gate 的评价协议

**不采纳为依赖**
- 35B 全量 criteria 常驻占卡
- 未验证的四专家齐全再谈主结果
- 以现成题库为唯一数据护城河
