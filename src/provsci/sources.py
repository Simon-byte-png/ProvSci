"""Source fingerprint and provenance records for reproducible ingestion."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urljoin, urlparse

from .verifier import is_known_license


class SourceError(ValueError):
    """Raised when an external source cannot be safely acquired."""


def search_europepmc(query: str, page_size: int = 25, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Discover candidate open-access records without downloading full text."""
    text = str(query).strip()
    if not text:
        raise SourceError("query cannot be empty")
    if not 1 <= int(page_size) <= 100:
        raise SourceError("page_size must be between 1 and 100")
    params = urlencode({"query": text, "format": "json", "resultType": "core", "pageSize": int(page_size)})
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}"
    request = Request(url, headers={"User-Agent": "ProvSci/0.3 (+https://provsci.example)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
        raw = json.loads(payload.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network-specific failures
        raise SourceError(f"could not search Europe PMC: {exc}") from exc
    hits = []
    for item in raw.get("resultList", {}).get("result", []):
        pmcid = str(item.get("pmcid", "")).strip()
        if not pmcid:
            continue
        hits.append({
            "pmc_id": pmcid,
            "pmid": item.get("pmid"),
            "doi": item.get("doi"),
            "title": item.get("title", ""),
            "year": item.get("pubYear"),
            "is_open_access": str(item.get("isOpenAccess", "")).casefold() in {"y", "yes", "true", "1"},
            "license": item.get("license"),
            "source_url": f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
        })
    return hits


def source_record(path: str | Path, document: Any, content_hash: str | None = None) -> dict[str, Any]:
    """Build a stable source record from a local file and DocumentPackage."""
    source = Path(path)
    digest = content_hash or hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = dict(getattr(document, "metadata", {}) or {})
    record: dict[str, Any] = {
        "doc_id": document.doc_id,
        "title": document.title,
        "year": document.year,
        "license": document.license,
        "license_status": "known" if is_known_license(document.license) else "unknown",
        "local_path": document.local_path,
        "source_hash": digest,
        "content_size_bytes": source.stat().st_size,
        "source_version": metadata.get("source_version") or f"sha256:{digest}",
        "retrieval_method": metadata.get("retrieval_method") or "local_file",
    }
    for key in ("source_url", "retrieved_at", "license_source", "adapter", "parser_version", "domain", "doi", "pmid"):
        if key in metadata:
            record[key] = metadata[key]
    return record


def source_record_errors(record: dict[str, Any]) -> list[str]:
    """Return actionable errors without blocking local/private inputs."""
    errors: list[str] = []
    if not str(record.get("source_hash", "")):
        errors.append("source_hash_missing")
    if not str(record.get("license", "")):
        errors.append("license_missing")
    if record.get("source_url") and not str(record["source_url"]).startswith(("http://", "https://")):
        errors.append("source_url_invalid")
    if record.get("retrieved_at") is None and record.get("retrieval_method") != "local_file":
        errors.append("retrieved_at_missing")
    return errors


def fetch_europepmc_jats(pmc_id: str, destination: str | Path, timeout: float = 30.0) -> dict[str, Any]:
    """Fetch one Europe PMC full-text XML record with explicit provenance.

    The caller still decides whether to put the downloaded file in a
    benchmark.  The response is written only after a successful HTTP read and
    a basic XML/article sanity check; the returned metadata is suitable for a
    manifest entry.
    """
    normalized = str(pmc_id).strip().upper()
    if not normalized.startswith("PMC") or not normalized[3:].isdigit():
        raise SourceError("pmc_id must look like PMC123456")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{normalized}/fullTextXML"
    request = Request(url, headers={"User-Agent": "ProvSci/0.3 (+https://provsci.example)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except Exception as exc:  # pragma: no cover - network-specific failures
        raise SourceError(f"could not fetch {normalized}: {exc}") from exc
    if b"<article" not in payload[:4096] or b"<license" not in payload:
        raise SourceError(f"response for {normalized} is not an article with a license record")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {
        "doc_id": normalized,
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).date().isoformat(),
        "retrieval_method": "europepmc_api",
        "source_version": "europepmc-fullTextXML",
        "license_source": "article JATS permissions",
    }


def fetch_http_source(
    source_url: str,
    destination: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
    timeout: float = 30.0,
    max_bytes: int = 100 * 1024 * 1024,
) -> dict[str, Any]:
    """Download one HTTP(S) source and return manifest-ready provenance.

    Redirects are followed by ``urllib`` and the final URL is recorded.  The
    body is bounded before writing, hashed after download, and never silently
    marked open access.  For XML/JATS responses the normalized article parser
    is used opportunistically to recover identifiers, title, year and license;
    parse failures remain explicit metadata so a binary/PDF fetch is still
    usable by a caller with a separate layout adapter.
    """
    raw_url = str(source_url).strip()
    if not raw_url:
        raise SourceError("source_url cannot be empty")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SourceError("source_url must use http or https")
    try:
        limit = int(max_bytes)
    except (TypeError, ValueError) as exc:
        raise SourceError("max_bytes must be a positive integer") from exc
    if limit <= 0:
        raise SourceError("max_bytes must be a positive integer")
    request = Request(raw_url, headers={"User-Agent": "ProvSci/0.3 (+https://provsci.example)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(limit + 1)
            final_url = str(getattr(response, "geturl", lambda: raw_url)() or raw_url)
            content_type = str(getattr(response, "headers", {}).get("Content-Type", ""))
    except Exception as exc:  # pragma: no cover - network-specific failures
        raise SourceError(f"could not fetch source {raw_url}: {exc}") from exc
    if not payload:
        raise SourceError(f"source response is empty: {raw_url}")
    if len(payload) > limit:
        raise SourceError(f"source exceeds max_bytes={limit}: {raw_url}")
    digest = hashlib.sha256(payload).hexdigest()
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)

    supplied = dict(metadata or {})
    retrieved_at = datetime.now(timezone.utc).date().isoformat()
    result: dict[str, Any] = {
        "source_url": final_url,
        "retrieved_at": retrieved_at,
        "retrieval_method": "http_url",
        "source_version": f"sha256:{digest}",
        "source_hash": digest,
        "content_size_bytes": len(payload),
        "local_path": str(target),
    }
    if content_type:
        result["content_type"] = content_type
    result.update({key: value for key, value in supplied.items() if value not in (None, "")})
    # The fetched URL and hash are authoritative even when callers supplied
    # stale values in a manifest template.
    result.update({
        "source_url": final_url,
        "retrieved_at": retrieved_at,
        "retrieval_method": "http_url",
        "source_version": f"sha256:{digest}",
        "source_hash": digest,
        "content_size_bytes": len(payload),
        "local_path": str(target),
    })

    looks_like_jats = target.suffix.casefold() in {".xml", ".nxml"} or b"<article" in payload[:8192]
    if looks_like_jats:
        try:
            from .adapters import load_document

            document = load_document(target, {**supplied, "source_url": final_url, "retrieved_at": retrieved_at})
            result.update({
                "doc_id": document.doc_id,
                "title": document.title,
                "year": document.year,
                "license": document.license,
            })
            for key in ("doi", "pmid"):
                if (document.metadata or {}).get(key):
                    result[key] = document.metadata[key]
            if document.license != "unknown":
                result["license_source"] = supplied.get("license_source") or "article JATS permissions"
            result["adapter"] = (document.metadata or {}).get("adapter", "jats_v0.1")
        except Exception as exc:  # pragma: no cover - malformed/partial XML
            result["parse_error"] = str(exc)
    result.setdefault("doc_id", supplied.get("doc_id") or f"url:{digest[:16]}")
    result.setdefault("title", supplied.get("title") or target.stem)
    result.setdefault("year", int(supplied.get("year", 0) or 0))
    result.setdefault("license", supplied.get("license", "unknown"))
    result["license_status"] = "known" if is_known_license(result.get("license")) else "unknown"
    return result


def fetch_external_supplement(
    article_url: str,
    href: str,
    destination: str | Path,
    timeout: float = 30.0,
    max_bytes: int = 50 * 1024 * 1024,
) -> dict[str, Any]:
    """Fetch one supplementary attachment with explicit provenance.

    Supplement links in JATS are often relative filenames.  Only HTTP(S)
    URLs are accepted, the response is bounded before writing, and the
    returned record contains the resolved URL and content hash.  Parsing the
    attachment remains a separate adapter step; this function never guesses
    whether a PDF, spreadsheet, image or archive is scientifically usable.
    """
    base = str(article_url).strip()
    relative = str(href).strip()
    if not base or not relative:
        raise SourceError("article_url and href cannot be empty")
    base_parts = urlparse(base)
    if base_parts.scheme not in {"http", "https"}:
        raise SourceError("article_url must use http or https")
    resolved = urljoin(base, relative)
    parts = urlparse(resolved)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise SourceError("supplement href must resolve to an http(s) URL")
    request = Request(resolved, headers={"User-Agent": "ProvSci/0.3 (+https://provsci.example)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(max_bytes + 1)
    except Exception as exc:  # pragma: no cover - network-specific failures
        raise SourceError(f"could not fetch supplement {resolved}: {exc}") from exc
    if not payload:
        raise SourceError(f"supplement response is empty: {resolved}")
    if len(payload) > max_bytes:
        raise SourceError(f"supplement exceeds max_bytes={max_bytes}: {resolved}")
    digest = hashlib.sha256(payload).hexdigest()
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {
        "source_url": resolved,
        "retrieved_at": datetime.now(timezone.utc).date().isoformat(),
        "retrieval_method": "external_supplement_http",
        "source_version": f"sha256:{digest}",
        "source_hash": digest,
        "content_size_bytes": len(payload),
        "local_path": str(target),
        "href": relative,
    }
