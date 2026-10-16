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
