# ProvSci v0.3 Package Manifest

This folder is a self-contained local prototype of the ProvSci auditable scientific data agent.

## Contents

- `README.md`: product scope, feature blueprint, schema, quick start, quality gates, and roadmap.
- `docs/provsci-plan-v0.1.md`: archived project planning context.
- `docs/research-comparison.md`: paper/open-source architecture comparison.
- `docs/benchmark-results-v0.3.md`: reproducible benchmark results and limitations.
- `docs/external-baseline-feasibility.md`: what was and was not executable locally for prior systems.
- `src/provsci/`: mining, processing, classification, path execution, verification, pipeline, queryable agent facade, and CLI code.
- `schemas/sample_schema.json`: machine-readable sample schema.
- `examples/documents/biophysics_demo.json`: normalized document-package demo input.
- `examples/documents/pmc_demo.nxml`: JATS/PMC adapter demo input.
- `examples/real/PMC13272437.nxml`: CC-BY PMC/JATS article retained for reproducible benchmark runs.
- `examples/benchmark/real-smoke-manifest.json`: four real open-access JATS smoke inputs.
- `tests/`: standard-library unit and end-to-end tests.
- `scripts/run_demo.sh`: run the example pipeline.
- `scripts/run_tests.sh`: run all tests.
- `scripts/run_benchmark.sh`: run all architecture strategies against the strict manifest.
- `scripts/run_real_smoke.sh`: run result-focused extraction on four real PMC articles.
- `work/*/human_review.jsonl`: generated review queue for semantic or safety failures.
- `pyproject.toml`: package metadata and console-script configuration.

## Excluded from the package

- `work/`: generated run outputs.
- Python bytecode and test caches.
- Browser state, credentials, tokens, and unrelated workspace files.

## Runtime requirement

Python 3.9 or newer. The prototype uses only the Python standard library.
