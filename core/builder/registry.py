"""Per-kind data (D30): which fixture, record, intake plan and replay transcript a village kind uses.
Code is village-agnostic; everything named lives in data/builder/villages.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .paths import DATA, FIXTURES, ROOT

REGISTRY = DATA / "builder" / "villages.json"


@lru_cache
def registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def kind_config(kind: str) -> dict[str, Any]:
    reg = registry()
    if kind not in reg:
        raise ValueError(f"unknown village kind: {kind}")
    return reg[kind]


def fixture_path(kind: str) -> Path:
    return FIXTURES / kind_config(kind)["fixture"]


def record(kind: str) -> dict[str, Any]:
    p = ROOT / kind_config(kind)["record"]
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def path(kind: str, key: str) -> Path:
    return ROOT / kind_config(kind)[key]
