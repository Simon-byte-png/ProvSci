from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
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
from provsci.review import build_review_queue, record_review_decision
from provsci.retry import retry_run
from provsci.ablation import evaluate_module_ablation
from provsci.adversarial import evaluate_adversarial_cases
from provsci.supplements import SupplementError, attach_supplement
from provsci.layout_adapters import DoclingAdapter, OptionalParserUnavailable


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

    def test_generic_scientific_units_and_conversion(self) -> None:
        from provsci.values import extract_measurement_occurrences

        values = extract_measurement_occurrences("yield was 85 %, temperature was 37 C, pressure was 2 kPa, duration was 2 day")
        self.assertEqual([(item[2].value, item[2].unit) for item in values], [
            (85.0, "%"), (37.0, "C"), (2.0, "kPa"), (2.0, "day"),
        ])

    def test_generic_length_units_and_conversion(self) -> None:
        self.assertEqual(parse_number_unit("2 μm").unit, "μm")
        self.assertAlmostEqual(convert(parse_number_unit("2 μm"), "m").value, 2e-6)
        self.assertAlmostEqual(convert(parse_number_unit("1 nm"), "μm").value, 1e-3)

    def test_temperature_symbol_conversion(self) -> None:
        self.assertAlmostEqual(convert(parse_number_unit("37 °C"), "K").value, 310.15)
        self.assertAlmostEqual(convert(parse_number_unit("310.15 K"), "°C").value, 37.0)

    def test_generic_profile_units_are_parseable(self) -> None:
        profile = json.loads((ROOT / "schemas" / "scientific_quantitative_result_profile.json").read_text())
        declared = {unit for units in profile["unit_policy"].values() for unit in units}
        for unit in declared:
            self.assertEqual(parse_number_unit(f"1 {unit}").unit, unit)


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

    def test_table_caption_condition_and_specialized_row_label_are_preserved(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "table:caption-condition", "title": "Caption condition", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "table.json",
            "tables": [{
                "id": "Table 1", "page": 1,
                "caption": "Cells were collected after 48 h and analyzed.",
                "rows": [{
                    "hPMTs": "H3 K27me3",
                    "Mean / Hs27": "1.25%",
                    "Standard Error / Hs27": "0.10%",
                    "p-Value": "0.05",
                }],
            }],
        })
        from provsci.miner import mine_numeric_table_candidates
        candidates = list(mine_numeric_table_candidates(document))
        candidate = candidates[0]
        self.assertEqual(candidate.answer["entity"], "H3 K27me3")
        self.assertEqual(candidate.answer["metric"], "mean")
        self.assertEqual(candidate.answer["condition"], "48 h")
        self.assertEqual(candidate.answer["condition_source"], "table_caption")
        self.assertEqual(candidate.answer["condition_fields"]["exposure_time_or_duration"], "48 h")
        self.assertEqual([item.answer["metric"] for item in candidates], ["mean", "standard error", "p-value"])

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

    def test_supplement_path_reproduces_value(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "supp:test", "title": "Supplement", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "paper.nxml",
            "supplements": [{"id": "sup1", "text": "IC50 for SW480 was 12.5 μM."}],
        })
        from provsci.miner import mine_supplement_numeric_candidates
        candidate = next(iter(mine_supplement_numeric_candidates(document)))
        verified = verify_sample(candidate.to_sample(document.license, document.title, document.local_path), document)
        self.assertEqual(verified["verification"]["status"], "pass")
        self.assertEqual(verified["evidence"][0]["modality"], "supplement")

    def test_structured_figure_point_path_reproduces_value(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "figure:curve", "title": "Structured curve", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "curve.json",
            "figures": [{
                "id": "Figure 1",
                "caption": "Measured yield over time",
                "axes": {
                    "x": {"label": "time", "unit": "h"},
                    "y": {"label": "yield", "unit": "%"},
                },
                "series": [{"name": "Batch A", "points": [{"x": 0, "y": 60}, {"x": 2, "y": 82}]}],
            }],
        })
        from provsci.miner import mine_figure_numeric_candidates
        candidates = list(mine_figure_numeric_candidates(document))
        self.assertEqual(len(candidates), 2)
        candidate = candidates[1]
        self.assertEqual(candidate.answer["condition"], "time=2 h")
        self.assertEqual(candidate.evidence[0]["locator"]["point_index"], 1)
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        verified = verify_sample(sample, document)
        self.assertEqual(verified["verification"]["status"], "pass")
        self.assertEqual(verified["verification"]["recomputed"]["value"], 82.0)
        sample["evidence"][0]["locator"]["point_index"] = 0
        tampered = verify_sample(sample, document)
        self.assertEqual(tampered["verification"]["status"], "fail")
        self.assertEqual(tampered["quality"]["failure_mode"], "evidence_mismatch")


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
            self.assertEqual(gold[0]["source"]["retrieval_method"], "local_file")
            self.assertTrue(summary["source"]["source_version"].startswith("sha256:"))
            self.assertGreaterEqual(summary["runtime_seconds"], 0.0)
            self.assertEqual(summary["estimated_cost_usd"], 0.0)
            self.assertTrue(gold[0]["verification"]["evidence_checked"])
            self.assertEqual(gold[0]["result_card"]["schema_version"], "result_card.v1")
            self.assertIn("condition", gold[0]["result_card"])
            self.assertTrue(validate_sample_contract(gold[0]) == [])
            self.assertTrue((Path(directory) / "result_cards.jsonl").exists())
            self.assertTrue((Path(directory) / "result_cards.csv").exists())
            self.assertTrue((Path(directory) / "data_card.json").exists())
            data_card = json.loads((Path(directory) / "data_card.json").read_text())
            self.assertEqual(data_card["schema_version"], "provsci.data_card.v1")
            self.assertEqual(data_card["sample_count"], 6)
            self.assertEqual(data_card["quality_counts"], {"gold": 6})
            self.assertEqual(data_card["domain_counts"], {"scientific_quantitative_result_v1": 6})

    def test_default_run_uses_generic_quantitative_profile(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "generic:result", "title": "Generic result", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "generic.json",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Results"],
                "text": "Sample A achieved a yield of 85 % at 37 C.",
            }],
        })
        candidate = next(iter(mine_numeric_text_candidates(document)))
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        self.assertEqual(sample["result_card"]["domain"], "scientific_quantitative_result_v1")

    def test_generic_demo_contains_multiple_measurement_metrics(self) -> None:
        generic_demo = ROOT / "examples" / "documents" / "generic_results_demo.json"
        with tempfile.TemporaryDirectory() as directory:
            summary = run_pipeline(generic_demo, directory)
            self.assertEqual(summary["total_candidates"], 6)
            self.assertEqual(summary["gold"], 6)
            rows = [json.loads(line) for line in (Path(directory) / "gold.jsonl").read_text().splitlines()]
            self.assertEqual({row["result_card"]["metric"] for row in rows}, {"yield", "temperature", "pressure"})
            self.assertEqual({row["result_card"]["entity"] for row in rows}, {"Batch A", "Batch B"})
            self.assertEqual({row["result_card"]["condition"]["text"] for row in rows}, {"2 h"})
            self.assertEqual({row["result_card"]["condition"]["source"] for row in rows}, {"table_caption"})

    def test_structured_curve_demo_runs_through_multimodal_pipeline(self) -> None:
        curve_demo = ROOT / "examples" / "documents" / "structured_curve_demo.json"
        with tempfile.TemporaryDirectory() as directory:
            summary = run_pipeline(curve_demo, directory, strategy="multimodal")
            self.assertEqual(summary["total_candidates"], 6)
            self.assertEqual(summary["gold"], 6)
            self.assertEqual(summary["path_reproducibility"], 1.0)
            rows = [json.loads(line) for line in (Path(directory) / "gold.jsonl").read_text().splitlines()]
            self.assertEqual({row["evidence"][0]["modality"] for row in rows}, {"figure"})
            self.assertEqual({row["result_card"]["condition"]["source"] for row in rows}, {"figure_axis"})

    def test_generic_result_prose_keeps_labeled_measurements_and_conditions(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "generic:prose", "title": "Generic prose", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "generic.txt",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Quantitative Results"],
                "text": (
                    "Batch A achieved a yield of 85 %; temperature was 37 C and "
                    "pressure was 2 kPa, measured using spectroscopy."
                ),
            }],
        })
        from provsci.batch import mine_candidates
        candidates = mine_candidates(document, "result_focused")
        self.assertEqual({candidate.answer["metric"] for candidate in candidates}, {"yield", "temperature", "pressure"})
        self.assertEqual({candidate.answer["entity"] for candidate in candidates}, {"Batch A"})
        yield_candidate = next(candidate for candidate in candidates if candidate.answer["metric"] == "yield")
        self.assertEqual(yield_candidate.answer["condition_fields"]["temperature"], "37 C")
        self.assertEqual(yield_candidate.answer["condition_fields"]["pressure"], "2 kPa")
        self.assertEqual(yield_candidate.answer["condition_fields"]["assay_or_method"], "spectroscopy")
        sample = yield_candidate.to_sample(document.license, document.title, document.local_path)
        self.assertEqual(sample["result_card"]["condition"]["source"], "local_text")

    def test_generic_result_paragraph_router_uses_measurement_terms(self) -> None:
        from provsci.miner import is_result_paragraph
        self.assertTrue(is_result_paragraph({"text": "The measured pressure was 2 kPa."}))
        self.assertTrue(is_result_paragraph({"section_path": ["Characterization"], "text": "Value: 2 kPa."}))

    def test_generic_result_prose_supports_non_biomedical_measurements(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "generic:length", "title": "Generic length", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "generic.txt",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Characterization"],
                "text": "Particle diameter was 2 μm for Sample A.",
            }],
        })
        from provsci.batch import mine_candidates
        candidates = mine_candidates(document, "result_focused")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].answer["metric"], "diameter")
        self.assertEqual(candidates[0].answer["entity"], "Sample A")

    def test_single_run_accepts_profile_domain_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_pipeline(DEMO, output, metadata={"domain": "example_specialization_v1"})
            row = json.loads((output / "all.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["result_card"]["domain"], "example_specialization_v1")

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

    def test_tampered_character_span_cannot_repoint_repeated_text_evidence(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "span:test", "title": "Repeated spans", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "span.txt",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Results"],
                "text": "Response was 42 % for sample A; control response was 42 %.",
            }],
        })
        from provsci.miner import mine_numeric_text_candidates
        candidate = next(iter(mine_numeric_text_candidates(document)))
        sample = candidate.to_sample(document.license, document.title, document.local_path)
        source_text = document.paragraphs[0]["text"]
        second_start = source_text.rindex("42 %")
        sample["evidence"][0]["locator"]["char_span"] = [second_start, second_start + len("42 %")]
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

    def test_numeric_text_binds_each_value_to_following_cell_line(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "cell-line:list", "title": "Cell-line list", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "paper.nxml",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Results"],
                "text": (
                    "The IC50 values were calculated as 13 µM in MCF‐7 cells "
                    "and 16 µM in MDA‐MB‐231 cells."
                ),
            }],
        })
        from provsci.batch import mine_candidates
        candidates = mine_candidates(document, "result_focused")
        self.assertEqual([c.answer["entity"] for c in candidates], ["MCF-7", "MDA-MB-231"])
        self.assertEqual(candidates[0].answer["condition_fields"]["cell_line"], "MCF-7")
        self.assertEqual(candidates[1].answer["condition_fields"]["cell_line"], "MDA-MB-231")

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

    def test_distant_ic50_mention_does_not_relabel_dose_condition(self) -> None:
        document = DocumentPackage.from_dict({
            "doc_id": "condition:ic50", "title": "Condition", "year": 2024,
            "license": "CC-BY-4.0", "local_path": "paper.nxml",
            "paragraphs": [{
                "id": "p1", "page": 1, "section_path": ["Results"],
                "text": "Consistent with IC50, cells were treated at 5 μM and became rounded.",
            }],
        })
        from provsci.batch import mine_candidates
        self.assertEqual(mine_candidates(document, "result_focused"), [])

    def test_conflicting_values_are_routed_to_human_review(self) -> None:
        document = {
            "doc_id": "conflict:test",
            "title": "Conflicting result reports",
            "year": 2024,
            "license": "CC-BY-4.0",
            "local_path": "conflict.json",
            "tables": [
                {
                    "id": "Table 1",
                    "page": 1,
                    "rows": [{"Sample": "Compound A", "IC50": "10 uM"}],
                },
                {
                    "id": "Table 2",
                    "page": 2,
                    "rows": [{"Sample": "Compound A", "IC50": "12 uM"}],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "conflict.json"
            output_path = Path(directory) / "run"
            input_path.write_text(json.dumps(document), encoding="utf-8")
            summary = run_pipeline(input_path, output_path, strategy="result_focused")

            self.assertEqual(summary["total_candidates"], 2)
            self.assertEqual(summary["gold"], 0)
            self.assertEqual(summary["silver"], 2)
            self.assertEqual(summary["human_review"], 2)
            self.assertEqual(summary["conflict_groups"], 1)
            self.assertEqual(summary["conflict_claims"], 2)
            rows = [json.loads(line) for line in (output_path / "human_review.jsonl").read_text().splitlines()]
            self.assertEqual({row["quality"]["failure_mode"] for row in rows}, {"conflicting_values"})
            self.assertEqual({row["result_card"]["duplicate_status"] for row in rows}, {"conflict"})
            self.assertEqual(len({row["result_card"]["conflict_group_id"] for row in rows}), 1)

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
            self.assertEqual(summary["human_review"], 5)
            self.assertTrue(all(
                json.loads(line)["quality"]["failure_mode"] == "license_unknown"
                for line in (Path(directory) / "human_review.jsonl").read_text().splitlines()
            ))

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
            self.assertEqual(summary["conflict_groups"], 0)
            self.assertEqual(summary["conflict_claims"], 0)

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
            result = evaluate_manifest(ROOT / "examples" / "benchmark" / "p0-gold-manifest.json", directory)
            self.assertGreater(result["strategies"]["full"]["claim_recall"], result["strategies"]["table_only"]["claim_recall"])
            self.assertEqual(result["strategies"]["result_focused"]["claim_recall"], 1.0)
            self.assertEqual(result["strategies"]["result_focused"]["evidence_locator_precision"], 1.0)
            self.assertEqual(result["strategies"]["result_focused"]["evidence_locator_recall"], 1.0)
            self.assertEqual(result["strategies"]["result_focused"]["table_value_match_rate"], 1.0)
            self.assertEqual(result["strategies"]["result_focused"]["condition_match_rate"], 1.0)
            self.assertGreaterEqual(result["strategies"]["result_focused"]["runtime_seconds"], 0.0)
            self.assertEqual(result["comparison_protocol"]["rule_baselines"], ["table_only", "full"])
            self.assertFalse(result["comparison_protocol"]["model_calls"])
            self.assertLess(result["strategies"]["table_only"]["claim_recall"], 1.0)
            self.assertGreater(result["improvement_result_focused_minus_table_only"]["claim_recall"], 0.0)

    def test_condition_matching_metric_detects_wrong_annotation(self) -> None:
        raw = json.loads((ROOT / "examples" / "benchmark" / "p0-gold-manifest.json").read_text())
        raw["documents"][1]["expected_claims"][0]["condition"] = "48 h"
        benchmark_root = ROOT / "examples" / "benchmark"
        for entry in raw["documents"]:
            entry["path"] = str((benchmark_root / entry["path"]).resolve())
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "condition-manifest.json"
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            result = evaluate_manifest(manifest, Path(directory) / "evaluation", strategies=("result_focused",))
            self.assertEqual(result["strategies"]["result_focused"]["condition_match_rate"], 0.8333)

    def test_table_value_metric_detects_wrong_annotation(self) -> None:
        raw = json.loads((ROOT / "examples" / "benchmark" / "p0-gold-manifest.json").read_text())
        raw["documents"][1]["expected_claims"][0]["value"] = 999.0
        benchmark_root = ROOT / "examples" / "benchmark"
        for entry in raw["documents"]:
            entry["path"] = str((benchmark_root / entry["path"]).resolve())
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "table-value-manifest.json"
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            result = evaluate_manifest(manifest, Path(directory) / "evaluation", strategies=("result_focused",))
            self.assertEqual(result["strategies"]["result_focused"]["table_value_match_rate"], 0.8333)

    def test_module_ablation_reports_quality_gate_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate_module_ablation(
                ROOT / "examples" / "benchmark" / "p0-gold-manifest.json",
                Path(directory) / "ablation",
            )
            variants = result["variants"]
            self.assertEqual(result["production_baseline"], "all_gates")
            self.assertEqual(variants["all_gates"]["gold_like_count"], 46)
            self.assertEqual(variants["without_quality_gate"]["gold_like_count"], 52)
            self.assertEqual(variants["all_gates"]["claim_recall"], 0.8846)
            self.assertEqual(variants["without_quality_gate"]["claim_recall"], 1.0)
            self.assertEqual(variants["without_verifier"]["selected_count"], 46)
            self.assertEqual(variants["without_license_gate"]["selected_count"], 46)
            self.assertEqual(variants["without_evidence_path_gate"]["selected_count"], 46)
            self.assertEqual(
                result["gate_rejection_counts"],
                {"quality": 6, "verifier": 0, "license": 0, "evidence": 0, "acquisition_path": 0},
            )
            self.assertTrue((Path(directory) / "ablation" / "ablation.json").exists())

    def test_module_ablation_separates_unknown_license_from_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate_module_ablation(
                ROOT / "examples" / "benchmark" / "manifest.json",
                Path(directory) / "ablation",
            )
            self.assertEqual(result["gate_rejection_counts"]["license"], 5)
            self.assertEqual(result["gate_rejection_counts"]["quality"], 0)
            self.assertEqual(result["variants"]["all_gates"]["selected_count"], 36)
            self.assertEqual(result["variants"]["without_license_gate"]["selected_count"], 41)

    def test_adversarial_cases_are_rejected_by_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate_adversarial_cases(
                ROOT / "examples" / "benchmark" / "p0-gold-manifest.json",
                Path(directory) / "adversarial",
            )
            self.assertEqual(result["case_count"], 5)
            self.assertEqual(result["missing_cases"], [])
            self.assertTrue(result["all_cases_rejected"])
            self.assertEqual(result["verifier_rejection_rate"], 1.0)
            self.assertEqual(result["would_be_selected_without_verifier_count"], 3)
            self.assertEqual(result["would_be_selected_without_verifier_rate"], 0.6)
            observed = result["observed_failure_mode_counts"]
            self.assertEqual(observed["answer_mismatch"], 1)
            self.assertEqual(observed["evidence_mismatch"], 1)
            self.assertEqual(observed["missing_evidence"], 1)
            self.assertEqual(observed["missing_acquisition_path"], 1)
            self.assertEqual(observed["path_execution_error"], 1)
            cases = {case["case"]: case for case in result["cases"]}
            self.assertTrue(cases["tampered_answer"]["would_be_selected_without_verifier"])
            self.assertTrue(cases["tampered_evidence"]["would_be_selected_without_verifier"])
            self.assertFalse(cases["missing_evidence"]["gate_states"]["evidence"])
            self.assertTrue((Path(directory) / "adversarial" / "adversarial.jsonl").exists())


class ReviewTests(unittest.TestCase):
    def _run_one(self, root: Path, license_name: str = "CC-BY-4.0") -> tuple[Path, str]:
        document = {
            "doc_id": "review:test",
            "title": "Review test",
            "year": 2024,
            "license": license_name,
            "local_path": "review.json",
            "tables": [{"id": "Table 1", "page": 1, "rows": [{"Sample": "Compound A", "IC50": "12.5 uM"}]}],
        }
        input_path = root / "review.json"
        output_path = root / "run"
        input_path.write_text(json.dumps(document), encoding="utf-8")
        run_pipeline(input_path, output_path)
        sample_id = json.loads((output_path / "all.jsonl").read_text().splitlines()[0])["id"]
        return output_path, sample_id

    def test_review_accept_is_append_only_and_keeps_license_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, sample_id = self._run_one(Path(directory), license_name="unknown")
            record = record_review_decision(output, sample_id, "accept", "alice", comment="Evidence is clear")
            self.assertEqual(record["decision"], "accept")
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["gold"], 0)
            self.assertEqual(summary["silver"], 1)
            self.assertEqual(summary["human_review"], 0)
            self.assertEqual(summary["review_decisions"], 1)
            self.assertTrue((output / "review_decisions.jsonl").exists())
            row = json.loads((output / "all.jsonl").read_text().splitlines()[0])
            self.assertFalse(row["quality"]["needs_human_review"])
            self.assertEqual(row["quality"]["failure_mode"], "license_unknown")

    def test_review_modify_reverifies_and_reject_is_separate_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, sample_id = self._run_one(Path(directory))
            record_review_decision(
                output,
                sample_id,
                "modify",
                "bob",
                changes={"task.answer.value": 999.0},
            )
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["gold"], 0)
            self.assertEqual(summary["human_review"], 1)
            row = json.loads((output / "all.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["quality"]["failure_mode"], "answer_mismatch")
            record_review_decision(output, sample_id, "reject", "bob", comment="Not a valid claim")
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["gold"], 0)
            self.assertEqual(summary["silver"], 0)
            self.assertEqual(summary["human_review"], 0)
            self.assertEqual(summary["rejected"], 1)
            rejected = (output / "rejected.jsonl").read_text().splitlines()
            self.assertEqual(len(rejected), 1)
            self.assertEqual(json.loads(rejected[0])["quality"]["failure_mode"], "human_rejected")

    def test_review_queue_is_ranked_and_omits_rejected_samples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, sample_id = self._run_one(Path(directory))
            # Turn the clean sample into a review item, then derive a queue.
            record_review_decision(output, sample_id, "modify", "bob", changes={"task.answer.value": 999.0})
            queue = build_review_queue(output)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["rank"], 1)
            self.assertEqual(queue[0]["failure_mode"], "answer_mismatch")
            self.assertEqual(queue[0]["recommended_action"], "inspect_path_and_replay")
            self.assertTrue((output / "review_queue.jsonl").exists())
            record_review_decision(output, sample_id, "reject", "bob")
            self.assertEqual((output / "review_queue.jsonl").read_text(), "")


class RetryTests(unittest.TestCase):
    def test_retry_uses_fallback_strategy_and_preserves_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "retry"
            initial = run_pipeline(DEMO, first, strategy="table_only")
            retried = retry_run(first, second)
            self.assertEqual(initial["strategy"], "table_only")
            self.assertEqual(retried["strategy"], "result_focused")
            self.assertEqual(retried["retry_strategy"], "result_focused")
            self.assertEqual(retried["total_candidates"], 6)
            self.assertEqual(retried["gold"], 6)
            self.assertTrue((second / "retry.json").exists())
            retry_info = json.loads((second / "retry.json").read_text())
            self.assertEqual(retry_info["previous_strategy"], "table_only")
            self.assertEqual(retry_info["resolved_inputs"], [str(DEMO)])


class AdapterTests(unittest.TestCase):
    def test_docling_adapter_normalizes_structured_export_without_dependency(self) -> None:
        class FakeDocument:
            def export_to_dict(self):
                return {
                    "schema_name": "DoclingDocument",
                    "version": "fake-1",
                    "name": "Layout paper",
                    "texts": [{"text": "IC50 was 5 uM.", "prov": [{"page_no": 2, "bbox": {"l": 1, "b": 2, "r": 3, "t": 4}}]}],
                    "tables": [{
                        "label": "Table 1",
                        "prov": [{"page_no": 2}],
                        "data": {
                            "num_rows": 2,
                            "num_cols": 2,
                            "table_cells": [
                                {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Sample", "column_header": True},
                                {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "IC50", "column_header": True},
                                {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "SW480"},
                                {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text": "5 uM"},
                            ],
                        },
                    }],
                    "pictures": [{"id": "fig1", "caption": "Dose response", "prov": [{"page_no": 3}]}],
                }

            def __repr__(self):
                return "FakeDocument()"

        class FakeConverter:
            def convert(self, path):
                self.path = path
                return type("Result", (), {"document": FakeDocument()})()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.pdf"
            path.write_bytes(b"fake pdf")
            document = load_document(path, {
                "doc_id": "docling:test", "license": "CC-BY-4.0", "year": 2024,
                "domain": "biomedical_cell_viability_v1",
            }, adapter=DoclingAdapter(converter_factory=FakeConverter))
            self.assertEqual(document.title, "Layout paper")
            self.assertEqual(document.paragraphs[0]["page"], 2)
            self.assertEqual(document.paragraphs[0]["bbox"], [1.0, 2.0, 3.0, 4.0])
            self.assertEqual(document.tables[0]["rows"][0]["IC50"], "5 uM")
            self.assertEqual(document.tables[0]["page"], 2)
            self.assertEqual(document.figures[0]["id"], "fig1")
            self.assertEqual(document.metadata["adapter"], "docling_v0.1")

    def test_docling_adapter_reports_missing_optional_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.pdf"
            path.write_bytes(b"fake pdf")
            adapter = DoclingAdapter()
            with patch("provsci.layout_adapters.importlib.import_module", side_effect=ImportError("not installed")):
                with self.assertRaises(OptionalParserUnavailable):
                    adapter.load(path)

    def test_docling_table_without_header_markers_preserves_first_data_row(self) -> None:
        from provsci.layout_adapters import _docling_tables

        exported = {
            "tables": [{
                "id": "Table data",
                "data": {
                    "num_rows": 2,
                    "num_cols": 2,
                    "table_cells": [
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "SW480"},
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "5 uM"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "SW1116"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text": "6 uM"},
                    ],
                },
            }],
        }
        tables = _docling_tables(exported)
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]["rows"]), 2)
        self.assertEqual(tables[0]["rows"][0]["column_1"], "SW480")

    def test_docling_table_infers_obvious_unmarked_header(self) -> None:
        from provsci.layout_adapters import _docling_tables

        exported = {
            "tables": [{
                "id": "Table header",
                "data": {
                    "rows": [["Sample", "IC50"], ["SW480", "5 uM"]],
                },
            }],
        }
        tables = _docling_tables(exported)
        self.assertEqual(tables[0]["columns"], ["Sample", "IC50"])
        self.assertEqual(tables[0]["rows"], [{"Sample": "SW480", "IC50": "5 uM"}])

    def test_csv_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "measurements.csv"
            path.write_text("Sample,IC50\nA,12.5 uM\nB,250 nM\n", encoding="utf-8")
            document = load_document(path, {"doc_id": "csv:test", "license": "CC-BY-4.0", "year": 2024})
            self.assertEqual(document.tables[0]["rows"][1]["IC50"], "250 nM")

    def test_custom_document_adapter_is_replaceable(self) -> None:
        class StubAdapter:
            name = "stub_layout_v1"

            def supports(self, source: Path) -> bool:
                return source.suffix == ".stub"

            def load(self, source: Path, metadata: dict[str, object] | None = None) -> DocumentPackage:
                return DocumentPackage.from_dict({
                    "doc_id": "stub:test",
                    "title": "Stub document",
                    "year": 2024,
                    "license": "CC-BY-4.0",
                    "local_path": str(source),
                    "paragraphs": [{"id": "p1", "page": 1, "text": "IC50 was 5 uM."}],
                    "metadata": dict(metadata or {}),
                })

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.stub"
            path.write_text("layout parser input", encoding="utf-8")
            document = load_document(path, {"domain": "biomedical_cell_viability_v1"}, adapter=StubAdapter())
            self.assertEqual(document.doc_id, "stub:test")
            self.assertEqual(document.metadata["adapter"], "stub_layout_v1")
            self.assertEqual(document.metadata["domain"], "biomedical_cell_viability_v1")

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

    def test_jats_adapter_preserves_inline_supplement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supp.nxml"
            path.write_text(
                '<article><front><article-meta><article-id pub-id-type="pmcid">PMC1</article-id>'
                '<title-group><article-title>Supplement test</article-title></title-group>'
                '<permissions><license><license-p>CC BY</license-p></license></permissions>'
                '</article-meta></front><body><supplementary-material id="sup1">'
                '<label>Supplementary Table 1</label><p>IC50 was 12.5 μM.</p>'
                '</supplementary-material></body></article>',
                encoding="utf-8",
            )
            document = load_document(path)
            self.assertEqual(document.supplements[0]["id"], "sup1")
            self.assertIn("12.5 μM", document.supplements[0]["text"])

    def test_jats_figure_alt_text_is_replayable(self) -> None:
        document = load_document(ROOT / "examples" / "documents" / "pmc_demo.nxml")
        self.assertEqual(document.figures[0]["id"], "f1")
        from provsci.miner import mine_figure_numeric_candidates
        candidates = list(mine_figure_numeric_candidates(document))
        self.assertEqual(len(candidates), 1)
        verified = verify_sample(candidates[0].to_sample(document.license, document.title, document.local_path), document)
        self.assertEqual(verified["verification"]["status"], "pass")

    def test_pdf_adapter_preserves_page_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.pdf"
            path.write_bytes(b"%PDF-1.4 placeholder")
            fake = type("Result", (), {"stdout": "Results\n\nIC50 was 5 uM.\fMore results\n\nViability was 80 %.", "returncode": 0})()
            with patch("provsci.adapters.subprocess.run", return_value=fake):
                document = load_document(path, {
                    "doc_id": "pdf:test", "license": "CC-BY-4.0", "year": 2024,
                    "domain": "biomedical_cell_viability_v1",
                })
            self.assertEqual([p["page"] for p in document.paragraphs], [1, 1, 2, 2])
            self.assertEqual(document.metadata["adapter"], "pdftotext_v0.2")
            self.assertEqual(document.metadata["page_count"], 2)

    def test_fetch_pmc_returns_manifest_provenance(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'<article><permissions><license>CC-BY</license></permissions></article>'

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "PMC123.nxml"
            with patch("provsci.sources.urlopen", return_value=Response()):
                from provsci.sources import fetch_europepmc_jats
                metadata = fetch_europepmc_jats("PMC123", destination)
            self.assertTrue(destination.exists())
            self.assertEqual(metadata["doc_id"], "PMC123")
            self.assertEqual(metadata["retrieval_method"], "europepmc_api")

    def test_fetch_http_source_recovers_jats_metadata_and_hash(self) -> None:
        class Response:
            headers = {"Content-Type": "application/xml"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *args):
                return (
                    b'<article><front><article-meta>'
                    b'<article-id pub-id-type="pmcid">PMC999</article-id>'
                    b'<article-id pub-id-type="doi">10.1234/demo</article-id>'
                    b'<title-group><article-title>Fetched source</article-title></title-group>'
                    b'<pub-date><year>2024</year></pub-date>'
                    b'<permissions><license><license-p>CC BY 4.0</license-p></license></permissions>'
                    b'</article-meta></front></article>'
                )

            def geturl(self):
                return "https://repository.example/final.nxml"

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source.nxml"
            with patch("provsci.sources.urlopen", return_value=Response()):
                from provsci.sources import fetch_http_source
                metadata = fetch_http_source("https://repository.example/article", destination)
            self.assertTrue(destination.exists())
            self.assertEqual(metadata["source_url"], "https://repository.example/final.nxml")
            self.assertEqual(metadata["doc_id"], "PMC999")
            self.assertEqual(metadata["title"], "Fetched source")
            self.assertEqual(metadata["year"], 2024)
            self.assertEqual(metadata["doi"], "10.1234/demo")
            self.assertEqual(metadata["license"], "CC-BY-4.0")
            self.assertEqual(metadata["license_status"], "known")
            self.assertEqual(len(metadata["source_hash"]), 64)
            self.assertEqual(metadata["retrieval_method"], "http_url")

    def test_fetch_http_source_rejects_non_http_and_oversized_response(self) -> None:
        from provsci.sources import SourceError, fetch_http_source
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SourceError):
                fetch_http_source("file:///tmp/article.xml", Path(directory) / "article.xml")

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self, *args):
                    return b"123456"

            with patch("provsci.sources.urlopen", return_value=Response()):
                with self.assertRaises(SourceError):
                    fetch_http_source("https://example.org/article", Path(directory) / "article.bin", max_bytes=5)

    def test_fetch_external_supplement_resolves_href_and_hashes_content(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *args):
                return b"supplement bytes"

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "supplement.pdf"
            with patch("provsci.sources.urlopen", return_value=Response()):
                from provsci.sources import fetch_external_supplement
                metadata = fetch_external_supplement(
                    "https://example.org/articles/PMC1/fullTextXML",
                    "media/supplement.pdf",
                    destination,
                )
            self.assertTrue(destination.exists())
            self.assertEqual(metadata["source_url"], "https://example.org/articles/PMC1/media/supplement.pdf")
            self.assertEqual(metadata["retrieval_method"], "external_supplement_http")
            self.assertEqual(len(metadata["source_hash"]), 64)

    def test_fetch_external_supplement_rejects_non_http_sources(self) -> None:
        from provsci.sources import SourceError, fetch_external_supplement
        with self.assertRaises(SourceError):
            fetch_external_supplement("file:///tmp/article.xml", "supp.pdf", "/tmp/supp.pdf")

    def test_attach_supplement_parses_attachment_and_preserves_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            article = root / "article.json"
            attachment = root / "supplement.csv"
            merged = root / "merged.json"
            article.write_text(json.dumps({
                "doc_id": "supp-article:test",
                "title": "Supplement article",
                "year": 2024,
                "license": "CC-BY-4.0",
                "local_path": str(article),
                "paragraphs": [{"id": "p1", "page": 1, "text": "Main text."}],
            }), encoding="utf-8")
            attachment.write_text("Sample,IC50\nSW480,12.5 uM\n", encoding="utf-8")
            info = attach_supplement(article, attachment, merged, "sup-csv", href="media/supplement.csv")
            self.assertEqual(info["supplement_id"], "sup-csv")
            self.assertEqual(info["supplement_tables"], 1)
            self.assertEqual(len(info["supplement_hash"]), 64)
            raw = json.loads(merged.read_text(encoding="utf-8"))
            self.assertEqual(raw["metadata"]["adapter"], "attached_package_v0.1")
            self.assertEqual(raw["supplements"][0]["href"], "media/supplement.csv")
            self.assertIn("12.5 uM", raw["supplements"][0]["text"])
            run_dir = root / "run"
            summary = run_pipeline(merged, run_dir, strategy="result_focused")
            self.assertGreaterEqual(summary["total_candidates"], 1)
            self.assertEqual(summary["path_reproducibility"], 1.0)

    def test_attach_supplement_rejects_in_place_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            article = root / "article.json"
            attachment = root / "supplement.csv"
            article.write_text(json.dumps({
                "doc_id": "supp-article:test", "title": "A", "year": 2024,
                "license": "CC-BY-4.0", "local_path": str(article),
            }), encoding="utf-8")
            attachment.write_text("Sample,IC50\nSW480,12.5 uM\n", encoding="utf-8")
            with self.assertRaises(SupplementError):
                attach_supplement(article, attachment, article, "sup-csv")

    def test_search_pmc_normalizes_open_access_candidates(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"resultList": {"result": [{
                    "pmcid": "PMC123", "pmid": "99", "doi": "10.1/demo",
                    "title": "Cell viability", "pubYear": "2024", "isOpenAccess": "Y", "license": "CC BY",
                }]}}).encode()

        with patch("provsci.sources.urlopen", return_value=Response()):
            from provsci.sources import search_europepmc
            hits = search_europepmc("cell viability", page_size=1)
        self.assertEqual(hits[0]["pmc_id"], "PMC123")
        self.assertTrue(hits[0]["is_open_access"])
        self.assertIn("fullTextXML", hits[0]["source_url"])


if __name__ == "__main__":
    unittest.main()
