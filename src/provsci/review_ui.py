"""Small local review workbench for ProvSci human-review samples.

The workbench deliberately stays in the standard library.  It can emit a
static HTML snapshot for sharing or run a loopback-only HTTP server whose POST
endpoint delegates to the existing append-only ``record_review_decision``
flow.  The server never exposes the run directory as a generic file server.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .review import ReviewError, build_review_queue, record_review_decision


MAX_REQUEST_BYTES = 256 * 1024


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _json_for_script(value: Any) -> str:
    """Embed JSON safely inside a script tag without closing it accidentally."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _source_label(item: dict[str, Any]) -> str:
    source = item.get("source", {}) or {}
    return " — ".join(
        str(value)
        for value in (source.get("title"), source.get("doc_id"))
        if value not in (None, "")
    ) or "source unavailable"


def render_review_html(queue: list[dict[str, Any]], *, interactive: bool = True) -> str:
    """Render a review queue as a self-contained HTML page."""
    payload = _json_for_script(queue)
    mode = "interactive" if interactive else "snapshot"
    endpoint = "/api/review" if interactive else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ProvSci review workbench</title>
<style>
:root {{ --ink:#172033; --muted:#526071; --line:#d8e0ea; --bg:#f8fafc; --blue:#2563eb; --teal:#0f766e; --orange:#b45309; }}
* {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--bg); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
header {{ padding:18px 24px; border-bottom:1px solid var(--line); background:white; position:sticky; top:0; z-index:2; }}
h1 {{ margin:0 0 4px; font-size:22px; }} h2 {{ margin:0 0 10px; font-size:16px; }} h3 {{ margin:14px 0 6px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
.sub {{ color:var(--muted); }} .notice {{ margin-top:10px; padding:8px 10px; border-radius:6px; background:#fff7ed; color:#92400e; }}
.layout {{ display:grid; grid-template-columns:300px minmax(0,1fr); min-height:calc(100vh - 86px); }}
aside {{ border-right:1px solid var(--line); background:white; overflow:auto; }} .queue-item {{ display:block; width:100%; border:0; border-bottom:1px solid var(--line); padding:12px 14px; text-align:left; background:white; color:var(--ink); cursor:pointer; }}
.queue-item:hover,.queue-item.active {{ background:#eff6ff; }} .rank {{ color:var(--blue); font-weight:700; margin-right:6px; }} .failure {{ color:var(--orange); font-size:12px; }} .priority {{ float:right; color:var(--muted); font-size:12px; }}
main {{ padding:22px; overflow:auto; }} .columns {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; align-items:start; }}
.panel {{ background:white; border:1px solid var(--line); border-radius:8px; padding:14px; min-width:0; }} .panel.wide {{ grid-column:1/-1; }}
.kv {{ display:grid; grid-template-columns:120px minmax(0,1fr); gap:5px 10px; margin:0; }} .kv dt {{ color:var(--muted); }} .kv dd {{ margin:0; overflow-wrap:anywhere; }}
pre {{ margin:6px 0 0; max-height:310px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; background:#f1f5f9; border-radius:6px; padding:9px; font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; }}
.evidence {{ border-left:3px solid var(--teal); padding-left:10px; margin:8px 0; }} .span {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
label {{ display:block; color:var(--muted); font-size:12px; margin:8px 0 3px; }} input,textarea {{ width:100%; border:1px solid var(--line); border-radius:5px; padding:7px; font:inherit; }} textarea {{ min-height:58px; resize:vertical; }}
.actions {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }} button {{ border:0; border-radius:5px; padding:8px 13px; color:white; background:var(--blue); cursor:pointer; }} button.reject {{ background:#b91c1c; }} button.modify {{ background:var(--teal); }} button:disabled {{ opacity:.55; cursor:not-allowed; }}
#status {{ margin-top:10px; color:var(--muted); min-height:20px; }} a {{ color:var(--blue); }} .empty {{ padding:24px; color:var(--muted); }}
@media (max-width:900px) {{ .layout {{ grid-template-columns:1fr; }} aside {{ max-height:260px; border-right:0; border-bottom:1px solid var(--line); }} .columns {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body data-mode="{mode}" data-endpoint="{endpoint}">
<header><h1>ProvSci 人工复核工作台</h1><div class="sub">并排查看来源证据、ResultCard、acquisition path、验证状态与许可；决策仍由 verifier 和 Gold 门禁裁决。</div>
<div class="notice">{('本页连接到本机 review server，可提交 accept / modify / reject。' if interactive else '这是静态快照；如需提交决策，请运行 provsci review-serve --run &lt;run&gt;。')}</div></header>
<div class="layout"><aside id="queue"></aside><main id="detail"><div class="empty">请选择左侧待审核样本。</div></main></div>
<script id="queue-data" type="application/json">{payload}</script>
<script>
const queue = JSON.parse(document.getElementById('queue-data').textContent || '[]');
let selected = queue[0] || null;
const interactive = document.body.dataset.mode === 'interactive';
const endpoint = document.body.dataset.endpoint;
const esc = value => String(value === undefined || value === null ? '' : value)
  .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const pretty = value => esc(JSON.stringify(value === undefined ? null : value, null, 2));
const source = item => item.source || {{}};
const card = item => (item.result_card || item.task || {{}});
const sourceLink = value => {{
  const raw = String(value === undefined || value === null ? '' : value);
  // Source metadata is untrusted input; only render navigable HTTP(S) links.
  return /^https?:\\/\\//i.test(raw)
    ? `<a href="${{esc(raw)}}" target="_blank" rel="noreferrer">打开来源</a>`
    : esc(raw || '—');
}};
function renderQueue() {{
  const host = document.getElementById('queue');
  if (!queue.length) {{ host.innerHTML = '<div class="empty">当前没有活动 Human Review 样本。</div>'; return; }}
  host.innerHTML = queue.map((item, index) => `
    <button class="queue-item ${{selected && item.sample_id === selected.sample_id ? 'active' : ''}}" data-id="${{esc(item.sample_id)}}">
      <span class="rank">#${{esc(item.rank || index + 1)}}</span><span class="priority">P${{esc(item.priority)}}</span>
      <div>${{esc(item.doc_id || '')}}</div><div class="failure">${{esc(item.failure_mode || 'unclassified')}}</div>
    </button>`).join('');
  host.querySelectorAll('.queue-item').forEach(button => button.addEventListener('click', () => {{
    selected = queue.find(item => item.sample_id === button.dataset.id) || null; renderQueue(); renderDetail();
  }}));
}}
function renderDetail() {{
  const host = document.getElementById('detail');
  if (!selected) {{ host.innerHTML = '<div class="empty">请选择左侧待审核样本。</div>'; return; }}
  const src = source(selected); const result = card(selected); const evidence = selected.evidence || [];
  const verification = selected.verification || {{}}; const quality = selected.quality || {{}};
  const condition = result.condition || {{}};
  const evidenceHtml = evidence.length ? evidence.map(item => `<div class="evidence"><div><b>${{esc(item.modality || 'unknown')}}</b> · <span class="span">${{esc(JSON.stringify(item.locator || {{}}))}}</span></div><div>${{esc(item.span_text || '')}}</div></div>`).join('') : '<div class="empty">没有可解析证据</div>';
  host.innerHTML = `
    <div class="columns">
      <section class="panel"><h2>来源与证据</h2><dl class="kv">
        <dt>文献</dt><dd>${{esc(src.title || selected.doc_id || '')}}</dd>
        <dt>doc_id</dt><dd>${{esc(selected.doc_id || '')}}</dd>
        <dt>许可</dt><dd>${{esc(src.license || '')}}</dd>
        <dt>hash</dt><dd class="span">${{esc(src.source_hash || '')}}</dd>
        <dt>本地路径</dt><dd class="span">${{esc(src.local_path || '')}}</dd>
        <dt>原文链接</dt><dd>${{sourceLink(src.source_url)}}</dd>
      </dl><h3>Evidence locator</h3>${{evidenceHtml}}</section>
      <section class="panel"><h2>ResultCard</h2><dl class="kv">
        <dt>实体</dt><dd>${{esc(result.entity || result.subject || '')}}</dd>
        <dt>指标</dt><dd>${{esc(result.metric || '')}}</dd>
        <dt>值 / 单位</dt><dd>${{esc(result.display || result.value || '')}} ${{esc(result.unit || '')}}</dd>
        <dt>条件</dt><dd>${{esc(condition.text || '未提取')}} · ${{esc(condition.status || '')}} (${{esc(condition.source || '')}})</dd>
        <dt>问题</dt><dd>${{esc(selected.question || (selected.task || {{}}).question || '')}}</dd>
      </dl><h3>原始与标准化</h3><pre>${{pretty({{raw_value: result.raw_value, normalized_value: result.normalized_value, uncertainty: result.uncertainty}})}}</pre></section>
      <section class="panel"><h2>路径与验证</h2><dl class="kv">
        <dt>失败模式</dt><dd>${{esc(selected.failure_mode || quality.failure_mode || '—')}}</dd>
        <dt>建议动作</dt><dd>${{esc(selected.recommended_action || 'inspect_sample_and_decide')}}</dd>
        <dt>验证状态</dt><dd>${{esc(verification.status || '')}}</dd>
        <dt>证据已检查</dt><dd>${{esc(verification.evidence_checked)}}</dd>
      </dl><h3>acquisition path</h3><pre>${{pretty(selected.acquisition_path || (selected.task || {{}}).acquisition_path || [])}}</pre><h3>verification trace</h3><pre>${{pretty(verification)}}</pre></section>
      <section class="panel wide"><h2>记录决策</h2>
        <label for="reviewer">审核者</label><input id="reviewer" placeholder="例如 alice">
        <label for="comment">备注</label><textarea id="comment" placeholder="记录证据、条件或修订理由"></textarea>
        <label for="changes">修改字段（JSON object，可选；例如 {{&quot;task.answer.value&quot;: 12.5}}）</label><textarea id="changes" placeholder="仅 modify 时填写"></textarea>
        <div class="actions"><button onclick="submitDecision('accept')" ${{interactive ? '' : 'disabled'}}>接受</button><button class="modify" onclick="submitDecision('modify')" ${{interactive ? '' : 'disabled'}}>修改并复核</button><button class="reject" onclick="submitDecision('reject')" ${{interactive ? '' : 'disabled'}}>拒绝</button></div><div id="status"></div>
      </section>
    </div>`;
}}
async function submitDecision(decision) {{
  if (!interactive) {{ document.getElementById('status').textContent = '静态快照不能提交，请运行 review-serve。'; return; }}
  const reviewer = document.getElementById('reviewer').value.trim(); if (!reviewer) {{ document.getElementById('status').textContent = '请填写审核者。'; return; }}
  let changes = null; const rawChanges = document.getElementById('changes').value.trim();
  if (rawChanges) {{ try {{ changes = JSON.parse(rawChanges); }} catch (error) {{ document.getElementById('status').textContent = '修改字段不是合法 JSON。'; return; }} }}
  if (decision === 'modify' && !changes) {{ document.getElementById('status').textContent = 'modify 需要填写 JSON 修改字段。'; return; }}
  const status = document.getElementById('status'); status.textContent = '正在提交…';
  try {{ const response = await fetch(endpoint, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{sample_id:selected.sample_id, decision, reviewer, comment:document.getElementById('comment').value, changes}})}}); const body = await response.json(); if (!response.ok) throw new Error(body.error || 'request failed'); status.textContent = '已记录：' + decision; await refreshQueue(); }} catch (error) {{ status.textContent = '提交失败：' + error.message; }}
}}
async function refreshQueue() {{ if (!interactive) return; const response = await fetch('/api/queue'); const fresh = await response.json(); queue.splice(0, queue.length, ...fresh); selected = queue[0] || null; renderQueue(); renderDetail(); }}
renderQueue(); renderDetail();
</script>
</body></html>"""


def build_review_html(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    """Write a static HTML snapshot and return its path."""
    run = Path(run_dir)
    queue = build_review_queue(run)
    destination = Path(output_path) if output_path is not None else run / "review_workbench.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_review_html(queue, interactive=False), encoding="utf-8")
    return destination


class _ReviewHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], run_dir: Path):
        self.run_dir = run_dir
        super().__init__(server_address, _ReviewRequestHandler)


class _ReviewRequestHandler(BaseHTTPRequestHandler):
    server: _ReviewHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - quiet local UI
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            queue = build_review_queue(self.server.run_dir)
            body = render_review_html(queue, interactive=True).encode("utf-8")
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", body)
            return
        if path == "/api/queue":
            queue = build_review_queue(self.server.run_dir)
            body = json.dumps(queue, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)
            return
        self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found\n")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if urlsplit(self.path).path != "/api/review":
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found\n")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ReviewError("request body is missing or too large")
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ReviewError("request body must be an object")
            result = record_review_decision(
                self.server.run_dir,
                str(payload.get("sample_id", "")),
                str(payload.get("decision", "")),
                str(payload.get("reviewer", "")),
                comment=str(payload.get("comment", "")),
                changes=payload.get("changes"),
            )
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)
        except (ReviewError, ValueError, TypeError, json.JSONDecodeError) as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", body)


def create_review_server(run_dir: str | Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create (but do not start) the loopback review server."""
    run = Path(run_dir)
    if str(host).strip().casefold() not in {"127.0.0.1", "localhost"}:
        raise ReviewError("review server must bind to loopback (127.0.0.1 or localhost)")
    if not (run / "human_review.jsonl").exists():
        raise ReviewError(f"human review queue not found: {run / 'human_review.jsonl'}")
    return _ReviewHTTPServer((host, int(port)), run)


def serve_review_workbench(run_dir: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the workbench until interrupted."""
    server = create_review_server(run_dir, host, port)
    print(f"ProvSci review workbench: http://{server.server_address[0]}:{server.server_address[1]}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()
