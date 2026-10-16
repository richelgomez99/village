"""VillageSpec → bundle files (the per-village layer uploaded into the sandbox).

The bundle = the template app (sandbox/template, or kit/ once it merges: RELEASE_BUNDLE_SOURCE=kit)
+ src/village/spec.json (views only: no printables, so the family word never ships)
+ src/village/theme.json (floor + village layer tokens)
+ tests/floor/floor.test.ts (generated, D8/D17).
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from core.release import floor_tests

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "sandbox" / "template"
KIT_DIR = ROOT / "kit"

# A token at 4.1:1 on the white button surface (the D23 caught-and-fixed demo).
BROKEN_INFO_FG = "#4C80B4"


def bundle_source() -> Path:
    """Bundle source directory. RELEASE_BUNDLE_SOURCE=kit switches to the kit lane's app."""
    if os.environ.get("RELEASE_BUNDLE_SOURCE", "sandbox") == "kit" and (KIT_DIR / "package.json").exists():
        return KIT_DIR
    return TEMPLATE_DIR


def base_theme() -> dict[str, Any]:
    return json.loads((TEMPLATE_DIR / "src" / "village" / "theme.json").read_text())


def village_theme(spec: dict[str, Any]) -> dict[str, Any]:
    theme = base_theme()
    accent = (spec.get("village") or {}).get("theme", {}).get("accent")
    if accent:
        theme["accent"] = accent
    return theme


def public_spec(spec: dict[str, Any]) -> dict[str, Any]:
    v = spec.get("village") or {}
    return {
        "contract_version": spec.get("contract_version"),
        "rev": spec.get("rev"),
        "village": {"id": v.get("id"), "name": v.get("name"), "lang": v.get("lang")},
        "views": copy.deepcopy(spec.get("views") or {}),
    }


def inject_failure(theme: dict[str, Any], kind: str | None) -> dict[str, Any]:
    theme = copy.deepcopy(theme)
    if kind == "contrast":
        theme["tones"]["info"]["fg"] = BROKEN_INFO_FG
    return theme


def template_files(source: Path | None = None) -> dict[str, bytes]:
    """Static app files (everything except node_modules/dist/generated village files)."""
    src = source or bundle_source()
    out: dict[str, bytes] = {}
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src).as_posix()
        if p.is_dir() or rel.startswith(("node_modules", "dist", "tests/floor/")) or "/node_modules/" in rel:
            continue
        if rel.endswith(".DS_Store"):
            continue
        out[rel] = p.read_bytes()
    return out


def village_files(spec: dict[str, Any], rev: int, theme: dict[str, Any]) -> dict[str, bytes]:
    vid = (spec.get("village") or {}).get("id", "v_unknown")
    pub = public_spec(spec)
    pub["rev"] = rev
    files = {
        "src/village/spec.json": json.dumps(pub, ensure_ascii=False, indent=1).encode(),
        "src/village/theme.json": json.dumps(theme, indent=1).encode(),
    }
    for path, text in floor_tests.files(vid, rev).items():
        files[path] = text.encode()
    return files


def build(spec: dict[str, Any], rev: int, *, theme: dict[str, Any] | None = None, inject: str | None = None) -> dict[str, bytes]:
    """Full bundle: template + village layer. `inject` only alters the bundle copy, never the spec."""
    th = inject_failure(theme or village_theme(spec), inject)
    files = template_files()
    files.update(village_files(spec, rev, th))
    return files
