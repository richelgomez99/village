"""Village registry and spec lookups (D30: the platform is the project).

Everything village-specific (ids, names, rota, quiet hours, verifiers, the family word) comes from
`data/villages/index.json` -> the village's contract spec + data file, or from the live spec in `db.specs`.
No member names or ids are hardcoded in core/; callers pass `village_id` and member ids.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.settings import ROOT, get_settings

INDEX = ROOT / "data" / "villages" / "index.json"

_SHE = {"mother", "daughter", "sister", "wife", "grandmother", "aunt", "niece", "granddaughter", "mom", "girlfriend"}
_HE = {"father", "son", "brother", "husband", "grandfather", "uncle", "nephew", "grandson", "dad", "boyfriend"}


def _load(path: str | Path | None) -> Any:
    if not path:
        return None
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    return json.loads(p.read_text()) if p.exists() else None


@lru_cache
def registry() -> dict[str, Any]:
    return _load(INDEX) or {"default": "", "villages": {}}


def village_ids() -> list[str]:
    return list(registry().get("villages", {}))


def default_village_id() -> str:
    """DEMO_VILLAGE_ID, else the registry default, else the first registered village."""
    configured = get_settings().demo_village_id.strip()
    if configured:
        return configured
    reg = registry()
    return reg.get("default") or next(iter(reg.get("villages", {})), "")


def entry(village_id: str | None) -> dict[str, Any]:
    return registry().get("villages", {}).get(village_id or default_village_id(), {})


@lru_cache
def fixture_spec(village_id: str) -> dict[str, Any]:
    return _load(entry(village_id).get("spec")) or {}


@lru_cache
def village_data(village_id: str) -> dict[str, Any]:
    return _load(entry(village_id).get("data")) or {}


def seed_events(village_id: str) -> list[dict[str, Any]]:
    return (_load(entry(village_id).get("events")) or {}).get("events", [])


def seed_messages(village_id: str) -> list[dict[str, Any]]:
    return (_load(entry(village_id).get("messages")) or {}).get("messages", [])


def seed_prescriptions(village_id: str) -> list[dict[str, Any]]:
    return json.loads(json.dumps(entry(village_id).get("prescriptions", [])))


def spec(village_id: str | None = None) -> dict[str, Any]:
    """Live published spec if Core has one, else the registered contract fixture."""
    vid = village_id or default_village_id()
    try:
        from core.db import db

        live = db.specs.get(vid)
        if live:
            return live
    except Exception:  # pragma: no cover - import cycles during startup
        pass
    return fixture_spec(vid)


def village_of_member(member_id: str | None) -> str | None:
    if not member_id:
        return None
    for vid in village_ids():
        if any(p.get("id") == member_id for p in people(vid)):
            return vid
    return None


def people(village_id: str | None = None) -> list[dict[str, Any]]:
    return spec(village_id).get("blueprint", {}).get("people", [])


def person(village_id: str | None, member_id: str | None) -> dict[str, Any] | None:
    if not member_id:
        return None
    return next((p for p in people(village_id) if p.get("id") == member_id), None)


def first_name(village_id: str | None, member_id: str | None, fallback: str = "") -> str:
    p = person(village_id, member_id)
    return str(p["name"]).split()[0] if p and p.get("name") else (fallback or (member_id or ""))


def coordinator_id(village_id: str | None = None) -> str | None:
    s = spec(village_id)
    return s.get("village", {}).get("coordinator_id") or next(
        (p["id"] for p in people(village_id) if p.get("role") == "coordinator"), None
    )


def care_recipient_id(village_id: str | None = None) -> str | None:
    s = spec(village_id)
    return s.get("village", {}).get("care_recipient_id") or next(
        (p["id"] for p in people(village_id) if p.get("role") in {"care_recipient", "elder"}), None
    )


def policy_params(village_id: str | None, rule_id: str) -> dict[str, Any] | None:
    for pol in spec(village_id).get("policies", []):
        if pol.get("rule_id") == rule_id:
            return pol.get("params") or {}
    return None


def receptionist_mode(village_id: str | None = None) -> bool:
    """D19 receptionist on the care recipient's line: policies[R-MONEY-UNKNOWN].params.receptionist_mode (set by Evolve)."""
    return bool((policy_params(village_id, "R-MONEY-UNKNOWN") or {}).get("receptionist_mode"))


def quiet_hours(village_id: str | None = None) -> str | None:
    params = policy_params(village_id, "P-QH-01")
    if params and params.get("quiet_hours"):
        return params["quiet_hours"]
    recipient = person(village_id, care_recipient_id(village_id))
    return ((recipient or {}).get("profile") or {}).get("quiet_hours")


def trusted_contacts(village_id: str | None = None) -> list[str]:
    params = policy_params(village_id, "R-MONEY-VERIFY") or {}
    return list(params.get("trusted_contacts") or [])


def default_verifier(village_id: str | None = None) -> str | None:
    """The first trusted money contact from R-MONEY-VERIFY (who a 'family' money claim is checked with)."""
    contacts = trusted_contacts(village_id)
    return contacts[0] if contacts else None


