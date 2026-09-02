# ProvSci v0.3 Benchmark Results

Run date: 2026-08-21

> This is a historical pre-P0 snapshot retained for provenance. It predates
> the earlier biomedical sample manifest and the current four-paper
> smoke results. Use [`p0-results-v1.md`](p0-results-v1.md) and
> [`p2-ablation-v1.md`](p2-ablation-v1.md) for the current benchmark and
> diagnostic numbers.

## Corpus

- 4 local fixtures: JSON, CSV, HTML, and JATS.
- 1 real CC-BY PMC/JATS article: `PMC13272437`, retained at `examples/real/PMC13272437.nxml`.
- 23 manually reviewed claims on the real article: 20 measurements and 3 relations.
- Exact matching checks value, unit, metric, entity, and relation subject/predicate/object.
- The article source is recorded as the Europe PMC full-text XML endpoint, with retrieval date and license source in the benchmark manifest and emitted sample metadata.

## Results

| Strategy | Claim Recall | Claim Precision | Path Reproducibility | Evidence Coverage | License Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `table_only` | 0.3902 | 1.0000 | 1.0000 | 1.0000 | 0.6875 |
| `full` | 1.0000 | 0.7069 | 1.0000 | 1.0000 | 0.9153 |
| `result_focused` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.8780 |

`result_focused` is the current default. It uses JATS section metadata to exclude method sections and filters condition-only values before semantic quality gating. `full` is intentionally retained as a high-recall/noisy comparison. `table_only` is the narrow baseline.

## Real-paper evidence

On `PMC13272437` specifically:

- `full`: 40 predicted claim signatures for 23 expected claims, precision `0.575`.
- `result_focused`: 23 predicted claim signatures, all 23 matched, precision/recall `1.0/1.0`.
- Both strategies replayed paths successfully; replay success alone was therefore insufficient to distinguish semantic quality.

## Interpretation and limits

This is a reproducible engineering benchmark, not proof that ProvSci surpasses every prior scientific agent. The current real articles are one biomedical sample domain under the generic quantitative-result profile and one annotation pass. A publication-grade evaluation should add at least 100 held-out claims, multiple scientific domains, independent annotators, parser version records, and cost/latency measurements.

The useful result at this stage is architectural: provenance replay is necessary but not sufficient; section-aware routing plus metric/entity/role binding materially improves precision while preserving recall on the current real-paper test.

## Four-paper real smoke

The separate `real-smoke-manifest.json` runs four CC-BY PMC/JATS articles without hand-written expected claims. It is a pipeline health and failure-routing check, not a precision benchmark:

| Document | Candidates | Gold | Silver / human review | Path replay |
| --- | ---: | ---: | ---: | ---: |
| `PMC13272437` | 23 | 23 | 0 | 1.0000 |
| `PMC8415024` | 29 | 23 | 6 | 1.0000 |
| `PMC9857184` | 140 | 140 | 0 | 1.0000 |
| `PMC2010468` | 0 | 0 | 0 | 1.0000 |
| **Total** | **192** | **186** | **6** | **1.0000** |

The current smoke suite retains six review items from semantically underspecified relation candidates in `PMC8415024`; the table row-label and caption-condition fixes improve entity/condition provenance for `PMC9857184`. Real-paper results without independent claim annotation should still be treated as pipeline health evidence, not proof of semantic precision.

## Reproduce

```bash
./scripts/run_benchmark.sh work/benchmark
cat work/benchmark/evaluation.json
```

Run the real-paper smoke set:

```bash
./scripts/run_real_smoke.sh work/real-smoke
cat work/real-smoke/summary.json
```
