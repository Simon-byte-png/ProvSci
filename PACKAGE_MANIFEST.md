# ProvSci v0.3 Package Manifest

This folder is a self-contained local prototype of the ProvSci auditable scientific data agent.

## Contents

- `README.md`: product scope, feature blueprint, schema, quick start, quality gates, and roadmap.
- `docs/provsci-plan-v0.1.md`: archived project planning context.
- `docs/research-comparison.md`: paper/open-source architecture comparison.
- `docs/benchmark-results-v0.3.md`: reproducible benchmark results and limitations.
- `docs/ProvSci_下一阶段要求.md`: current scope, P0/P1/P2 requirements, Gold minimum and completion criteria.
- `docs/p0-failure-cases.md`: reproducible failure cases and routing decisions.
- `docs/p0-results-v1.md`: P0 benchmark/result table, condition matching and runtime/cost baseline.
- `docs/p2-ablation-v1.md`: fixed-manifest module-ablation report (five independent gates) and interpretation limits.
- `docs/老师演示方案-v1.md`: 8–10 minute teacher-demo script, commands, expected outputs, Q&A and fallback checklist.
- `docs/review-figures.md`: reproducible literature matrix and qualitative review-figure workflow.
- `docs/external-baseline-feasibility.md`: what was and was not executable locally for prior systems.
- `src/provsci/`: source fingerprinting/acquisition (including bounded external supplements), replaceable `DocumentAdapter` protocol, mining, processing, classification, path execution, verification, ResultCard export, module-ablation evaluation, append-only review decisions, local review workbench, retry orchestration, pipeline, queryable agent facade, and CLI code.
- `src/provsci/review_ui.py`: standard-library static HTML snapshot and loopback-only interactive review server; decisions delegate to the append-only review flow.
- `src/provsci/supplements.py`: parse downloaded attachments and attach them to a new normalized article package while preserving article/attachment hashes.
- `src/provsci/layout_adapters.py`: optional lazy Docling adapter with structured text/table/figure conversion and explicit missing-dependency errors.
- `src/provsci/figures.py`: dependency-free normalization and replay helpers for explicit figure axes, series and curve points.
- `schemas/sample_schema.json`: machine-readable sample schema.
- `schemas/result_card_v1.schema.json`: frozen ResultCard v1 interchange schema.
- `schemas/scientific_quantitative_result_profile.json`: default domain-agnostic quantitative-result profile and annotation policy.
- `schemas/biomedical_cell_viability_profile.json`: optional biomedical cell-viability specialization retained for regression examples.
- `examples/documents/biophysics_demo.json`: normalized document-package demo input.
- `examples/documents/generic_results_demo.json`: default domain-agnostic measurement demo input (yield, temperature and pressure).
- `examples/documents/structured_curve_demo.json`: explicit structured figure/curve demo with axis units, series and point-level provenance.
- `examples/documents/pmc_demo.nxml`: JATS/PMC adapter demo input.
- `examples/real/PMC13272437.nxml`: CC-BY PMC/JATS article retained for reproducible benchmark runs.
- `examples/benchmark/real-smoke-manifest.json`: four real open-access JATS smoke inputs.
- `examples/benchmark/p0-gold-manifest.json`: two real CC-BY articles and 52 manually checked claim signatures.
- `examples/review/literature_matrix.json`: 21 representative public works encoded for qualitative system comparison.
- `tests/`: standard-library unit and end-to-end tests.
- `scripts/run_demo.sh`: run the example pipeline.
- `scripts/run_tests.sh`: run all tests.
- `scripts/run_benchmark.sh`: run all architecture strategies against the strict manifest.
- `scripts/run_real_smoke.sh`: run result-focused extraction on four real PMC articles.
- `scripts/run_p0.sh`: reproduce the P0 demo, annotated benchmark and real-paper smoke in one command.
- `scripts/run_teacher_demo.sh`: reproduce P0 and add the SW480/IC50 query, compact preview, review queue snapshot and static review workbench for a live demonstration.
- `scripts/build_teacher_dashboard.py`: build the self-contained interactive visual dashboard from a completed teacher-demo run.
- `scripts/run_product_app.py`: serve the tracked product workspace and route uploaded files to the local ProvSci pipeline through `POST /api/analyze`.
- `scripts/start_product_app.sh` / `scripts/start_product_app.bat`: one-command launchers for downloaded macOS/Linux and Windows copies.
- `web/product_workspace.html`: tracked product workspace with file drop, run progress, structured result table, evidence panel and CSV export.
- `src/provsci/provider.py`: optional OpenAI-compatible API connection test and plain-language overview; it never replaces deterministic verification.
- `scripts/run_p2.sh`: reproduce the fixed-manifest benchmark and diagnostic module ablation.
- `scripts/run_adversarial.sh`: derive controlled contamination cases and audit verifier rejection.
- `scripts/build_review_figures.py`: rebuild matrix CSV/summary and four source-linked SVG review figures.
- `scripts/run_review_figures.sh`: reproducible wrapper for the review matrix/figure build.
- `provsci fetch-url`: bounded HTTP(S) source acquisition with redirect URL, parser metadata, license, version and SHA-256 provenance.
- `tests/test_review_ui.py`: snapshot rendering, loopback HTTP queue/review API, and unsafe-route regression tests.
- `work/*/human_review.jsonl`: generated review queue for semantic or safety failures.
- `work/*/review_queue.jsonl`: deterministic risk-prioritized review view derived from the active queue.
- `work/*/review_decisions.jsonl`: append-only accept/modify/reject audit log.
- `work/*/rejected.jsonl`: human-rejected samples retained for audit.
- `work/*/retry.json`: retry lineage and previous-summary hash for a re-run.
- `work/*/data_card.json`: dataset-level quality, domain, modality, license and failure summary.
- `work/*/teacher_dashboard.html`: generated interactive visual dashboard for the teacher demo.
- `work/*/adversarial_summary.json`: controlled contamination coverage and verifier rejection summary.
- `work/*/adversarial.jsonl`: controlled contaminated candidates with full verification/provenance traces.
- `pyproject.toml`: package metadata and console-script configuration.
- `.env.example`: optional local API settings template; real keys are never committed.

## Excluded from the package

- `work/`: generated run outputs.
- Python bytecode and test caches.
- Browser state, credentials, tokens, and unrelated workspace files.

## Runtime requirement

Python 3.9 or newer. The prototype uses only the Python standard library.
