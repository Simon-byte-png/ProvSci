#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a self-contained visual dashboard from a completed teacher-demo run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def collect_data(run_dir: Path) -> dict[str, Any]:
    real_dir = run_dir / "p0" / "real-smoke"
    summary = json.loads((real_dir / "summary.json").read_text(encoding="utf-8"))
    benchmark = json.loads((run_dir / "p0" / "benchmark" / "evaluation.json").read_text(encoding="utf-8"))
    focused = benchmark["strategies"]["result_focused"]

    table_rows: dict[tuple[str, str], dict[str, Any]] = {}
    source: dict[str, Any] = {}
    for item in read_jsonl(real_dir / "all.jsonl"):
        card = item.get("result_card", {}) or {}
        if item.get("source", {}).get("doc_id") != "PMC8415024":
            continue
        if card.get("metric") != "IC50" or card.get("result_type") != "measurement":
            continue
        evidence = item.get("evidence", []) or []
        if not evidence or evidence[0].get("modality") != "table":
            continue
        condition = card.get("condition", {}) or {}
        time_text = condition.get("text")
        if not time_text:
            continue
        key = (str(card.get("entity", "")), str(time_text))
        table_rows.setdefault(
            key,
            {
                "entity": card.get("entity"),
                "time": time_text,
                "time_hours": _number(str(time_text).split()[0]),
                "value": _number(card.get("value")),
                "uncertainty": _number(card.get("uncertainty")),
                "unit": card.get("unit") or "μM",
                "display": card.get("display") or card.get("raw_value"),
                "card": card,
                "evidence": evidence,
                "path": item.get("acquisition_path", []),
                "verification": item.get("verification", {}),
                "source": item.get("source", {}),
            },
        )
        source = item.get("source", {}) or source

    series: dict[str, list[dict[str, Any]]] = {}
    for row in table_rows.values():
        series.setdefault(str(row["entity"]), []).append(row)
    for values in series.values():
        values.sort(key=lambda row: row["time_hours"])

    review = read_jsonl(real_dir / "human_review.jsonl")
    review_item = review[0] if review else {}
    primary = table_rows.get(("SW480", "24 h"))
    if primary is None and table_rows:
        primary = next(iter(table_rows.values()))
    if primary is None:
        raise RuntimeError("PMC8415024 table measurements were not found in the run")

    return {
        "run_name": run_dir.name,
        "source": source,
        "primary": primary,
        "series": series,
        "summary": {
            "documents": summary.get("document_count", 0),
            "candidates": summary.get("total_candidates", 0),
            "gold": summary.get("gold", 0),
            "human_review": summary.get("human_review", 0),
            "evidence_coverage": summary.get("evidence_coverage", 0),
            "path_reproducibility": summary.get("path_reproducibility", 0),
            "runtime_seconds": summary.get("runtime_seconds", 0),
        },
        "benchmark": {
            "claims": 52,
            "claim_recall": focused.get("claim_recall", 0),
            "claim_precision": focused.get("claim_precision", 0),
            "locator_precision": focused.get("evidence_locator_precision", 0),
            "locator_recall": focused.get("evidence_locator_recall", 0),
            "condition_match_rate": focused.get("condition_match_rate", 0),
        },
        "review": {
            "failure_mode": review_item.get("failure_mode"),
            "question": review_item.get("question"),
            "recommended_action": review_item.get("recommended_action"),
        },
    }


