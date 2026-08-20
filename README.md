# ProvSci

从科学论文里生产**可验证结果数据**的智能体。

它不是只回答“答案是什么”，而是同时交付四样东西：

1. 答案
2. 证据在哪里（哪一页、哪张表、哪一格）
3. 答案是怎么从证据算出来的（获取路径）
4. 这条路径能不能由程序重新跑通（验证结果）

一句话：别人做的是“帮我读论文 / 帮我分析数据”，ProvSci 做的是“把论文里的数据加工成以后可以放心拿来用的样本”。

## 第一阶段范围

- 垂直域：生物医学剂量—效应 / 浓度数据（IC50、EC50、fold-change、浓度、时间点、组间差异）
- 优先处理文字和表格中的数值结果，暂不做全学科、不读图、不做实验机器人
- 大模型不能用“凭知识回答”混过验证；路径动作必须可执行

```text
论文 PDF/HTML
    ↓  ingest     规范化文档包（页码、hash）
    ↓  extract    文字、表格、数值、单位、行列位置
    ↓  claims     候选事实
    ↓  tasks      改写成问答 / 查表 / 计算
    ↓  path       白名单动作序列
    ↓  verify     按路径重算
    ↓  gate       gold / silver / raw
    ↓  card       答案 + 证据 + 路径 + 许可 + 日志
```

## 仓库结构

```text
docs/                 定位、功能设计、调研
src/provsci/          Python 包（当前是接口骨架）
  ingest/             文档导入
  extract/            表格与文本抽取
  claims/             候选事实发现
  path/               获取路径生成
  verify/             路径验证器
  gate/               质量闸门
  schema.py           数据卡 JSON 结构
data/
  raw/                原始论文（默认不入库）
  gold/               人工核验样本
  cards/              自动产出的数据卡
tests/
```

## 本地启动

```bash
cd ProvSci
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # 填入 XAI_API_KEY
```

LLM 调用走 SpaceXAI（xAI API：`XAI_API_KEY`，`https://api.x.ai/v1`）。密钥只放在被 git 忽略的 `.env` 里。

当前 `provsci` 命令只打印流水线状态，模块还是空实现。下一步是冻结 schema、写白名单工具，再人工做第一批 Gold 样本。

## 文档

- [我想做的科学结果数据智能体](docs/vision.md)
- [现状与功能设计 v0.1](docs/design-v0.1.md)
- [TRUST 论文对照调研](docs/trust-survey.md)
