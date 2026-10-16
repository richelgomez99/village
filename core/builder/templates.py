from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .mapping import normalize_spec_mapping
from .paths import FIXTURES


def fixture_for_kind(kind: str) -> dict[str, Any]:
    name = "block_spec.json" if kind == "block" else "reyes_spec.json"
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def spec(kind: str = "care", *, village_id: str | None = None, status: str = "draft") -> dict[str, Any]:
    out = normalize_spec_mapping(fixture_for_kind(kind))
    out["village"]["status"] = status
    if village_id:
        out["village"]["id"] = village_id
    return out


def view(kind: str, role: str) -> dict[str, Any]:
    fixture = spec(kind)
    return deepcopy(fixture["views"][role])
