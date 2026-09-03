#!/usr/bin/env python3
"""Serve the ProvSci product workspace and expose a small local analyze API."""

from __future__ import annotations

import cgi
import json
import mimetypes
import os
import shutil
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEB_ROOT = ROOT / "web"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _sample_for_ui(sample: dict) -> dict:
    card = sample.get("result_card", {}) or {}
    condition = card.get("condition", {}) or {}
    verification = sample.get("verification", {}) or {}
    quality = sample.get("quality", {}) or {}
    evidence = sample.get("evidence", []) or []
    locator = evidence[0].get("locator", {}) if evidence else {}
    value = card.get("display") or card.get("raw_value")
    if not value and card.get("value") is not None:
        value = str(card.get("value"))
        if card.get("uncertainty") is not None:
            value += f" ± {card['uncertainty']}"
    locator_text = " · ".join(
        part for part in (
            locator.get("table_id") or locator.get("section") or locator.get("modality"),
            f"row {locator['row']}" if locator.get("row") else None,
            f"col {locator['col']}" if locator.get("col") else None,
        ) if part
    ) or "原文证据"
    return {
        "id": sample.get("id"),
        "entity": card.get("entity") or "未命名对象",
        "metric": card.get("metric") or "measurement",
        "value": value or "—",
        "number": card.get("value"),
        "uncertainty": card.get("uncertainty"),
        "unit": card.get("unit") or "—",
        "condition": condition.get("text") or "未标注",
        "locator": locator_text,
        "quality": "gold" if verification.get("status") == "pass" and not quality.get("needs_human_review") else "review",
        "quote": evidence[0].get("span_text") if evidence else value or "—",
        "path": [[step.get("action", "step"), step.get("tool", "deterministic processor")] for step in sample.get("acquisition_path", [])],
    }


class ProductHandler(BaseHTTPRequestHandler):
    web_root = DEFAULT_WEB_ROOT

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(self.path.split("?", 1)[0])
        if path == "/api/health":
            _json_response(self, {"ok": True, "service": "provsci-product-app"})
            return
        if path == "/api/provider-config":
            from provsci.provider import normalize_provider_config

            _json_response(self, {"provider": normalize_provider_config().public_dict()})
            return
        relative = "teacher_dashboard.html" if path in {"", "/"} else path.lstrip("/")
        target = (self.web_root / relative).resolve()
        if self.web_root.resolve() not in target.parents and target != self.web_root.resolve():
            _json_response(self, {"error": "unsafe path"}, 400)
            return
        if not target.is_file():
            _json_response(self, {"error": "not found"}, 404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/provider-test":
            self._test_provider()
            return
        if path != "/api/analyze":
            _json_response(self, {"error": "not found"}, 404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_UPLOAD_BYTES:
            _json_response(self, {"error": "upload is empty or too large"}, 413)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            _json_response(self, {"error": "expected multipart/form-data"}, 415)
            return
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )
        file_field = form["file"] if "file" in form else None
        if file_field is None or not getattr(file_field, "filename", None):
            _json_response(self, {"error": "file field is required"}, 400)
            return
        filename = Path(os.path.basename(file_field.filename)).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".json", ".csv", ".tsv", ".txt", ".md", ".markdown", ".html", ".htm", ".xml", ".nxml", ".pdf", ".xlsx"}:
            _json_response(self, {"error": f"unsupported input format: {suffix or '<none>'}"}, 415)
            return

        # Runtime uploads belong in the ignored work area, not beside the
        # versioned product page under web/.
        upload_root = ROOT / "work" / "product-uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="upload-", dir=upload_root) as task_dir:
            task_path = Path(task_dir) / filename
            with task_path.open("wb") as handle:
                shutil.copyfileobj(file_field.file, handle, length=1024 * 1024)
            output_dir = Path(task_dir) / "run"
            try:
                from provsci.agent import ScientificDataAgent

                summary = ScientificDataAgent().run(task_path, output_dir)
                samples = [json.loads(line) for line in (output_dir / "all.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                ui_results = [_sample_for_ui(sample) for sample in samples]
                payload = {
                    "summary": summary,
                    "source": summary.get("source", {}),
                    "results": ui_results,
                }
                provider_field = form["provider_config"] if "provider_config" in form else None
                provider_settings = None
                if provider_field is not None and getattr(provider_field, "value", ""):
                    try:
                        provider_settings = json.loads(provider_field.value)
                    except json.JSONDecodeError:
                        _json_response(self, {"error": "provider_config must be valid JSON"}, 400)
                        return
                from provsci.provider import generate_overview, normalize_provider_config

                provider = normalize_provider_config(provider_settings)
                if provider.enabled:
                    payload["provider"] = provider.public_dict()
                    payload["ai_review"] = generate_overview(provider, summary, ui_results)
            except Exception as exc:  # pragma: no cover - HTTP boundary
                _json_response(self, {"error": str(exc)}, 422)
                return
        _json_response(self, payload)

    def _test_provider(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > 64 * 1024:
            _json_response(self, {"error": "配置内容为空或过大"}, 400)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            _json_response(self, {"error": "需要 application/json 配置"}, 415)
            return
        try:
            raw = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _json_response(self, {"error": "配置不是有效 JSON"}, 400)
            return
        if not isinstance(raw, dict):
            _json_response(self, {"error": "配置必须是 JSON 对象"}, 400)
            return
        from provsci.provider import normalize_provider_config, test_provider

        config = normalize_provider_config(raw)
        result = test_provider(config)
        _json_response(self, result, 200 if result.get("ok") else 400)


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    host = args[0] if args else "127.0.0.1"
    port = int(args[1]) if len(args) > 1 else 4173
    ProductHandler.web_root = Path(args[2]).resolve() if len(args) > 2 else DEFAULT_WEB_ROOT
    server = ThreadingHTTPServer((host, port), ProductHandler)
    print(f"ProvSci product app: http://{host}:{port}/product_workspace.html", flush=True)
    print(f"Upload API: POST http://{host}:{port}/api/analyze", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
