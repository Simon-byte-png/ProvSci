"""Domain/profile defaults for the generic ProvSci result slice.

The core pipeline is deliberately domain-agnostic.  A profile names the
field vocabulary and validation policy used by a run; specialized profiles
can be layered on later without changing the provenance contract.
"""

from __future__ import annotations

from typing import Any


DEFAULT_DOMAIN = "scientific_quantitative_result_v1"
DEFAULT_PROFILE_PATH = "schemas/scientific_quantitative_result_profile.json"


def resolve_domain(metadata: dict[str, Any] | None = None) -> str:
    """Return an explicit run domain or the generic quantitative profile."""
    value = (metadata or {}).get("domain")
    return str(value).strip() if value not in (None, "") else DEFAULT_DOMAIN
