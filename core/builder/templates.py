from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .mapping import normalize_spec_mapping
from .paths import FIXTURES


def fixture_for_kind(kind: str) -> dict[str, Any]:
    name = "block_spec.json" if kind == "block" else "reyes_spec.json"
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def spec(
    kind: str = "care",
    *,
    village_id: str | None = None,
    status: str = "draft",
    member_id_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    out = normalize_spec_mapping(fixture_for_kind(kind))
    if member_id_map:
        out = remap_ids(out, member_id_map=member_id_map)
    out["village"]["status"] = status
    if village_id:
        out = remap_ids(out, village_id_map={out["village"]["id"]: village_id})
    return out


def view(kind: str, role: str) -> dict[str, Any]:
    fixture = spec(kind)
    return deepcopy(fixture["views"][role])


def remap_ids(
    spec_obj: dict[str, Any],
    *,
    village_id_map: dict[str, str] | None = None,
    member_id_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a fixture copy with village/member ids replaced everywhere they appear as values.

    This deliberately does not substring-rewrite prose. Contract references are structured values:
    object keys, prop values, source refs, modules and arrays. Keeping prose untouched avoids
    corrupting names while preserving every machine reference used by validation/rendering.
    """
    village_id_map = village_id_map or {}
    member_id_map = member_id_map or {}
    replacements = {**village_id_map, **member_id_map}
    out = _rewrite_values(deepcopy(spec_obj), replacements)
    if member_id_map:
        for table in ("channels",):
            if table in out:
                out[table] = {member_id_map.get(key, key): value for key, value in out[table].items()}
    return out


def _rewrite_values(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_rewrite_values(item, replacements) for item in value]
    if isinstance(value, dict):
        return {replacements.get(key, key): _rewrite_values(item, replacements) for key, item in value.items()}
    return value
