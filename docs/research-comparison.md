# ProvSci Research And Architecture Comparison

Research snapshot: 2026-08-21. Repository stars are rough ecosystem signals, not quality or scientific-performance scores. The implementation should benchmark task-level metrics on a fixed corpus before making performance claims.

## Design question

The target is a scientific result-data agent, not only a scientific QA system. The agent must discover results, preserve evidence, transform values, classify and annotate them, and prove that an executable path can reproduce the result.

## Papers and open-source systems

| System / paper | What it is good at | Evidence and provenance | Main limitation for ProvSci | Decision |
| --- | --- | --- | --- | --- |
| [Docling](https://github.com/docling-project/docling), [technical report](https://arxiv.org/abs/2408.09869) | Multi-format parsing, layout, tables, formulas, OCR, local execution and export | Strong document-level structure; provenance must be added by the downstream agent | Heavy optional dependency and model/runtime cost; parser output is not a verified scientific claim | **Preferred rich parser adapter** |
| [GROBID](https://github.com/grobidOrg/grobid) | Scholarly PDF structure, metadata, citations and TEI XML | Excellent source spans and scholarly structure when configured | Less focused on arbitrary result tables and executable numerical transformations | **Optional scholarly parser adapter** |
| [Nougat](https://github.com/facebookresearch/nougat), [paper](https://arxiv.org/abs/2308.13418) | Academic PDF OCR with LaTeX math and tables | Produces structured text but page/table claims still need grounding | OCR errors and missing-page behavior can fabricate or drop evidence | **Fallback for scanned/math-heavy PDFs** |
| [Table Transformer](https://github.com/microsoft/table-transformer), [PubTables-1M](https://arxiv.org/abs/2110.00061) | Table detection and structure recognition; GriTS evaluation | Cell boxes and structure support precise locators | Needs OCR/text extraction; table structure is not semantic scientific interpretation | **Preferred table specialist** |
| [PaperQA2](https://github.com/Future-House/paper-qa), [PaperQA paper](https://arxiv.org/abs/2312.07559) | High-accuracy scientific RAG, citation-backed answers, contradiction detection | Citation support is useful for retrieval and answer grounding | Answer/citation quality is not the same as an executable transformation path; not a dataset curation gate | **Retrieval/evidence module reference** |
| [SciSpaCy](https://github.com/allenai/scispacy) | Scientific/biomedical NER and entity linking | Entity spans can enrich evidence and normalization | Not a document parser or end-to-end provenance verifier | **Optional terminology/entity layer** |
| [S2ORC](https://arxiv.org/abs/1911.02782) | Large structured scientific corpus | Useful corpus and pretraining reference | Corpus scale does not guarantee result-level provenance or license-safe derivation | **Corpus source/reference, not agent core** |
| [EcoData Extraction](https://github.com/ZhangHan200005/EcoData_Extraction) | Human-in-the-loop structured extraction from literature | Explicit review loop is relevant | Domain-specific and LLM-centric; no general deterministic path gate | **Human review UX reference** |
| [Paper2Data](https://github.com/Yourunwen/Paper2Data) | LLM extraction and metadata structuring for a domain dataset | Demonstrates task-specific extraction at scale | Domain schema and evaluation do not directly solve cross-domain provenance | **Domain extraction reference** |
| [SciEx / ChemX line of work](https://arxiv.org/abs/2510.00795) | Agentic scientific information extraction and benchmark framing | Moves evaluation toward agent systems and scientific IE | Newer work requires careful reproduction and may depend on proprietary models | **Benchmark design reference** |

## What ProvSci should combine

The best practical architecture is a layered system, not one monolithic LLM agent:

```text
Document adapters
  Docling (rich local path) / GROBID (scholarly XML) / TATR (tables) / Nougat (fallback)
        -> canonical DocumentPackage
Candidate miners
  table cells + text claims + formulas + conditions + figures
        -> candidate + evidence locator
Task and data processor
  entity/field normalization + units + conditions + type/difficulty/license
        -> task + answer + raw/normalized values
Path builder
  LLM may propose; an allowlist compiler must make it executable
        -> acquisition_path
Verifier and gate
  deterministic tools + evidence check + license check + doc-level split
        -> Gold / Silver / Human queue
Benchmark
  held-out documents + path reproducibility + evidence precision + abstention
```

The innovation claim is the **provenance-native gate**: retrieval and generation are proposal mechanisms, while only a path that replays from located source evidence can create a Gold sample. The path trace also becomes supervision for a later reasoning model.

## Comparison protocol

For every architecture, evaluate the same document-level held-out set:

- `candidate_recall`: gold result candidates discovered / annotated candidates
- `answer_accuracy`: normalized answer correctness
- `evidence_precision`: evidence actually supports the answer
- `path_reproducibility`: path replay agrees within tolerance
- `abstention_precision`: rejected/queued items are genuinely unsafe
- `fabrication_rate`: samples without supporting evidence that pass the gate
- `split_leakage`: document IDs shared across train/dev/test
- `cost_per_gold`: runtime and model/API cost per Gold sample

The benchmark now contains four local fixtures plus one real CC-BY PMC/JATS article (`PMC13272437`, downloaded from Europe PMC on 2026-08-21). The real article has 23 manually reviewed claims covering 20 measurements and 3 relations. On the current run, `result_focused` matched all 23 claims with 1.0 claim precision, 1.0 claim recall and 1.0 path reproducibility. This is evidence for the current corpus only, not a general scientific leaderboard. A publication-grade comparison still needs at least 100 independently annotated held-out claims across multiple domains and annotators.

The real-paper run also demonstrated why the semantic gate matters: unconstrained `full` generated 40 predicted signatures for 23 expected claims on that document, while `result_focused` generated 23/23 after excluding method sections, condition-only values and underspecified claims. On the five-document run, the measured strategies were:

| Strategy | Claim Recall | Claim Precision | Path Reproducibility | Evidence Coverage |
| --- | ---: | ---: | ---: | ---: |
| `table_only` | 0.3902 | 1.0000 | 1.0000 | 1.0000 |
| `full` | 1.0000 | 0.7069 | 1.0000 | 1.0000 |
| `result_focused` | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

These values are recorded in `work/strict-benchmark-v2/evaluation.json` when the benchmark is run locally. The honest interpretation is: result-focused routing materially improves claim coverage over table-only and avoids the precision collapse of unconstrained text mining on the included real paper. It does not yet prove superiority over every external agent.

## Decisions for the next implementation

1. Keep the standard-library adapter and verifier as the reproducible baseline.
2. Add optional Docling/GROBID/TATR adapters behind the same `DocumentPackage` contract.
3. Put LLMs after candidate generation and before path compilation; never let an LLM directly assign `verification.status=pass`.
4. Add human review for ambiguous units, OCR-low-confidence spans, cross-table joins and unsupported relations.
5. Report per-domain and per-modality scores; do not aggregate away table, text, formula and figure failures.
