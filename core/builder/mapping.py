from __future__ import annotations

from copy import deepcopy
from typing import Any

CARE_ROLES = ["elder", "coordinator", "helper"]
BLOCK_ROLES = ["coordinator", "resident", "volunteer"]

MEMORY_MAP = {
    "full": "typical",
    "typical": "typical",
    "lapses": "mild_lapses",
    "mild_lapses": "mild_lapses",
    "impaired": "significant",
    "significant": "significant",
    "unknown": "typical",
}
TECH_COMFORT_MAP = {
    "none": "phone",
    "low": "phone",
    "phone": "phone",
    "medium": "both",
    "both": "both",
    "high": "app",
    "app": "app",
    "unknown": "app",
}
PHONE_CHANNELS = {"phone_line", "outbound_calls"}
APP_PROMPT_CHANNELS = {"verification:app_prompt"}
CALL_CONSENT_CHANNELS = {"verification:call"}


def roles_for(kind: str) -> list[str]:
    if kind == "block":
        return list(BLOCK_ROLES)
    if kind == "care":
        return list(CARE_ROLES)
    raise ValueError(f"unknown village kind: {kind}")


def map_memory(value: str | None) -> str:
    return MEMORY_MAP.get(value or "unknown", "typical")


def map_tech_comfort(value: str | None) -> str:
    return TECH_COMFORT_MAP.get(value or "unknown", "app")


def role_for_person(kind: str, person: dict[str, Any]) -> str | None:
    if person.get("view") is not None:
        return person["view"]
    role = person.get("role")
    tech = map_tech_comfort(person.get("profile", {}).get("tech_comfort"))
    if tech == "phone":
        return None
    if kind == "block":
        if role == "coordinator":
            return "coordinator"
        if role == "volunteer":
            return "volunteer"
        if role == "resident":
            return "resident"
        return None
    if role == "care_recipient":
        return "elder"
    if role == "coordinator":
        return "coordinator"
    if role in {"caregiver", "professional_caregiver"}:
        return "helper"
    return None


def channels_for_person(kind: str, person: dict[str, Any]) -> list[str]:
    profile = person.get("profile", {})
    consent = person.get("consent", {})
    channels: list[str] = []
    view = role_for_person(kind, person)
    tech = map_tech_comfort(profile.get("tech_comfort"))
    preferred = set(profile.get("preferred_channels", []))

    if view:
        channels.append(f"app:{view}")
    if tech in {"phone", "both"} or "phone_line" in preferred:
        channels.append("phone_line")
    if tech == "both" or "outbound_calls" in preferred:
        channels.append("outbound_calls")
    if consent.get("app_prompts") and view:
        channels.append("verification:app_prompt")
    if consent.get("ai_calls"):
        channels.append("verification:call")
    if "fridge_card" in preferred or (kind == "care" and person.get("role") == "care_recipient"):
        channels.append("fridge_card")

    return _dedupe(ch for ch in channels if ch != "lid_qr")


def derive_channels(spec: dict[str, Any]) -> dict[str, list[str]]:
    kind = spec.get("village", {}).get("kind", "care")
    return {person["id"]: channels_for_person(kind, person) for person in spec.get("blueprint", {}).get("people", [])}


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(profile)
    out["memory"] = map_memory(out.get("memory"))
    out["tech_comfort"] = map_tech_comfort(out.get("tech_comfort"))
    if isinstance(out.get("preferred_channels"), list):
        out["preferred_channels"] = _dedupe(ch for ch in out["preferred_channels"] if ch != "lid_qr")
    return out


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


def fridge_printables_only(spec: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(spec)
    out["printables"] = [p for p in out.get("printables", []) if p.get("kind") == "fridge_card"]
    return out


def normalize_spec_mapping(spec: dict[str, Any]) -> dict[str, Any]:
    out = fridge_printables_only(strip_lid_qr_channels(spec))
    kind = out.get("village", {}).get("kind", "care")
    valid_roles = set(roles_for(kind))
    for person in out.get("blueprint", {}).get("people", []):
        person["profile"] = normalize_profile(person.get("profile", {}))
        view = role_for_person(kind, person)
        person["view"] = view if view in valid_roles else None
    out["channels"] = derive_channels(out)
    return ensure_chat(out)


def _dedupe(values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


ELDER_BUTTONS_D22 = 3


def elder_view_problems(view: dict[str, Any]) -> list[str]:
    """D22 elder view: TonightCard + exactly 3 BigButtons + a 911 ContactCard, no chat, no med names."""
    els = view.get("elements", {})
    types = [e.get("type") for e in els.values()]
    problems = []
    if view.get("theme") != "elder":
        problems.append("theme is not elder")
    if "TonightCard" not in types:
        problems.append("missing TonightCard")
    if types.count("BigButton") != ELDER_BUTTONS_D22:
        problems.append(f"{types.count('BigButton')} BigButtons, D22 wants 3")
    if not any(e.get("type") == "ContactCard" and "911" in json_text(e) for e in els.values()):
        problems.append("missing 911 ContactCard")
    if "VillageChat" in types:
        problems.append("VillageChat in elder view")
    return problems


def json_text(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def components_for(capability: str) -> list[str]:
    """Catalog component types a capability implements (capabilities.yaml `implements`, catalog types only)."""
    from .capabilities import catalog
    from .validate import catalog_types

    types = set(catalog_types())
    return [c for c in catalog()["capabilities"].get(capability, {}).get("implements", []) if c in types]


def capability_components(plan_by_member: dict[str, list[str]]) -> dict[str, list[str]]:
    """member → catalog components chosen through their capabilities (why this screen? → this capability)."""
    return {m: list(dict.fromkeys(c for cap in caps for c in components_for(cap))) for m, caps in plan_by_member.items()}
