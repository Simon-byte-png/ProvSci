# AI4S Biomedical Agent 调研报告（面向 BioClaw 改进）

**日期**：2026-07　|　**产品**：BioClaw（chat.bioclaw.tech）　|　**目的**：摸清 AI4S 产品当前能做什么，并给出 BioClaw 的改进方向。

> 本报告由 5 个文件组成，本文件是总览：
> - `00_主报告`（本文，结论先行）
> - `01_产品Mapping总表`（赛道结构 + 对照表 + 能力矩阵）← mentor 要求①
> - `02_评测框架_rubric与测试题集`（打分标准 + 3 难度×8 类型测试题）← mentor 要求②
> - `03_国际竞品详析` / `04_国内竞品详析`（逐产品事实卡片）
> - `05_bioclaw改进建议`（预估评分 + 分优先级改进）← mentor 要求③

---

## 一、一页结论（TL;DR）

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

## 二、mentor 三项要求的落点

| mentor 要求 | 对应交付 | 关键结论 |
|---|---|---|
| ① 国内外产品 mapping（Omicos/天鹜/Claude science/Biomni/Edison/Kdense…）| `01` + `03` + `04` | 已覆盖 30+ 产品，画出四层赛道结构与能力矩阵；辨清 Omicos=OmicOS、phylo=Biomni 商业公司、Edison=Kosmos |
| ② AI 生成不同难度/类型 prompt + rubric 打分表 | `02` + `05` | 已产出 3 难度×8 生物类型共 24 题 + 8 维 rubric + 记录模板；`05` 给出预估评分表（待实测校准）|
| ③ 指向性 report：bioclaw 能改哪里 | `05` + 本文 | 10 条分优先级建议，核心是"补深度+溯源、守住协作/易用护城河"|

---

## 三、关键辨析（避免踩坑）

- **Omicos** = **OmicOS（源境解码）**，闭源组学 AI 科学家；其开源底座是 **OmicVerse**；姊妹项目 **OmicClaw** 与 BioClaw 形态高度重合 → **最直接国产竞品之一**。
- **Biomni 的 "phylo"** = 从 Biomni 孵化的**商业公司 Phylo**（旗舰 Biomni Lab / IBE，phylo.bio 可免费注册），不是版本代号。
- **Edison** = **Edison Scientific**，产品是 **Kosmos**（FutureHouse 分拆），前 6 run 免费后 $200/run。
- **K-Dense** = Biostate AI 出品，Gemini 2.5 Pro 基座，BixBench 29.2%（"HLE 生物医学第一"**未证实**）。
- **"国产 Claude science"** = 多指 **OpenClaw/NanoClaw agent 生态**在生物医学的衍生（BioClaw 自己就是其中之一；底座 OpenClaw 非国产，生物医学层多为华人/中国团队）。
- 用户提到的 **"智海""Chat2Bio"** 检索**未找到**确切同名产品，疑记忆偏差，建议补出处。

---

## 四、下一步建议（给你执行）

1. **实测校准评分表**：拿 `02` 的 8 题基准集，注册 Biomni Lab（免费）、phylo.bio（免费 pro）、FutureHouse（免费）、K-Dense Web、深势玻尔（限免）实跑，把真实分数填进 `05` 的表，替换预估值。BioClaw 用你们自己网页版跑同一批题。
2. **重点抓 L3 难题**：L1/L2 各家都能做，拉开差距的是 L3（GEO 端到端、多组学整合、假设生成+实验设计）。这几题最能暴露 BioClaw 与"AI 科学家"的差距，也最能指导改进。
3. **先落地 P0 三件事**：跑 benchmark、给结论加可点击溯源、押注零安装云版——三件都是低成本高回报。

---

## 五、信息可信度与存疑项

- 本报告基于公开 web 检索（官网/bioRxiv/GitHub/知乎/公众号/36氪/机器之心等），关键事实交叉验证。
- 多个官网（bioclaw.tech 部分、matvenus.com、部分 NCBI）受网络策略限制，细节来自搜索索引/镜像，建议人工复核一手信息。
- 未证实项已在各文件标注（K-Dense HLE 成绩、Kosmos 基座、多家定价、"智海/Chat2Bio"）。
- `05` 的评分表为**专家预估非亲测**，务必实跑后校准再对外用。
