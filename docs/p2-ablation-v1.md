# ProvSci P2 模块消融报告（v2）

本报告使用 `examples/benchmark/p0-gold-manifest.json` 的 2 篇真实 CC-BY PMC/JATS 文献和 52 条人工核验 claim。命令为：

```bash
./scripts/run_p2.sh work/p2-evaluation
```

当前完整核验目录为 `work/p2-generic-final-v3/`，其中同时包含 `benchmark/`、`ablation/` 和 `adversarial/` 三类诊断产物。

`ablation.json` 中的 `all_gates` 是生产基线；其余变体只用于诊断，不能用于生产 Gold。所有变体共用同一次 `result_focused` 候选挖掘，避免把挖掘策略差异误当成门禁差异。当前把门禁拆成五项：`quality`、`verifier`、`license`、`evidence` 和 `acquisition_path`。

| 变体 | 保留候选 | Gold-like Yield | Claim Recall | Claim Precision | License Coverage | Path Reproducibility |
|---|---:|---:|---:|---:|---:|---:|
| `all_gates` | 46 | 0.8846 | 0.8846 | 1.0000 | 1.0000 | 1.0000 |
| `without_quality_gate` | 52 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `without_verifier` | 46 | 0.8846 | 0.8846 | 1.0000 | 1.0000 | 1.0000 |
| `without_license_gate` | 46 | 0.8846 | 0.8846 | 1.0000 | 1.0000 | 1.0000 |
| `without_evidence_path_gate` | 46 | 0.8846 | 0.8846 | 1.0000 | 1.0000 | 1.0000 |

解释：P0 文献中的 52 条候选都能通过确定性 replay，只有 6 条关系样本因语义跨度不稳定被质量门禁分流，所以本 manifest 上去掉 verifier、license 或 evidence/path presence 都不会额外放行候选。这不是“验证器没有价值”的证据，而是固定集没有故意植入 path/evidence 篡改样本。`without_quality_gate` 多放行 6 条未达到 Gold 语义门禁的 claim。要测出 verifier 对篡改值、篡改证据和非法 path 的拒绝能力，应使用现有 adversarial 单测和后续独立污染集，不能把人工金牌集改坏。

本次运行的独立门禁拒绝计数为：`quality=6`、`verifier=0`、`license=0`、`evidence=0`、`acquisition_path=0`。计数按候选逐项统计，允许同一候选同时触发多个门禁；它是诊断信息，不是互斥的错误分类。

为了观察许可门禁，亦可对包含 unknown-license fixture 的旧 manifest 运行：

```bash
./scripts/run_p2.sh work/p2-multiformat examples/benchmark/manifest.json
```

该运行的 `without_license_gate` 会保留 5 条 unknown-license 候选，License Coverage 从 1.0 降到 0.878；这说明许可门禁影响的是可公开数据产出，不应由 claim precision 单项替代。由于 unknown license 在运行时仍会进入人工队列，消融实现将其从独立 `quality` 门禁中分离，避免把许可证问题重复计入质量门禁。

`without_evidence_path_gate` 只忽略证据和 acquisition path 是否存在，但仍要求 verifier 通过；因此当证据或路径缺失导致 verifier 失败时，该变体仍可能不放行。这种重叠是有意保留的，便于说明“存在性门禁”和“完整 replay 验证”不是同一个检查；后续污染集应分别构造只破坏其中一项的样本。

为避免把“固定集没有失败”误解成 verifier 不重要，仓库另提供独立的对抗评测：

```bash
./scripts/run_adversarial.sh work/adversarial-evaluation
```

该评测从固定 manifest 的干净候选复制五类污染样本（篡改答案、篡改证据、删除证据、删除 acquisition path、替换为非法 path action），每个样本都针对原文重新执行 verifier，并记录预期/实际 failure mode、各门禁状态以及如果去掉 verifier 是否会被放行。当前 5/5（1.0）被 verifier 拒绝，其中 3/5 会在去掉 verifier 时满足其他门禁，说明固定干净集上的零差异不能解释为 verifier 无效。它是诊断 benchmark，不会修改 Gold manifest，也不能替代真实文献人工标注。
