# External Baseline Feasibility

Checked: 2026-08-21 on the current local environment.

## What was checked

| System | Repository/paper | Local dependency state | Fair-comparison status |
| --- | --- | --- | --- |
| Docling | `docling-project/docling`, arXiv:2408.09869 | `docling` unavailable; current machine has Python 3.9.6 while current Docling README says Python 3.10+ | Not executed locally; planned parser baseline |
| GROBID | `grobidOrg/grobid` | Java runtime unavailable and no GROBID service running | Not executed locally; planned scholarly parser baseline |
| Table Transformer | `microsoft/table-transformer`, PubTables-1M | `torch` and `transformers` unavailable | Not executed locally; planned table specialist baseline |
| Nougat | `facebookresearch/nougat`, arXiv:2308.13418 | PyTorch/model runtime unavailable | Not executed locally; planned scanned-PDF fallback |
| PaperQA2 | `Future-House/paper-qa`, arXiv:2312.07559 | package and model/API credentials unavailable | Not directly comparable to deterministic local baseline without a fixed model/API budget |
| SciSpaCy | `allenai/scispacy` | package unavailable | Optional entity-linking ablation, not an end-to-end agent baseline |

## Why this matters

The current ProvSci numbers are not presented as “better than Docling” or “better than PaperQA2”, because those systems solve different layers and were not run under the same corpus, model, hardware and budget. The fair comparison is:

1. Run the same document files through the same parser layer.
2. Convert each parser output to `DocumentPackage`.
3. Run the same candidate schema and verifier.
4. Score result claim recall, semantic precision, evidence precision, path reproducibility, review rate and cost per Gold.

ProvSci's current measurable advantage is at the downstream gate: parser output is not allowed to become Gold merely because an LLM or retrieval system produced a plausible answer. Evidence must resolve, the allowlisted path must replay, the runtime contract must pass, and license/semantic review gates must pass.

## Next fair-baseline experiment

Use Python 3.10+ in a separate environment and run:

- Docling-only parsing -> ProvSci verifier
- GROBID-only parsing -> ProvSci verifier
- Docling + Table Transformer table path -> ProvSci verifier
- ProvSci standard-library/JATS baseline

The output should be one comparison JSON containing parser version, source hash, runtime, wall time, candidate count, Gold count, review count, evidence precision and path reproducibility. Until this experiment is run, any broad claim of outperforming prior agents remains unproven.
