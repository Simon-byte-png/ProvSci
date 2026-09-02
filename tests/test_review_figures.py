from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_review_figures.py"
MATRIX = ROOT / "examples" / "review" / "literature_matrix.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location("provsci_review_figures", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load review-figure builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviewFigureTests(unittest.TestCase):
    def test_matrix_has_required_representative_records(self) -> None:
        builder = _load_builder()
        matrix = builder.load_matrix(MATRIX)
        self.assertGreaterEqual(len(matrix["records"]), 15)
        self.assertEqual(len({row["id"] for row in matrix["records"]}), len(matrix["records"]))
        self.assertTrue(any(row["uses_llm_vlm"] for row in matrix["records"]))
        self.assertTrue(any(not row["uses_llm_vlm"] for row in matrix["records"]))

    def test_builds_linked_svg_and_tabular_artifacts(self) -> None:
        builder = _load_builder()
        with tempfile.TemporaryDirectory() as directory:
            manifest = builder.build_review_artifacts(MATRIX, directory)
            self.assertEqual(manifest["record_count"], 21)
            for name in manifest["artifacts"]:
                self.assertTrue((Path(directory) / name).exists(), name)
            timeline = (Path(directory) / "timeline.svg").read_text(encoding="utf-8")
            self.assertIn("xlink:href=", timeline)
            self.assertIn("docling", timeline)
            summary = json.loads((Path(directory) / "literature_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["record_count"], 21)
            self.assertIn("by_limitation_tag", summary["counts"])


if __name__ == "__main__":
    unittest.main()