def helpers(village_id: str | None = None) -> list[str]:
    return [p["id"] for p in people(village_id) if p.get("role") in {"caregiver", "helper", "volunteer"}]


def default_on_duty(village_id: str | None = None) -> str | None:
    """Rota fallback when no shift row exists: today's rota entry from the village data, else first helper."""
    vid = village_id or default_village_id()
    hs = helpers(vid)
    return hs[0] if hs else coordinator_id(vid)


def default_backup(village_id: str | None = None) -> str | None:
    return coordinator_id(village_id)


def pronoun(p: dict[str, Any] | None) -> str:
    if not p:
        return "they"
    if p.get("pronoun"):
        return str(p["pronoun"])
    rel = str(p.get("relation") or p.get("relationship") or "").lower()
    if rel in _SHE:
        return "she"
    if rel in _HE:
        return "he"
    return "they"


def relationship_word(village_id: str | None, member_id: str | None, lang: str = "es") -> str:
    words = spec(village_id).get("village", {}).get("theme", {}).get("relationship_words", {})
    word = (words.get(member_id or "") or {}).get(lang)
    if word:
        return word
    p = person(village_id, member_id)
    return (p or {}).get("short_name") or first_name(village_id, member_id)


def family_word(village_id: str | None = None) -> str | None:
    for pr in spec(village_id).get("printables", []):
        if pr.get("kind") == "fridge_card":
            return pr.get("family_word")
    return None


def village_name(village_id: str | None = None) -> str:
    return spec(village_id).get("village", {}).get("name", village_id or "")


def timezone(village_id: str | None = None) -> str:
    return spec(village_id).get("village", {}).get("timezone", "America/New_York")


def member_village(member_id: str | None, fallback: str | None = None) -> str:
    return village_of_member(member_id) or fallback or default_village_id()


# ---- pure: GateInput.village_state from a spec dict (used by services and by the two-village gate test) ----

def state_from_spec(
    spec_doc: dict[str, Any],
    *,
    now: str,
    rota_today: dict[str, Any] | None = None,
    open_verifications: list[dict[str, Any]] | None = None,
    recent_money_requests: list[dict[str, Any]] | None = None,
    dose_windows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rules are parameters (D30): quiet hours (P-QH-01), coordinator (R-MONEY-DEFAULT), money verifiers
    (R-MONEY-VERIFY trusted_contacts + consent), names and pronouns all come from the village spec."""
    village = spec_doc.get("village", {})
    people_ = spec_doc.get("blueprint", {}).get("people", [])
    params = {p.get("rule_id"): p.get("params") or {} for p in spec_doc.get("policies", [])}
    trusted = set((params.get("R-MONEY-VERIFY") or {}).get("trusted_contacts") or [])
    coord = (params.get("R-MONEY-DEFAULT") or {}).get("coordinator") or village.get("coordinator_id") or next(
        (p["id"] for p in people_ if p.get("role") == "coordinator"), None
    )
    recipient = village.get("care_recipient_id")
    channels = spec_doc.get("channels", {})
    members = []
    for p in people_:
        consent = p.get("consent") or {}
        first = str(p.get("name", p["id"])).split()
        first = first[1] if first and first[0].rstrip(".").lower() in {"mr", "mrs", "ms", "dr"} and len(first) > 1 else (first[0] if first else p["id"])
        members.append({
            "id": p["id"],
            "name": first,
            "aliases": [first.lower()],
            "role": p.get("role", "member"),
            "pronoun": pronoun(p),
            "has_app_session": any(str(c).startswith("app:") for c in channels.get(p["id"], [])) or bool(p.get("view") and p["id"] != recipient),
            "consent": {
                "ai_calls": bool(consent.get("ai_calls")),
                "app_prompts": bool(consent.get("app_prompts")),
                "dose_logging": bool(consent.get("dose_logging", False)),
                "money_verifier": bool(consent.get("money_verifier", False)) or p["id"] in trusted,
                "share_with": consent.get("share_with", []),
                "money_safety_share_with": consent.get("money_safety_share_with", []),
            },
        })
    helpers_ = [p["id"] for p in people_ if p.get("role") in {"caregiver", "helper", "volunteer"}]
    state: dict[str, Any] = {
        "village_id": village.get("id", ""),
        "now": now,
        "timezone": village.get("timezone", "America/New_York"),
        "kill_switch": False,
        "coordinator_id": coord,
        "rota_today": rota_today or {"date": now[:10], "on_duty": (helpers_ or [coord])[0], "backup": coord},
        "members": members,
        "dose_windows": dose_windows or [],
        "open_verifications": open_verifications or [],
        "recent_money_requests": recent_money_requests or [],
    }
    if recipient:
        state["care_recipient_id"] = recipient
    qh = (params.get("P-QH-01") or {}).get("quiet_hours")
    if qh:
        state["quiet_hours"] = qh
    return state
