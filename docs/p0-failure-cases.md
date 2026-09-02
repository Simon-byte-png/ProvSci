# P0 典型失败案例与处理

P0 不把所有候选都强行变成 Gold。以下案例来自 `examples/real/PMC8415024.nxml` 和现有 adversarial 测试，均可由 `./scripts/run_p0.sh work/p0-final` 重建。

| 案例 | 触发原因 | 正确处理 | 证据位置 |
|---|---|---|---|
| 结果段中出现 `5 μM`、`10 μM` 等给药浓度 | 同一段较早提到 IC50，近邻关键词会造成指标误判 | `result_focused` 将其路由为条件并排除，不进入 Gold | `p24`；`miner.is_core_result_candidate` |
| 关系抽取主语以 “As shown/To determine/when” 开头或过长 | 关系跨度包含叙述上下文，语义主客体不稳定 | 保留候选和完整证据，但标记 `underspecified_relation`，进入 Silver/Human Review | `PMC8415024` 的 `p22/p24/p26/p28/p30/p35` |
| 源文件许可证为 `unknown` | 结果可 replay，但不能确认公开再分发权限 | 保留为 Silver，标记 `license_unknown` 并进入人工队列 | `examples/benchmark/manifest.json` 的 `csv:unknown-license` |
| 修改 Gold 的答案值 | 答案不再与 acquisition path 重算结果一致 | verifier 返回 `answer_mismatch`，拒绝 Gold | `tests/test_pipeline.py::test_tampered_answer_cannot_pass` |
| 修改证据片段 | locator 仍存在但原文不支持该片段 | verifier 返回 `evidence_mismatch`，拒绝 Gold | `tests/test_pipeline.py::test_tampered_evidence_cannot_pass` |
| 同一文献不同表格对同一实体/指标/单位/条件报告不同值 | 跨证据上下文无法自动判断哪个值应作为最终结果 | 两个样本均保留，标记 `conflicting_values`，进入 Silver/Human Review，不静默覆盖 | `tests/test_pipeline.py::test_conflicting_values_are_routed_to_human_review` |
| 表格第一列不是常见的 Sample/Cell line，而是 `hPMTs`/`Analyte` 等科学标签 | 若退回 `row N`，实体绑定会丢失 | 使用受控标签词表保留第一列实体；未知列仍回退 `row N` 并需人工确认 | `src/provsci/miner.py::_row_label` |
| 表格 caption 明确写出统一采集时间（例如 `after 48 h`） | 仅凭列名无法提供实验条件 | 只传播显式时间表达；不把 `Mean / Hs27` 这类比较组误当作时间条件 | `src/provsci/miner.py::_caption_condition` |
| 解析或语义门禁失败后需要换策略 | 原运行结果不能证明更高召回策略一定安全 | 用 `retry` 写入新目录重跑，记录原始摘要 hash 和策略；仍由 verifier/Gold gate 裁决 | `tests/test_pipeline.py::RetryTests::test_retry_uses_fallback_strategy_and_preserves_lineage` |

## 为什么保留失败样本

`all.jsonl` 保留全部候选；`silver.jsonl` 保留未达到 Gold 门禁的结果；`human_review.jsonl` 只包含需要人处理的样本，并带有 `failure_mode`。这样可以区分“没有抽到”“抽到了但语义不完整”“结果可信但许可待确认”，避免失败被静默丢弃。

## 现场核验

```bash
./scripts/run_p0.sh work/p0-final
cat work/p0-final/benchmark/evaluation.json
cat work/p0-final/real-smoke/human_review.jsonl
```
