from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from provsci.models import DocumentPackage
from provsci.path import PathExecutionError, PathExecutor
from provsci.pipeline import run_pipeline
from provsci.values import convert, parse_number_unit
from provsci.batch import assign_split, read_manifest_entries, run_batch
from provsci.adapters import load_document
from provsci.miner import mine_numeric_text_candidates
from provsci.verifier import verify_sample
from provsci.evaluate import evaluate_manifest
from provsci.contract import validate_sample_contract
from provsci.agent import ScientificDataAgent


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "documents" / "biophysics_demo.json"


class ValueTests(unittest.TestCase):
    def test_parse_scientific_value(self) -> None:
        self.assertEqual(parse_number_unit("1.25e-5 M").value, 1.25e-5)
        self.assertEqual(parse_number_unit("12.5 μM").unit, "μM")

    def test_convert_concentration(self) -> None:
        converted = convert(parse_number_unit("250 nM"), "uM")
        self.assertAlmostEqual(converted.value, 0.25)

    def test_extract_text_percentage(self) -> None:
        from provsci.values import extract_number_unit_occurrences
        occurrences = extract_number_unit_occurrences("The response was 82.0 % at 10 uM.")
        self.assertEqual(len(occurrences), 2)
        self.assertEqual(occurrences[0][2].unit, "%")

    def test_figure_or_version_like_tokens_are_not_units(self) -> None:
        from provsci.values import extract_measurement_occurrences
        self.assertEqual(extract_measurement_occurrences("Figure 9C and ImageJ 1.54g"), [])


class PathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = DocumentPackage.from_dict(json.loads(DEMO.read_text()))

    def test_table_path_reproduces_value(self) -> None:
        output, trace = PathExecutor(self.document).execute([
            {
                "step_id": 1,
                "action": "extract_table_cell",
                "args": {"table_id": "Table 1", "row_key": "Compound B", "col": "IC50"},
                "depends_on": [],
            },
            {
                "step_id": 2,
                "action": "parse_number_unit",
                "args": {"value_from": 1},
                "depends_on": [1],
            },
        ])
        self.assertEqual(output, {"value": 250.0, "unit": "nM"})
        self.assertEqual(len(trace), 2)

    def test_table_path_reproduces_row_without_label_column(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "table:no-label", "title": "No label", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "table.json",
            "tables": [{"id": "Table 1", "page": 1, "rows": [{"Mean": "0.50 %"}]}],
        })
        from provsci.miner import mine_numeric_table_candidates
        candidate = next(iter(mine_numeric_table_candidates(document)))
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        verified = verify_sample(sample, document)
        self.assertEqual(verified["verification"]["status"], "pass")
        self.assertEqual(candidate.evidence[0]["locator"]["row_index"], 0)

    def test_unallowlisted_action_fails(self) -> None:
        with self.assertRaises(PathExecutionError):
            PathExecutor(self.document).execute([{
                "step_id": 1,
                "action": "hallucinate_answer",
                "args": {},
                "depends_on": [],
            }])

    def test_conversion_and_arithmetic_path(self) -> None:
        output, _ = PathExecutor(self.document).execute([
            {
                "step_id": 1,
                "action": "extract_table_cell",
                "args": {"table_id": "Table 1", "row_key": "Compound B", "col": "IC50"},
                "depends_on": [],
            },
            {
                "step_id": 2,
                "action": "parse_number_unit",
                "args": {"value_from": 1},
                "depends_on": [1],
            },
            {
                "step_id": 3,
                "action": "unit_convert",
                "args": {"value_from": 2, "to": "uM"},
                "depends_on": [2],
            },
            {
                "step_id": 4,
                "action": "arith_eval",
                "args": {"expression": "$3 * 2", "unit": "uM"},
                "depends_on": [3],
            },
        ])
        self.assertAlmostEqual(output["value"], 0.5)
        self.assertEqual(output["unit"], "uM")

    def test_boolean_arithmetic_is_rejected(self) -> None:
        with self.assertRaises(PathExecutionError):
            PathExecutor(self.document).execute([{
                "step_id": 1,
                "action": "arith_eval",
                "args": {"expression": "True + 1"},
                "depends_on": [],
            }])

    def test_duplicate_step_id_fails(self) -> None:
        with self.assertRaises(PathExecutionError):
            PathExecutor(self.document).execute([
                {"step_id": 1, "action": "read_text_span", "args": {"paragraph_id": "p1"}},
                {"step_id": 1, "action": "read_text_span", "args": {"paragraph_id": "p2"}},
            ])

    def test_undeclared_dependency_fails(self) -> None:
        with self.assertRaises(PathExecutionError):
            PathExecutor(self.document).execute([
                {"step_id": 1, "action": "read_text_span", "args": {"paragraph_id": "p1"}},
                {
                    "step_id": 2,
                    "action": "parse_number_unit",
                    "args": {"value_from": 1},
                    "depends_on": [],
                },
            ])

    def test_relation_path_reproduces_relation(self) -> None:
        output, trace = PathExecutor(self.document).execute([
            {
                "step_id": 1,
                "action": "read_text_span",
                "args": {"paragraph_id": "p1", "page": 1},
                "depends_on": [],
            },
            {
                "step_id": 2,
                "action": "extract_relation",
                "args": {"text_from": 1, "relation": "increased"},
                "depends_on": [1],
            },
        ])
        self.assertEqual(output["value"], "increased")
        self.assertEqual(output["subject"], "Compound A")
        self.assertEqual(output["object"], "response relative to control")
        self.assertEqual(len(trace), 2)