def render(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.replace("__PAYLOAD__", payload)


TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ProvSci teacher demo dashboard</title>
<style>
:root {
  --ink: #173047;
  --muted: #65788a;
  --line: #d8e4eb;
  --canvas: #f3f7f8;
  --surface: #ffffff;
  --surface-soft: #f7fafb;
  --teal-deep: #0d3d46;
  --teal: #087f78;
  --teal-soft: #e3f3f0;
  --blue: #376ec3;
  --blue-soft: #eaf0fb;
  --amber: #b46e1a;
  --amber-soft: #fff3de;
  --coral: #bd5551;
  --green: #2d8b65;
  --font-size-base: 14px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--canvas); color: var(--ink); font: var(--font-size-base)/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
button { font: inherit; }
a { color: var(--teal); }
.demo-app { max-width: 1500px; min-height: 100vh; margin: 0 auto; display: grid; grid-template-columns: 232px minmax(0, 1fr); }
.sidebar { padding: 24px 16px 18px; background: var(--teal-deep); color: #eaf7f6; display: flex; flex-direction: column; gap: 22px; }
.brand { display: flex; align-items: baseline; gap: 8px; padding: 0 8px; font-size: 22px; font-weight: 500; letter-spacing: .01em; }
.brand small { color: #9bd5d0; font-size: 10px; letter-spacing: .12em; }
.source-mini { padding: 14px; border: 1px solid #2b5c64; background: #164b54; border-radius: 8px; }
.eyebrow { color: #8fc9c5; font-size: 11px; letter-spacing: .09em; text-transform: uppercase; }
.source-mini h2 { margin: 7px 0 8px; font-size: 15px; line-height: 1.35; font-weight: 500; }
.source-mini p { margin: 0; color: #c1e0dd; font-size: 12px; }
.source-status { display: flex; align-items: center; gap: 7px; margin-top: 12px; color: #c1e8d9; font-size: 12px; }
.dot { width: 7px; height: 7px; display: inline-block; border-radius: 50%; background: #68c796; }
.nav { display: grid; gap: 4px; }
.nav button { border: 0; border-radius: 6px; padding: 10px 11px; color: #b8d6d4; background: transparent; text-align: left; cursor: pointer; }
.nav button:hover, .nav button[aria-current="page"] { color: #ffffff; background: #1b5660; }
.nav button span { display: inline-block; width: 23px; color: #84c0bc; }
.sidebar-foot { margin-top: auto; padding: 12px 8px 0; border-top: 1px solid #2b5c64; color: #9fc5c2; font: 11px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }
.main { min-width: 0; padding: 22px 28px 36px; }
.topbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; padding-bottom: 22px; }
.topbar h1 { margin: 5px 0 0; font-size: 25px; font-weight: 500; letter-spacing: 0; }
.kicker { color: var(--teal); font-size: 12px; font-weight: 500; letter-spacing: .08em; text-transform: uppercase; }
.run-state { display: flex; align-items: center; gap: 9px; color: var(--muted); font-size: 12px; white-space: nowrap; }
.run-state strong { padding: 6px 9px; border-radius: 5px; color: var(--green); background: #e2f3ea; font-size: 11px; letter-spacing: .05em; }
.hero { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: end; padding: 22px 24px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.hero h2 { margin: 0 0 6px; font-size: 19px; font-weight: 500; }
.hero p { max-width: 650px; margin: 0; color: var(--muted); }
.metric-strip { display: grid; grid-template-columns: repeat(4, minmax(76px, 1fr)); gap: 18px; min-width: 350px; }
.metric { padding-left: 14px; border-left: 1px solid var(--line); }
.metric strong { display: block; color: var(--ink); font-size: 23px; font-weight: 500; line-height: 1.1; }
.metric span { display: block; margin-top: 4px; color: var(--muted); font-size: 11px; }
.workspace { display: grid; grid-template-columns: minmax(0, 1.28fr) minmax(310px, .72fr); gap: 18px; margin-top: 18px; align-items: start; }
.stack { display: grid; gap: 18px; min-width: 0; }
.panel { min-width: 0; padding: 18px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 16px; }
.panel-head h3 { margin: 0; font-size: 15px; font-weight: 500; }
.panel-head p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.result-panel { display: grid; grid-template-columns: minmax(0, 1fr) 190px; gap: 18px; align-items: stretch; }
.result-label { color: var(--muted); font-size: 12px; }
.result-value { margin: 10px 0 4px; color: var(--teal-deep); font-size: 38px; font-weight: 500; line-height: 1; letter-spacing: 0; }
.result-value small { color: var(--muted); font-size: 17px; font-weight: 400; }
.result-context { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 14px; }
.context { padding: 6px 9px; border-radius: 5px; color: var(--ink); background: var(--surface-soft); font-size: 12px; }
.context em { color: var(--muted); font-style: normal; }
.pass-stamp { display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 14px; border-left: 1px solid var(--line); background: var(--teal-soft); text-align: center; }
.pass-stamp strong { color: var(--green); font-size: 18px; font-weight: 500; }
.pass-stamp span { margin-top: 5px; color: #3b716c; font-size: 11px; }
.series-controls { display: flex; flex-wrap: wrap; gap: 12px; }
.series-controls button { display: inline-flex; align-items: center; gap: 6px; border: 0; padding: 0; color: var(--muted); background: transparent; cursor: pointer; }
.series-controls button[aria-pressed="true"] { color: var(--ink); }
.swatch { width: 9px; height: 9px; border-radius: 50%; background: var(--series-color); }
.chart-wrap { min-height: 330px; }
#ic50-chart { display: block; width: 100%; height: 330px; overflow: visible; }
#ic50-chart text { fill: var(--muted); font-size: 11px; }
#ic50-chart .axis-title { fill: var(--ink); font-size: 11px; }
#ic50-chart .grid-line { stroke: #e9eff2; stroke-width: 1; }
#ic50-chart .axis-line { stroke: #b9cbd1; stroke-width: 1; }
#ic50-chart .series-line { fill: none; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
#ic50-chart .error-line { stroke-width: 1.3; }
#ic50-chart .point { stroke: var(--surface); stroke-width: 2; cursor: pointer; }
#ic50-chart .point-hit { fill: transparent; cursor: pointer; }
.chart-detail { min-height: 28px; margin-top: 4px; color: var(--muted); font-size: 12px; }
.chart-detail strong { color: var(--ink); font-weight: 500; }
.time-select { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.time-select button { border: 1px solid var(--line); border-radius: 5px; padding: 6px 10px; color: var(--muted); background: var(--surface); cursor: pointer; }
.time-select button:hover, .time-select button[aria-pressed="true"] { border-color: var(--teal); color: var(--teal); background: var(--teal-soft); }
.evidence-block { padding: 13px; border-left: 3px solid var(--teal); background: var(--surface-soft); }
.evidence-block h4 { margin: 0 0 9px; color: var(--teal); font-size: 12px; font-weight: 500; }
.locator { display: grid; grid-template-columns: 68px minmax(0, 1fr); gap: 4px 10px; margin: 0; font-size: 12px; }
.locator dt { color: var(--muted); }
.locator dd { margin: 0; color: var(--ink); overflow-wrap: anywhere; }
.evidence-quote { margin: 13px 0 0; color: var(--ink); font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.path { display: grid; gap: 9px; }
.path-step { display: grid; grid-template-columns: 27px minmax(0, 1fr); gap: 9px; align-items: start; border: 1px solid transparent; border-radius: 7px; padding: 8px; background: var(--surface-soft); text-align: left; cursor: pointer; }
.path-step:hover, .path-step.active { border-color: #a6d6d1; background: var(--teal-soft); }
.path-number { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; color: var(--teal); background: #c5e9e5; font-size: 11px; }
.path-step strong { display: block; color: var(--ink); font-size: 12px; font-weight: 500; }
.path-step span { display: block; margin-top: 2px; color: var(--muted); font-size: 11px; }
.path-detail { min-height: 55px; margin-top: 12px; padding: 10px; color: var(--ink); background: #f2f7f7; font: 11px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.gate-list { display: grid; gap: 9px; }
.gate { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 9px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 12px; }
.gate:last-child { padding-bottom: 0; border-bottom: 0; }
.gate strong { color: var(--green); font-weight: 500; white-space: nowrap; }
.review-strip { display: grid; grid-template-columns: 160px minmax(0, 1fr) auto; gap: 16px; align-items: center; margin-top: 18px; padding: 17px 18px; border: 1px solid #efd8af; border-radius: 10px; background: var(--amber-soft); }
.review-strip h3 { margin: 0; color: var(--amber); font-size: 13px; font-weight: 500; }
.review-strip p { margin: 0; color: #795524; font-size: 12px; overflow-wrap: anywhere; }
.review-strip button { border: 1px solid #d8b678; border-radius: 5px; padding: 7px 10px; color: #80541e; background: transparent; cursor: pointer; white-space: nowrap; }
.review-strip button:hover { background: #ffe8ba; }
.principle-panel { margin-top: 18px; }
.principle-flow { display: flex; align-items: stretch; gap: 8px; padding: 12px 0 14px; overflow-x: auto; }
.principle-flow > div { min-width: 116px; padding: 10px; border: 1px solid var(--line); border-radius: 7px; background: var(--surface-soft); }
.principle-flow > div strong { display: block; color: var(--teal); font-size: 12px; font-weight: 500; }
.principle-flow > div span { display: block; margin-top: 4px; color: var(--muted); font-size: 11px; }
.principle-flow > i { align-self: center; color: var(--teal); font-style: normal; }
.principle-intro { margin: 0 0 16px; padding: 13px 15px; border-left: 3px solid var(--teal); color: var(--ink); background: var(--teal-soft); font-size: 13px; }
.principle-intro strong { color: var(--teal-deep); font-weight: 600; }
.principle-section-title { margin: 18px 0 9px; color: var(--ink); font-size: 13px; font-weight: 600; }
.principle-stages { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 22px; }
.principle-stage { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 9px; padding: 12px 0; border-top: 1px solid var(--line); }
.principle-stage:nth-child(-n + 2) { border-top: 0; }
.principle-stage-num { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; color: var(--teal); background: #c5e9e5; font-size: 11px; font-weight: 600; }
.principle-stage h4 { margin: 0; color: var(--ink); font-size: 13px; font-weight: 600; }
.principle-stage p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.principle-stage small { display: block; margin-top: 6px; color: var(--teal); font-size: 11px; }
.principle-api-title { margin-top: 17px; }
.principle-api-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.principle-api-card { min-width: 0; padding: 12px; border: 1px solid var(--line); border-radius: 7px; background: var(--surface-soft); }
.principle-api-card h4 { margin: 0 0 6px; color: var(--ink); font-size: 12px; font-weight: 600; }
.principle-api-card p { margin: 0; color: var(--muted); font-size: 11px; }
.principle-api-card code, .principle-code code { display: block; margin-top: 8px; color: var(--teal); font: 11px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }
.principle-code { margin: 10px 0 0; padding: 11px 13px; border: 1px solid var(--line); border-radius: 6px; color: var(--ink); background: #f2f7f7; font: 11px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.principle-code code { margin: 0; color: inherit; }
.principle-note { margin: 12px 0 0; color: var(--muted); font-size: 11px; }
.principle-note strong { color: var(--ink); font-weight: 600; }
.principle-future { margin-top: 14px; padding: 11px 13px; border: 1px solid #efd8af; border-radius: 6px; color: #795524; background: var(--amber-soft); font-size: 12px; }
.principle-future strong { color: var(--amber); font-weight: 600; }
.principle-api { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 10px; padding-top: 13px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }
.principle-api strong { color: var(--ink); font-weight: 500; }
.principle-api code { padding: 1px 4px; border-radius: 3px; color: var(--teal); background: var(--teal-soft); font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }
.footnote { margin: 18px 2px 0; color: var(--muted); font-size: 11px; }
.tooltip { position: absolute; z-index: 3; display: none; pointer-events: none; padding: 8px 10px; border: 1px solid #a9c2c7; border-radius: 5px; color: #173047; background: #ffffff; box-shadow: 0 7px 18px rgba(23,48,71,.12); font-size: 12px; white-space: nowrap; }
@media (max-width: 1080px) {
  .demo-app { grid-template-columns: 190px minmax(0, 1fr); }
  .main { padding-inline: 20px; }
  .hero { grid-template-columns: 1fr; }
  .metric-strip { min-width: 0; }
}
@media (max-width: 820px) {
  .demo-app { display: block; }
  .sidebar { padding: 14px 16px; gap: 13px; }
  .source-mini, .sidebar-foot { display: none; }
  .nav { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .nav button { padding: 8px 7px; font-size: 12px; }
  .nav button span { width: 16px; }
  .main { padding: 18px 14px 28px; }
  .workspace { grid-template-columns: 1fr; }
  .result-panel { grid-template-columns: 1fr; }
  .pass-stamp { padding: 12px; border-top: 1px solid var(--line); border-left: 0; align-items: flex-start; }
  .review-strip { grid-template-columns: 1fr; gap: 8px; }
  .principle-api { grid-template-columns: 1fr; gap: 5px; }
  .principle-stages, .principle-api-grid { grid-template-columns: 1fr; }
  .principle-stage:nth-child(2) { border-top: 1px solid var(--line); }
}
@media (max-width: 500px) {
  .topbar { display: block; }
  .run-state { margin-top: 12px; }
  .metric-strip { grid-template-columns: repeat(2, 1fr); gap: 12px 18px; }
  .metric:nth-child(3) { border-left: 0; padding-left: 0; }
  .result-value { font-size: 31px; }
  .chart-wrap, #ic50-chart { height: 290px; min-height: 290px; }
}
</style>
</head>
<body>
<div class="demo-app" id="provsci-demo">
  <aside class="sidebar">
    <div class="brand">ProvSci <small>TEACHER DEMO</small></div>
    <section class="source-mini">
      <div class="eyebrow">当前文献</div>
      <h2 id="source-title">真实开放论文</h2>
      <p id="source-meta">PMC8415024 · 2021</p>
      <div class="source-status"><i class="dot"></i><span id="source-license">CC-BY-4.0 · 许可已确认</span></div>
    </section>
    <nav class="nav" aria-label="演示导航">
      <button type="button" aria-current="page" data-target="overview"><span>01</span>结果总览</button>
      <button type="button" aria-current="false" data-target="evidence"><span>02</span>证据链</button>
      <button type="button" aria-current="false" data-target="review"><span>03</span>人工复核</button>
      <button type="button" aria-current="false" data-target="principle"><span>04</span>技术原理</button>
    </nav>
    <div class="sidebar-foot" id="run-name">run / teacher-demo-v2</div>
  </aside>
  <main class="main">
    <header class="topbar" id="overview">
      <div><div class="kicker">可审计结果工作台</div><h1>从论文表格到可复算结果</h1></div>
      <div class="run-state"><strong>运行正常</strong><span>result_focused · 本地确定性处理</span><a href="../../web/product_workspace.html" target="_blank" rel="noopener" style="display:inline-block;margin-left:10px;padding:6px 9px;border:1px solid #9bc9c6;border-radius:5px;color:#087f78;background:#fff;text-decoration:none;font-size:11px;">进入产品工作台</a></div>
    </header>
    <section class="hero">
      <div><h2>一个结果，四层证据</h2><p>点击下方曲线上的时间点，结果卡、原文 locator、acquisition path 和 verifier 状态会同步切换。</p></div>
      <div class="metric-strip" aria-label="运行规模">
        <div class="metric"><strong id="metric-docs">4</strong><span>真实论文</span></div>
        <div class="metric"><strong id="metric-candidates">192</strong><span>候选结果</span></div>
        <div class="metric"><strong id="metric-gold">186</strong><span>Gold</span></div>
        <div class="metric"><strong id="metric-review">6</strong><span>人工复核</span></div>
      </div>
    </section>
    <section class="workspace">
      <div class="stack">
        <section class="panel result-panel" aria-live="polite">
          <div>
            <div class="result-label">当前选中 · <span id="selected-entity">SW480</span> / IC50 / <span id="selected-time">24 h</span></div>
            <div class="result-value"><span id="selected-value">15.34 ± 0.81</span> <small id="selected-unit">μM</small></div>
            <div class="result-context">
              <span class="context"><em>condition</em> <b id="selected-condition">24 h</b></span>
              <span class="context"><em>result_type</em> <b>measurement</b></span>
              <span class="context"><em>quality</em> <b>Gold</b></span>
            </div>
          </div>
          <div class="pass-stamp"><strong>通过</strong><span>verifier 重算<br>证据已检查</span></div>
        </section>
        <section class="panel" aria-labelledby="chart-title">
          <div class="panel-head"><div><h3 id="chart-title">IC50 随处理时间变化</h3><p>PMC8415024 · TABLE 1 · 均值 ± 误差</p></div><div class="series-controls" id="series-controls"></div></div>
          <div class="chart-wrap"><svg id="ic50-chart" role="img" aria-label="SW480 与 SW1116 的 IC50 随时间变化图"></svg><div class="tooltip" id="chart-tooltip" role="tooltip"></div></div>
          <div class="chart-detail" id="chart-detail">当前点：<strong>SW480 · 24 h · 15.34 ± 0.81 μM</strong></div>
          <div class="time-select" id="time-select" aria-label="选择处理时间"></div>
        </section>
      </div>
      <div class="stack">
        <section class="panel" id="evidence">
          <div class="panel-head"><div><h3>证据定位（Evidence locator）</h3><p>能从结果回到原文的精确位置</p></div></div>
          <div class="evidence-block"><h4 id="evidence-title">TABLE 1 / SW480 / IC50(μM) / 24 h</h4><dl class="locator"><dt>文献</dt><dd id="evidence-doc">PMC8415024</dd><dt>表格</dt><dd id="evidence-table">TABLE 1</dd><dt>行</dt><dd id="evidence-row">SW480</dd><dt>列</dt><dd id="evidence-col">IC50(μM) / 24 h</dd><dt>页</dt><dd>0（JATS normalized）</dd></dl><div class="evidence-quote" id="evidence-quote">15.34 ± 0.81</div></div>
          <p class="footnote">证据模态：table · 原始值保留 · source hash 已记录</p>
        </section>
        <section class="panel">
          <div class="panel-head"><div><h3>处理路径（Acquisition path）</h3><p>点击步骤查看输入和中间结果</p></div></div>
          <div class="path" id="path-list"></div>
          <div class="path-detail" id="path-detail" aria-live="polite"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><div><h3>质量门禁</h3><p>所有 Gold 结果都要通过这些检查</p></div></div>
          <div class="gate-list"><div class="gate"><span>证据定位</span><strong>通过</strong></div><div class="gate"><span>路径可复现</span><strong>1.0000</strong></div><div class="gate"><span>条件明确</span><strong>通过</strong></div><div class="gate"><span>许可已确认</span><strong>通过</strong></div><div class="gate"><span>P0 claim precision</span><strong id="gate-claim-precision">1.0000</strong></div><div class="gate"><span>P0 locator P / R</span><strong id="gate-locator">1.0000 / 1.0000</strong></div></div>
        </section>
      </div>
    </section>
    <section class="review-strip" id="review"><h3>保留一个需要人的样本</h3><p id="review-text">关系候选的主客体跨度不稳定，因此保留证据并进入 Human Review，不被硬塞进 Gold。</p><button type="button" id="review-button">打开复核工作台</button></section>
    <section class="panel principle-panel" id="principle">
      <div class="panel-head"><div><h3>技术原理：用最直白的话说明白</h3><p>把论文变成“有出处、能复算、出问题能追责”的数据，而不是只生成一段看起来合理的文字。</p></div></div>
      <p class="principle-intro"><strong>先用一个比喻：</strong>这个智能体像一条科研数据质检流水线。第一位工作人员负责在论文里找出可能的数字，第二位工作人员负责把数字放回原文重新验货；只有两边对得上，才贴上 <strong>Gold（验收合格）</strong> 标签。找到但信息不完整的，放到 <strong>Silver（待确认）</strong>；主客体或条件说不清的，交给 <strong>Human Review（人工复核）</strong>，系统不会假装自己确定。</p>
      <div class="principle-flow" aria-label="数据处理主流程"><div><strong>1. 输入</strong><span>论文 / 实验文件</span></div><i>→</i><div><strong>2. 适配</strong><span>转成统一文档结构</span></div><i>→</i><div><strong>3. 挖掘</strong><span>找数字、单位、实体、条件</span></div><i>→</i><div><strong>4. 形成证据</strong><span>结果卡 + 原文位置 + 处理路径</span></div><i>→</i><div><strong>5. 复算分流</strong><span>verifier 决定 Gold / Silver / 人工</span></div></div>

      <h4 class="principle-section-title">一篇论文进入系统后，具体发生什么？</h4>
      <div class="principle-stages">
        <article class="principle-stage"><i class="principle-stage-num">1</i><div><h4>读取原始文件</h4><p>可以输入 PMC/JATS XML、JSON 等结构化文件。系统先保存原文件、文献编号、许可证、来源 URL、下载时间和 SHA-256 hash。hash 就像文件指纹，用来证明后来复核的还是同一份材料。</p><small>产物：source manifest + 本地原文件</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">2</i><div><h4>格式适配，而不是直接猜答案</h4><p>不同论文的 XML 标签不一样，适配器先把正文、表格、图注和章节整理成统一结构，并保留表格 ID、行名、列名等位置关系。这样后面才能准确回答“哪一张表、哪一行、哪一列”。</p><small>产物：normalized document</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">3</i><div><h4>挖掘候选结果</h4><p>miner 在结果相关章节和表格中寻找数值表达式，例如 <code>15.34 ± 0.81 μM</code>，同时识别实体 SW480、指标 IC50、条件 24 h 和结果类型 measurement。这里得到的是“可能的答案”，还不是最终答案。</p><small>产物：candidate records</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">4</i><div><h4>生成 ResultCard（结果卡）</h4><p>候选会被装进固定字段：entity、metric、value、uncertainty、unit、condition、source、evidence 和 acquisition_path。固定字段的意义是让不同论文的结果可以比较，也让程序能够逐项检查。</p><small>产物：结构化 ResultCard JSONL</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">5</i><div><h4>记录 Evidence locator（证据定位）</h4><p>系统同时记录原文片段及其位置，例如 <code>TABLE 1 → row SW480 → col IC50(μM) / 24 h</code>。老师点击页面上的结果，就能从结果卡回到这段原文，而不是只能相信一段摘要。</p><small>产物：span_text + table/row/col locator</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">6</i><div><h4>记录 Acquisition path（处理路径）</h4><p>路径是“系统怎样得到这个数”的操作清单，例如先取表格单元格，再解析均值、误差和单位。每一步都有输入、参数和输出，后续可以按同样步骤重做。</p><small>产物：可执行 path trace</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">7</i><div><h4>verifier replay（清空答案后重算）</h4><p>verifier 不直接复述候选答案，而是暂时把答案拿掉，沿 acquisition path 重新读取原文并计算。如果重算值、误差、单位、条件和证据片段都一致，verification.status 才是 pass。</p><small>产物：verification trace + pass/fail reason</small></div></article>
        <article class="principle-stage"><i class="principle-stage-num">8</i><div><h4>质量分流</h4><p>所有关键检查通过才进入 Gold；数值找到了但条件或许可不够完整，进入 Silver；关系主客体不清、证据冲突或路径无法复现，则进入 Human Review，并保留原始证据等待专家决定。</p><small>产物：Gold / Silver / Human Review</small></div></article>
      </div>

      <h4 class="principle-section-title principle-api-title">API 到底分几层？可以把它理解成“拿资料、加工资料、查询结果”</h4>
      <div class="principle-api-grid">
        <article class="principle-api-card"><h4>第一层：论文来源 API</h4><p>负责把开放论文拿到本地。比如 <code>fetch-pmc --pmc-id PMC8415024</code> 会请求 Europe PMC 的 fullTextXML 接口，再把正文和来源元数据保存下来。</p><code>GET https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8415024/fullTextXML</code></article>
        <article class="principle-api-card"><h4>第二层：智能体处理 API</h4><p>这是项目自己的 Python 接口。<code>run</code> 负责完整流水线：读取、解析、挖掘、生成证据、验证并写出 JSONL；它不是聊天接口，而是一个可重复运行的处理函数。</p><code>agent.run(input_path, output_dir)</code></article>
        <article class="principle-api-card"><h4>第三层：自然语言查询 API</h4><p><code>ask</code> 读取已经生成的结果，只在 verification.status=pass 的样本中做透明的关键词匹配，再把答案、证据、路径和验证轨迹一起返回。</p><code>agent.ask(question, results_dir)</code></article>
      </div>
      <pre class="principle-code"><code># 1) 处理一篇论文：产生可审计结果
from provsci.agent import ScientificDataAgent
agent = ScientificDataAgent()
summary = agent.run("paper.nxml", "work/run")

# 2) 查询已验证结果：不会绕过 verifier
results = agent.ask("What IC50 was reported for SW480 under 24 h?", "work/run")
</code></pre>
      <p class="principle-note"><strong>命令行是怎么接上的？</strong> CLI 只是一个外壳：它接收 <code>--input</code>、<code>--output</code>、<code>--question</code> 等参数，转换成上面的 Python 函数调用，再把结果写成 JSON/JSONL 文件。当前核心智能体是本地 Python API，不是已经部署在服务器上的 HTTP API；<code>review-serve</code> 只负责把人工复核页面提供给浏览器。</p>
      <div class="principle-future"><strong>未来如果接入大模型 API：</strong>大模型适合放在“候选挖掘”和“自然语言问题理解”位置，例如帮助判断一句话里的实体和条件；它输出的内容仍必须转成 ResultCard，并经过 evidence locator、acquisition path 和 verifier replay。也就是说，模型可以当“找线索的助手”，不能直接跳过质检盖章。</div>
    </section>
    <p class="footnote">当前图表数据来自真实开放论文 PMC8415024 的 TABLE 1；规模指标来自同一运行目录。小规模 benchmark 用于检验闭环，不代表跨领域总体准确率。</p>
  </main>
</div>
<script id="demo-data" type="application/json">__PAYLOAD__</script>
<script>
(() => {
  const data = JSON.parse(document.getElementById('demo-data').textContent || '{}');
  const root = document.getElementById('provsci-demo');
  const seriesColors = {SW480: '#087f78', SW1116: '#376ec3'};
  const state = {entity: 'SW480', time: '24 h', visible: {SW480: true, SW1116: true}, pathStep: 1};
  const esc = value => String(value === undefined || value === null ? '' : value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const activeRow = () => (data.series[state.entity] || []).find(row => row.time === state.time) || data.primary;
  const pathFor = row => row.path || [];

  function populateStatic() {
    const src = data.source || {};
    const summary = data.summary || {};
    document.getElementById('source-title').textContent = src.title || '真实开放论文';
    document.getElementById('source-meta').textContent = `${src.doc_id || 'PMC8415024'} · ${src.year || ''}`;
    document.getElementById('source-license').textContent = `${src.license || 'CC-BY-4.0'} · ${src.license_status === 'known' ? '许可已确认' : '许可未知'}`;
    document.getElementById('run-name').textContent = `run / ${data.run_name || 'teacher-demo'}`;
    document.getElementById('metric-docs').textContent = summary.documents ?? '—';
    document.getElementById('metric-candidates').textContent = summary.candidates ?? '—';
    document.getElementById('metric-gold').textContent = summary.gold ?? '—';
    document.getElementById('metric-review').textContent = summary.human_review ?? '—';
    const benchmark = data.benchmark || {};
    document.getElementById('gate-claim-precision').textContent = Number(benchmark.claim_precision ?? 0).toFixed(4);
    document.getElementById('gate-locator').textContent = `${Number(benchmark.locator_precision ?? 0).toFixed(4)} / ${Number(benchmark.locator_recall ?? 0).toFixed(4)}`;
    const review = data.review || {};
    if (review.question) document.getElementById('review-text').textContent = `${review.failure_mode || '需要复核'}：${review.question}`;
    document.getElementById('review-button').addEventListener('click', () => window.open('p0/real-smoke/review_workbench.html', '_blank', 'noopener'));
  }

  function updateSelection() {
    const row = activeRow();
    if (!row) return;
    state.entity = row.entity;
    state.time = row.time;
    const display = row.display || `${row.value} ± ${row.uncertainty}`;
    document.getElementById('selected-entity').textContent = row.entity;
    document.getElementById('selected-time').textContent = row.time;
    document.getElementById('selected-condition').textContent = row.time;
    document.getElementById('selected-value').textContent = display.replace(/\s*μM\s*$/, '');
    document.getElementById('selected-unit').textContent = row.unit || 'μM';
    const locator = (row.evidence || [])[0]?.locator || {};
    const column = locator.col || `IC50(μM) / ${row.time}`;
    document.getElementById('evidence-title').textContent = `${locator.table_id || 'TABLE 1'} / ${locator.row || row.entity} / ${column}`;
    document.getElementById('evidence-doc').textContent = row.source?.doc_id || 'PMC8415024';
    document.getElementById('evidence-table').textContent = locator.table_id || 'TABLE 1';
    document.getElementById('evidence-row').textContent = locator.row || row.entity;
    document.getElementById('evidence-col').textContent = column;
    document.getElementById('evidence-quote').textContent = row.evidence?.[0]?.span_text || display;
    document.getElementById('chart-detail').innerHTML = `当前点：<strong>${esc(row.entity)} · ${esc(row.time)} · ${esc(display)} ${esc(row.unit || 'μM')}</strong>`;
    document.querySelectorAll('#time-select button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.time === state.time)));
    document.querySelectorAll('#series-controls button').forEach(button => button.setAttribute('aria-pressed', String(!!state.visible[button.dataset.entity])));
    renderPath();
    drawChart();
  }

  function renderSeriesControls() {
    const host = document.getElementById('series-controls');
    host.innerHTML = Object.keys(data.series || {}).map(entity => `<button type="button" data-entity="${esc(entity)}" aria-pressed="${state.visible[entity] !== false}"><i class="swatch" style="--series-color:${seriesColors[entity] || '#087f78'}"></i>${esc(entity)}</button>`).join('');
    host.querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
      const entity = button.dataset.entity;
      state.visible[entity] = !state.visible[entity];
      if (!Object.values(state.visible).some(Boolean)) state.visible[entity] = true;
      updateSelection();
    }));
  }

  function renderTimeButtons() {
    const times = [...new Set(Object.values(data.series || {}).flat().map(row => row.time))].sort((a,b) => Number.parseFloat(a) - Number.parseFloat(b));
    const host = document.getElementById('time-select');
    host.innerHTML = times.map(time => `<button type="button" data-time="${esc(time)}" aria-pressed="${time === state.time}">${esc(time)}</button>`).join('');
    host.querySelectorAll('button').forEach(button => button.addEventListener('click', () => { state.time = button.dataset.time; updateSelection(); }));
  }

  function renderPath() {
    const row = activeRow();
    const path = pathFor(row);
    const host = document.getElementById('path-list');
    host.innerHTML = path.map((step, index) => `<button type="button" class="path-step ${state.pathStep === index + 1 ? 'active' : ''}" data-step="${index + 1}"><i class="path-number">${index + 1}</i><span><strong>${esc(step.action || 'step')}</strong><span>${esc(step.tool || 'deterministic processor')}</span></span></button>`).join('');
    host.querySelectorAll('button').forEach(button => button.addEventListener('click', () => { state.pathStep = Number(button.dataset.step); renderPath(); }));
    const selected = path[state.pathStep - 1] || path[0];
    document.getElementById('path-detail').textContent = selected ? `${selected.action}\n输入: ${JSON.stringify(selected.args || {})}\n输出: ${JSON.stringify(selected.output)}` : '没有可显示的路径步骤';
  }

  function drawChart() {
    const svg = document.getElementById('ic50-chart');
    const width = Math.max(320, svg.parentElement.clientWidth || 640);
    const height = svg.clientHeight || 330;
    const pad = {left: 50, right: 22, top: 18, bottom: 40};
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    const values = Object.values(data.series || {}).flat();
    const maxValue = Math.max(...values.map(row => row.value + row.uncertainty), 1);
    const yMax = Math.ceil(maxValue / 2) * 2;
    const times = [...new Set(values.map(row => row.time_hours))].sort((a,b) => a-b);
    const x = hours => pad.left + (times.length <= 1 ? plotWidth / 2 : (hours - times[0]) / (times[times.length - 1] - times[0]) * plotWidth);
    const y = value => pad.top + plotHeight - (value / yMax) * plotHeight;
    const ns = 'http://www.w3.org/2000/svg';
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = '';
    const line = (x1,y1,x2,y2,className) => { const el = document.createElementNS(ns,'line'); el.setAttribute('x1',x1); el.setAttribute('y1',y1); el.setAttribute('x2',x2); el.setAttribute('y2',y2); el.setAttribute('class',className); svg.appendChild(el); return el; };
    const text = (tx,ty,value,className='') => { const el = document.createElementNS(ns,'text'); el.setAttribute('x',tx); el.setAttribute('y',ty); if (className) el.setAttribute('class',className); el.textContent = value; svg.appendChild(el); return el; };
    for (let tick = 0; tick <= yMax; tick += Math.max(2, yMax / 4)) { const value = Math.round(tick); line(pad.left, y(value), width - pad.right, y(value), 'grid-line'); text(pad.left - 10, y(value) + 4, value, ''); }
    line(pad.left, pad.top, pad.left, height - pad.bottom, 'axis-line');
    line(pad.left, height - pad.bottom, width - pad.right, height - pad.bottom, 'axis-line');
    times.forEach(hour => { const tx = x(hour); line(tx, height - pad.bottom, tx, height - pad.bottom + 5, 'axis-line'); text(tx, height - pad.bottom + 21, `${hour} h`, ''); });
    text(7, pad.top + plotHeight / 2, 'IC50 (μM)', 'axis-title');
    text(width - 105, height - 8, '处理时间', 'axis-title');
    Object.entries(data.series || {}).forEach(([entity, rows]) => {
      if (state.visible[entity] === false) return;
      const color = seriesColors[entity] || '#087f78';
      const points = rows.map(row => `${x(row.time_hours)},${y(row.value)}`).join(' ');
      const polyline = document.createElementNS(ns,'polyline'); polyline.setAttribute('points', points); polyline.setAttribute('class','series-line'); polyline.setAttribute('stroke',color); svg.appendChild(polyline);
      rows.forEach(row => {
        const cx = x(row.time_hours), cy = y(row.value), top = y(row.value + row.uncertainty), bottom = y(Math.max(0, row.value - row.uncertainty));
        line(cx, top, cx, bottom, 'error-line').setAttribute('stroke', color); line(cx - 4, top, cx + 4, top, 'error-line').setAttribute('stroke', color); line(cx - 4, bottom, cx + 4, bottom, 'error-line').setAttribute('stroke', color);
        const circle = document.createElementNS(ns,'circle'); circle.setAttribute('cx',cx); circle.setAttribute('cy',cy); circle.setAttribute('r', row.entity === state.entity && row.time === state.time ? 6 : 4.5); circle.setAttribute('fill',color); circle.setAttribute('class','point'); circle.setAttribute('aria-label',`${row.entity} ${row.time} ${row.display}`); circle.addEventListener('click', () => { state.entity = row.entity; state.time = row.time; updateSelection(); }); circle.addEventListener('mouseenter', event => showTooltip(event, row, svg)); circle.addEventListener('mouseleave', hideTooltip); svg.appendChild(circle);
        const hit = document.createElementNS(ns,'circle'); hit.setAttribute('cx',cx); hit.setAttribute('cy',cy); hit.setAttribute('r',18); hit.setAttribute('class','point-hit'); hit.addEventListener('click', () => { state.entity = row.entity; state.time = row.time; updateSelection(); }); hit.addEventListener('mouseenter', event => showTooltip(event, row, svg)); hit.addEventListener('mouseleave', hideTooltip); svg.appendChild(hit);
      });
    });
  }

  function showTooltip(event, row, svg) {
    const tip = document.getElementById('chart-tooltip');
    const rect = svg.getBoundingClientRect();
    tip.textContent = `${row.entity} · ${row.time} · ${row.display} ${row.unit || 'μM'}`;
    tip.style.display = 'block';
    tip.style.left = `${event.clientX - rect.left + 10}px`;
    tip.style.top = `${event.clientY - rect.top - 42}px`;
  }
  function hideTooltip() { document.getElementById('chart-tooltip').style.display = 'none'; }

  document.querySelectorAll('.nav button').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('.nav button').forEach(item => item.setAttribute('aria-current', String(item === button))); document.getElementById(button.dataset.target).scrollIntoView({behavior:'smooth', block:'start'}); }));
  window.addEventListener('resize', drawChart);
  populateStatic();
  renderSeriesControls();
  renderTimeButtons();
  updateSelection();
})();
</script>
</body>
</html>
'''


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2:
        print("usage: build_teacher_dashboard.py RUN_ROOT [OUTPUT_HTML]", file=sys.stderr)
        return 2
    run_dir = Path(argv[0])
    output = Path(argv[1]) if len(argv) == 2 else run_dir / "teacher_dashboard.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(collect_data(run_dir)), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
