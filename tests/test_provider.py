from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.provsci.provider import ProviderConfig, generate_overview, normalize_provider_config, test_provider


class MockProviderHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/models":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "demo-model"}]}).encode())

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        self.server.last_request = request  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"choices": [{"message": {"content": "本次共找到 2 条数据，其中 1 条可直接使用，1 条建议人工检查。"}}]}).encode())


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockProviderHandler)
        cls.server.last_request = None  # type: ignore[attr-defined]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_normalize_prefers_request_and_hides_key_from_public_config(self) -> None:
        config = normalize_provider_config(
            {"base_url": self.base_url, "model": "demo-model", "api_key": "secret", "enabled": True},
            environ={"PROVSCI_API_BASE_URL": "http://env.invalid/v1", "PROVSCI_API_MODEL": "env-model"},
        )
        self.assertEqual(config.base_url, self.base_url)
        self.assertEqual(config.model, "demo-model")
        self.assertNotIn("api_key", config.public_dict())

    def test_provider_connection_and_optional_overview(self) -> None:
        config = ProviderConfig(base_url=self.base_url, model="demo-model", api_key="secret", enabled=True)
        self.assertEqual(test_provider(config)["ok"], True)
        result = generate_overview(config, {"total_candidates": 2, "gold": 1, "human_review": 1}, [
            {"entity": "A", "metric": "yield", "value": "4", "unit": "%", "condition": "20 C", "quality": "gold"},
        ])
        self.assertEqual(result["status"], "success")
        self.assertIn("可直接使用", result["message"])
        request = self.server.last_request  # type: ignore[attr-defined]
        self.assertEqual(request["model"], "demo-model")
        self.assertEqual(request["temperature"], 0)

    def test_disabled_provider_does_not_call_network(self) -> None:
        result = generate_overview(ProviderConfig(enabled=False), {}, [])
        self.assertEqual(result["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