class PipelineTests(unittest.TestCase):
    def test_demo_creates_gold_and_silver_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = run_pipeline(DEMO, directory)
            self.assertEqual(summary["total_candidates"], 6)
            self.assertEqual(summary["gold"], 6)
            self.assertEqual(summary["silver"], 0)
            self.assertEqual(summary["path_reproducibility"], 1.0)
            self.assertEqual(summary["failure_modes"], {})
            self.assertTrue((Path(directory) / "gold.jsonl").exists())
            gold = [json.loads(line) for line in (Path(directory) / "gold.jsonl").read_text().splitlines()]
            self.assertEqual(gold[0]["task"]["classification"]["result_type"], "measurement")
            self.assertTrue(gold[0]["processing"]["raw_value_preserved"])
            self.assertEqual(len(gold[0]["source"]["source_hash"]), 64)
            self.assertTrue(gold[0]["verification"]["evidence_checked"])

    def test_tampered_answer_cannot_pass(self) -> None:
        document = DocumentPackage.from_dict(json.loads(DEMO.read_text()))
        candidate = next(iter(__import__("provsci.miner", fromlist=["mine_numeric_table_candidates"]).mine_numeric_table_candidates(document)))
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        sample["task"]["answer"]["value"] = 999.0
        verified = verify_sample(sample, document)
        self.assertEqual(verified["verification"]["status"], "fail")
        self.assertEqual(verified["quality"]["failure_mode"], "answer_mismatch")

    def test_tampered_evidence_cannot_pass(self) -> None:
        document = DocumentPackage.from_dict(json.loads(DEMO.read_text()))
        candidate = next(iter(__import__("provsci.miner", fromlist=["mine_numeric_table_candidates"]).mine_numeric_table_candidates(document)))
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        sample["evidence"][0]["span_text"] = "999 uM"
        verified = verify_sample(sample, document)
        self.assertEqual(verified["verification"]["status"], "fail")
        self.assertEqual(verified["quality"]["failure_mode"], "evidence_mismatch")

    def test_runtime_contract_rejects_missing_provenance_fields(self) -> None:
        self.assertTrue(validate_sample_contract({"id": "incomplete"}))

    def test_numeric_text_candidate_has_replayable_path(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "text:test", "title": "Text", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "text.txt",
            "paragraphs": [{"id": "p1", "page": 1, "text": "The response was 82.0 % at 10 uM."}],
        })
        candidates = list(mine_numeric_text_candidates(document))
        self.assertEqual(len(candidates), 2)
        verified = verify_sample(candidates[0].to_sample(document.license, document.title, document.local_path), document)
        self.assertEqual(verified["verification"]["status"], "pass")

    def test_result_focused_drops_treatment_conditions(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "conditions:test", "title": "Conditions", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "conditions.txt",
            "paragraphs": [{
                "id": "p1", "page": 1,
                "text": "Cells were treated with 20 uM compound for 6 h. Viability was 42 %.",
                "section_path": ["Results"],
            }],
        })
        from provsci.batch import mine_candidates
        candidates = mine_candidates(document, "result_focused")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].answer["metric"], "cell viability")

    def test_result_focused_uses_cell_line_context(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "cell-line:test", "title": "Cell line", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "paper.nxml",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Results"],
                "text": "The proportion of apoptosis cells of SW1116 cells was 19.87%.",
            }],
        })
        from provsci.batch import mine_candidates
        candidates = mine_candidates(document, "result_focused")
        self.assertEqual(candidates[0].answer["entity"], "SW1116")

    def test_treatment_concentration_is_routed_out_of_gold(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "concentration:test", "title": "Concentration", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "paper.nxml",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Results"],
                "text": "Cells were treated with different concentrations of ivermectin. The highest concentration was 30 uM.",
            }],
        })
        from provsci.batch import mine_candidates
        self.assertEqual(mine_candidates(document, "result_focused"), [])

    def test_batch_keeps_documents_in_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = run_batch([DEMO], directory)
            self.assertEqual(summary["document_count"], 1)
            self.assertEqual(summary["duplicate_sample_ids"], [])
            self.assertEqual(summary["path_reproducibility"], 1.0)
            self.assertEqual(assign_split("doi:10.1234/a"), assign_split("doi:10.1234/a"))

    def test_batch_reports_duplicate_ids_for_duplicate_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = run_batch([DEMO, DEMO], directory)
            self.assertEqual(summary["document_count"], 2)
            self.assertEqual(len(summary["duplicate_sample_ids"]), 6)

    def test_unknown_license_stays_silver(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = run_batch([(
                ROOT / "examples" / "documents" / "measurements.csv",
                {"doc_id": "csv:unknown", "license": "unknown", "year": 2024},
            )], directory)
            self.assertEqual(summary["gold"], 0)
            self.assertEqual(summary["silver"], 5)
            self.assertEqual(summary["license_coverage"], 0.0)

    def test_real_pmc_smoke_suite_preserves_audit_invariants(self) -> None:
        manifest = ROOT / "examples" / "benchmark" / "real-smoke-manifest.json"
        with tempfile.TemporaryDirectory() as directory:
            summary = run_batch(read_manifest_entries(manifest), directory, strategy="result_focused")
            self.assertEqual(summary["document_count"], 4)
            self.assertGreaterEqual(summary["total_candidates"], 150)
            self.assertEqual(summary["path_reproducibility"], 1.0)
            self.assertEqual(summary["evidence_coverage"], 1.0)
            self.assertEqual(summary["license_coverage"], 1.0)
            self.assertEqual(summary["duplicate_sample_ids"], [])

    def test_agent_can_query_verified_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = ScientificDataAgent()
            summary = agent.run(DEMO, directory)
            self.assertEqual(summary["path_reproducibility"], 1.0)
            results = agent.ask("Compound B IC50", limit=1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["task"]["answer"]["display"], "250 nM")

    def test_full_strategy_beats_table_only_on_claim_recall(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate_manifest(ROOT / "examples" / "benchmark" / "manifest.json", directory)
            self.assertGreater(result["strategies"]["full"]["claim_recall"], result["strategies"]["table_only"]["claim_recall"])
            self.assertEqual(result["strategies"]["result_focused"]["claim_recall"], 1.0)
            self.assertLess(result["strategies"]["table_only"]["claim_recall"], 1.0)
            self.assertGreater(result["improvement_result_focused_minus_table_only"]["claim_recall"], 0.0)


class AdapterTests(unittest.TestCase):
    def test_csv_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "measurements.csv"
            path.write_text("Sample,IC50\nA,12.5 uM\nB,250 nM\n", encoding="utf-8")
            document = load_document(path, {"doc_id": "csv:test", "license": "CC-BY-4.0", "year": 2024})
            self.assertEqual(document.tables[0]["rows"][1]["IC50"], "250 nM")

    def test_html_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.html"
            path.write_text(
                "<html><head><title>Demo Paper</title></head><body>"
                "<p>Compound A increased response relative to control.</p>"
                "<table><tr><th>Sample</th><th>IC50</th></tr>"
                "<tr><td>A</td><td>12.5 uM</td></tr></table></body></html>",
                encoding="utf-8",
            )
            document = load_document(path, {"doc_id": "html:test", "license": "CC-BY-4.0", "year": 2024})
            self.assertEqual(document.title, "Demo Paper")
            self.assertEqual(document.tables[0]["rows"][0]["IC50"], "12.5 uM")

    def test_jats_adapter_preserves_section_and_license(self) -> None:
        document = load_document(ROOT / "examples" / "documents" / "pmc_demo.nxml", {"source_url": "https://example.test/pmc_demo"})
        self.assertEqual(document.doc_id, "PMC-DEMO")
        self.assertEqual(document.license, "CC-BY-4.0")
        self.assertEqual(document.paragraphs[0]["section_path"], ["Results"])
        self.assertEqual(document.tables[0]["rows"][0]["IC50"], "5 uM")
        self.assertEqual(document.metadata["source_url"], "https://example.test/pmc_demo")

    def test_jats_figure_alt_text_is_replayable(self) -> None:
        document = load_document(ROOT / "examples" / "documents" / "pmc_demo.nxml")
        self.assertEqual(document.figures[0]["id"], "f1")
        from provsci.miner import mine_figure_numeric_candidates
        candidates = list(mine_figure_numeric_candidates(document))
        self.assertEqual(len(candidates), 1)
        verified = verify_sample(candidates[0].to_sample(document.license, document.title, document.local_path), document)
        self.assertEqual(verified["verification"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
