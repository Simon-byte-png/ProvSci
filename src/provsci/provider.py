"""Optional OpenAI-compatible provider support for the local product app.

The deterministic pipeline remains the source of truth for extracted values.
When a user opts in, this module only asks an external provider for a plain-
language overview and never lets the model change, verify, or promote data.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_OVERVIEW_RESULTS = 40


@dataclass(frozen=True)
class ProviderConfig:
    """Credentials and endpoint settings for an OpenAI-compatible API."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = ""
    enabled: bool = False
    timeout_seconds: int = 45

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def public_dict(self) -> dict[str, Any]:
        """Return settings safe to send to the browser or logs."""
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "base_url": self.base_url,
            "model": self.model,
            "provider_type": "openai_compatible",
        }


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def normalize_provider_config(raw: dict[str, Any] | None = None, *, environ: dict[str, str] | None = None) -> ProviderConfig:
    """Build a provider config from request values, falling back to env vars.

    Request values are intentionally explicit: a browser can override the
    local defaults for one run, while a downloaded installation can use a
    `.env`/shell configuration without touching the UI.
    """
    values: dict[str, Any] = dict(environ or os.environ)
    incoming = raw or {}
    base_url = str(incoming.get("base_url") or values.get("PROVSCI_API_BASE_URL") or values.get("XAI_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = str(incoming.get("model") or values.get("PROVSCI_API_MODEL") or values.get("XAI_MODEL") or DEFAULT_MODEL).strip()
    api_key = str(incoming.get("api_key") or values.get("PROVSCI_API_KEY") or values.get("XAI_API_KEY") or "").strip()
    enabled = _as_bool(incoming.get("enabled"), _as_bool(values.get("PROVSCI_API_ENABLED"), False))
    if not base_url.startswith(("http://", "https://")):
        base_url = DEFAULT_BASE_URL
    return ProviderConfig(
        base_url=base_url.rstrip("/"),
        model=model or DEFAULT_MODEL,
        api_key=api_key,
        enabled=enabled,
    )


def _endpoint(config: ProviderConfig, suffix: str) -> str:
    base = config.base_url.rstrip("/")
    if base.endswith(suffix.lstrip("/")):
        return base
    return f"{base}/{suffix.lstrip('/')}"


def _request_json(config: ProviderConfig, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        endpoint,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ProvSci/0.3 local-product",
        },
    )
    with urlopen(request, timeout=config.timeout_seconds) as response:
        raw = response.read()
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("provider returned a non-object JSON response")
    return parsed


def test_provider(config: ProviderConfig) -> dict[str, Any]:
    """Check an API key and endpoint without exposing the key in errors."""
    if not config.api_key:
        return {"ok": False, "error": "没有填写 API 密钥"}
    try:
        response = _request_json(config, "GET", _endpoint(config, "/models"))
        models = response.get("data") if isinstance(response.get("data"), list) else []
        return {
            "ok": True,
            "message": "API 连接成功",
            "model_count": len(models),
            "config": config.public_dict(),
        }
    except HTTPError as exc:
        return {"ok": False, "error": f"API 返回 HTTP {exc.code}，请检查地址、密钥和权限"}
    except (URLError, TimeoutError) as exc:
        return {"ok": False, "error": f"无法连接 API：{exc.reason if isinstance(exc, URLError) else exc}"}
    except (ValueError, json.JSONDecodeError):
        return {"ok": False, "error": "API 返回格式无法识别，请确认这是 OpenAI 兼容接口"}
    except Exception as exc:  # pragma: no cover - provider-specific failures
        return {"ok": False, "error": f"API 连接失败：{type(exc).__name__}"}


def _result_context(summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    rows = []
    for row in results[:MAX_OVERVIEW_RESULTS]:
        rows.append({
            "对象": row.get("entity"),
            "指标": row.get("metric"),
            "结果": row.get("value"),
            "单位": row.get("unit"),
            "条件": row.get("condition"),
            "状态": "可直接使用" if row.get("quality") == "gold" else "建议人工检查",
        })
    return json.dumps({
        "概况": {
            "找到的数据": summary.get("total_candidates", len(results)),
            "可直接使用": summary.get("gold"),
            "建议人工检查": summary.get("human_review"),
        },
        "结果": rows,
    }, ensure_ascii=False)


def generate_overview(config: ProviderConfig, summary: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask the user's provider for an optional human-readable run overview."""
    if not config.enabled:
        return {"status": "disabled", "message": "未启用外部 API，本地流程已完成"}
    if not config.configured:
        return {"status": "error", "message": "已开启外部 API，但地址、模型或密钥不完整"}
    prompt = (
        "请用中文给科研数据整理结果写一段不超过 180 字的说明。"
        "只总结下面已经由本地程序提取并核对的内容，不要改写任何数值，不要补充数据。"
        "必须说明：找到多少条、多少条可直接使用、多少条建议人工检查，以及用户下一步该做什么。\n\n"
        f"{_result_context(summary, results)}"
    )
    payload = {
        "model": config.model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是一个严谨的科研数据整理助手。"},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        response = _request_json(config, "POST", _endpoint(config, "/chat/completions"), payload)
        choices = response.get("choices") or []
        content = (((choices[0] if choices else {}).get("message") or {}).get("content") or "").strip()
        if not content:
            return {"status": "error", "message": "API 已返回，但没有生成说明"}
        return {
            "status": "success",
            "message": content[:1000],
            "model": config.model,
            "provider": config.base_url,
        }
    except HTTPError as exc:
        return {"status": "error", "message": f"API 返回 HTTP {exc.code}，本地结果不受影响"}
    except (URLError, TimeoutError):
        return {"status": "error", "message": "外部 API 暂时无法连接，本地结果不受影响"}
    except (ValueError, json.JSONDecodeError):
        return {"status": "error", "message": "API 返回格式无法识别，本地结果不受影响"}
    except Exception as exc:  # pragma: no cover - provider-specific failures
        return {"status": "error", "message": f"外部 API 调用失败（{type(exc).__name__}），本地结果不受影响"}
