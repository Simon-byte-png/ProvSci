from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from provsci.pipeline import run_pipeline
from provsci.review import ReviewError, build_review_queue, record_review_decision
from provsci.review_ui import build_review_html, create_review_server, render_review_html


class ReviewUITests(unittest.TestCase):
    def _run_review(self, root: Path) -> tuple[Path, str]:
        document = {
            "doc_id": "review-ui:test",
            "title": "Review UI test",
            "year": 2024,
            "license": "CC-BY-4.0",
            "local_path": "review-ui.json",
            "tables": [{
                "id": "Table 1",
                "page": 1,
                "caption": "Measured result after 2 h.",
                "rows": [{"Sample": "Compound A", "IC50": "12.5 uM"}],
            }],
        }
        input_path = root / "review-ui.json"
        output_path = root / "run"
        input_path.write_text(json.dumps(document), encoding="utf-8")
        run_pipeline(input_path, output_path)
        sample_id = json.loads((output_path / "all.jsonl").read_text(encoding="utf-8").splitlines()[0])["id"]
        # Create a deterministic Human Review item without hand-writing a
        # partial sample; the normal modify/reverify flow remains exercised.
        record_review_decision(output_path, sample_id, "modify", "seed", changes={"task.answer.value": 999.0})
        return output_path, sample_id

    def test_render_and_static_snapshot_include_review_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run, sample_id = self._run_review(Path(directory))
            queue = build_review_queue(run)
            rendered = render_review_html(queue, interactive=False)
            self.assertIn(sample_id, rendered)
            self.assertIn("ResultCard", rendered)
            self.assertIn("acquisition path", rendered)
            self.assertIn("evidence", rendered.lower())
            self.assertIn("12.5", rendered)
            unsafe_queue = [dict(queue[0], source=dict(queue[0]["source"], source_url="javascript:alert(1)"))]
            unsafe_rendered = render_review_html(unsafe_queue, interactive=False)
            self.assertNotIn('href="javascript:', unsafe_rendered)

            destination = Path(directory) / "snapshot" / "review.html"
            self.assertEqual(build_review_html(run, destination), destination)
            self.assertTrue(destination.exists())
            self.assertIn(sample_id, destination.read_text(encoding="utf-8"))

    def test_server_supports_queue_review_and_rejects_unsafe_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run, sample_id = self._run_review(Path(directory))
            with self.assertRaises(ReviewError):
                create_review_server(run, host="0.0.0.0", port=0)
            server = create_review_server(run, port=0)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(base + "/", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(sample_id, response.read().decode("utf-8"))
                with urlopen(base + "/api/queue", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    queue = json.loads(response.read().decode("utf-8"))
                    self.assertEqual([item["sample_id"] for item in queue], [sample_id])

                invalid = Request(
                    base + "/api/review",
                    data=json.dumps({"sample_id": sample_id, "decision": "drop", "reviewer": "alice"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(invalid, timeout=2)
                self.assertEqual(error.exception.code, 400)

                reject = Request(
                    base + "/api/review",
                    data=json.dumps({
                        "sample_id": sample_id,
                        "decision": "reject",
                        "reviewer": "alice",
                        "comment": "not suitable for this generic profile",
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(reject, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read().decode())["decision"], "reject")
                with urlopen(base + "/api/queue", timeout=2) as response:
                    self.assertEqual(json.loads(response.read().decode()), [])
                decisions = (run / "review_decisions.jsonl").read_text(encoding="utf-8").splitlines()
                self.assertEqual(json.loads(decisions[-1])["decision"], "reject")

                unsafe = Request(base + "/all.jsonl", method="GET")
                with self.assertRaises(HTTPError) as error:
                    urlopen(unsafe, timeout=2)
                self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
