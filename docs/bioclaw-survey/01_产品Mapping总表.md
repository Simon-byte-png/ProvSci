# AI4S Biomedical Agent 产品 Mapping 总表

> 时间：2026-07。价格/版本以官网为准，标注"?"为未查到公开信息。
> 阅读方式：先看"一、形态分层图"理解赛道结构，再看"二、总对照表"逐项对比，"三、按任务能力矩阵"看谁能做什么。

---

## 一、形态分层图（赛道结构）

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

## 二、总对照表

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

## 三、按生物任务能力矩阵（√真执行 / ○文本级 / ✗不支持 / — 未知）

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
