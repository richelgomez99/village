from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import templates
from .validate import validate_spec


@dataclass
class RoleResult:
    status: str
    attempts: int = 1
    errors: list[str] = field(default_factory=list)
    ms: int = 0
    ttft_ms: int = 0
    cache_read_tokens: int = 0


async def render_spec(description: str, kind: str, village_id: str, mode: str = "fixture") -> tuple[dict[str, Any], dict[str, RoleResult]]:
    spec = templates.spec(kind, village_id=village_id, status="draft")
    report = validate_spec(spec)
    status = "validated" if report.ok else "template"
    roles = {role: RoleResult(status=status, errors=report.errors) for role in spec["views"]}
    return spec, roles
