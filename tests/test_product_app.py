from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from scripts.run_product_app import ProductHandler


ROOT = Path(__file__).resolve().parents[1]


def multipart_file(filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = "----provsci-test-boundary"
    body = b"--" + boundary.encode() + b"\r\n"
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += content
    body += b"\r\n--" + boundary.encode() + b"--\r\n"
    return body, f"multipart/form-data; boundary={boundary}"


class ProductAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ProductHandler.web_root = ROOT / "web"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ProductHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_health_and_product_page(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/api/health", timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["service"], "provsci-product-app")
        with urllib.request.urlopen(f"{self.base_url}/product_workspace.html", timeout=10) as response:
            page = response.read().decode("utf-8")
        self.assertIn("科研数据工作台", page)
        self.assertIn("/api/analyze", page)
        self.assertIn("结构化结果", page)

    def test_real_jats_upload_returns_auditable_results(self) -> None:
        content = (ROOT / "examples" / "real" / "PMC8415024.nxml").read_bytes()
        body, content_type = multipart_file("PMC8415024.nxml", content)
        request = urllib.request.Request(
            f"{self.base_url}/api/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
        self.assertEqual(payload["summary"]["doc_id"], "PMC8415024")
        self.assertGreater(payload["summary"]["total_candidates"], 0)
        self.assertEqual(len(payload["results"]), payload["summary"]["total_candidates"])
        result = next(item for item in payload["results"] if item["entity"] == "SW480" and item["condition"] == "24 h")
        self.assertEqual(result["value"], "15.34 ± 0.81")
        self.assertIn("TABLE 1", result["locator"])
        self.assertTrue(result["path"])
        self.assertEqual(result["quality"], "gold")

    def test_upload_rejects_unsupported_extension(self) -> None:
        body, content_type = multipart_file("payload.exe", b"not a document")
        request = urllib.request.Request(
            f"{self.base_url}/api/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(context.exception.code, 415)


if __name__ == "__main__":
    unittest.main()
