from __future__ import annotations

from copy import deepcopy
from typing import Any


def roles_for(kind: str) -> list[str]:
    return ["coordinator", "resident", "volunteer"] if kind == "block" else ["elder", "coordinator", "helper"]


def ensure_chat(spec_or_view: dict[str, Any], role: str | None = None) -> dict[str, Any]:
    target = deepcopy(spec_or_view)
    if "views" in target:
        for view_role, view in target["views"].items():
            _ensure_chat_view(view, view_role)
        return target
    _ensure_chat_view(target, role or "view")
    return target


def _ensure_chat_view(view: dict[str, Any], role: str) -> None:
    elements = view.get("elements", {})
    if view.get("theme") == "elder":
        return
    if any(element.get("type") == "VillageChat" for element in elements.values()):
        return
    eid = "chat"
    suffix = 2
    while eid in elements:
        eid = f"chat{suffix}"
        suffix += 1
    elements[eid] = {
        "type": "VillageChat",
        "props": {
            "bind": "chat:village",
            "composer": True,
            "title": "Village chat",
            "mention_label": "@Village",
            "allow_approve": role == "coordinator",
            "limit": 50,
        },
    }
    elements["s"].setdefault("children", []).append(eid)
    view.setdefault("needs_served", {})[eid] = ["n_safety"]


def strip_lid_qr_channels(spec: dict[str, Any]) -> dict[str, Any]:
    """Apply D22 for today's demo path: no lid stickers or lid scanning."""
    out = deepcopy(spec)
    for member_id, channels in out.get("channels", {}).items():
        out["channels"][member_id] = [ch for ch in channels if ch != "lid_qr"]
    for person in out.get("blueprint", {}).get("people", []):
        profile = person.get("profile", {})
        if isinstance(profile.get("preferred_channels"), list):
            profile["preferred_channels"] = [ch for ch in profile["preferred_channels"] if ch != "lid_qr"]
    return out
