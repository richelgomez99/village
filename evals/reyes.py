"""Reyes village fixture state for evals (pure: reads contracts/fixtures only)."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"
DATASETS = ROOT / "data" / "datasets"

# The eval clock: the headline call time (gate.schema.json example T29).
EVAL_NOW = "2026-10-16T14:02:09-04:00"


def fold(text: str) -> str:
    """Lowercase and strip accents (Lucía -> lucia)."""
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in norm if not unicodedata.combining(ch)).lower().strip()


@lru_cache(maxsize=4)
def load_spec(village_id: str = "v_reyes") -> dict[str, Any]:
    if village_id != "v_reyes":
        raise KeyError(f"no eval fixture for {village_id}")
    return json.loads((FIXTURES / "reyes_spec.json").read_text())


@lru_cache(maxsize=4)
def seed_events(village_id: str = "v_reyes") -> list[dict[str, Any]]:
    if village_id != "v_reyes":
        return []
    return list(json.loads((FIXTURES / "events_reyes_seed.json").read_text())["events"])


def members(village_id: str = "v_reyes") -> list[dict[str, Any]]:
    out = []
    for person in load_spec(village_id)["blueprint"]["people"]:
        consent = person.get("consent") or {}
        first = person["name"].split()[0]
        aliases = sorted({fold(first)} | ({fold(person["short_name"])} if person.get("short_name") else set()))
        member = {
            "id": person["id"],
            "name": first,
            "aliases": aliases,
            "role": person["role"],
            "pronoun": "he" if person.get("relation") in {"son", "father", "brother", "husband"} else "she",
            "has_app_session": person.get("view") not in (None, "elder"),
            "consent": {
                "ai_calls": bool(consent.get("ai_calls")),
                "app_prompts": bool(consent.get("app_prompts")),
            },
        }
        for key in ("dose_logging", "money_verifier"):
            if key in consent and consent[key] is not None:
                member["consent"][key] = bool(consent[key])
        for key in ("share_with", "money_safety_share_with"):
            if consent.get(key):
                member["consent"][key] = list(consent[key])
        out.append(member)
    return out


def resolve_member(claimed: str | None, village_id: str = "v_reyes") -> str | None:
    """Core's claimed_member resolution: name key, alias or member id -> member id, else None (unknown)."""
    if not claimed:
        return None
    key = fold(claimed)
    for member in members(village_id):
        if key == member["id"] or key in member["aliases"] or key == fold(member["name"]):
            if member["role"] == "care_recipient":
                return None  # she cannot be the claimed requester of her own money
            return member["id"]
    return None


def village_state(village_id: str = "v_reyes", now: str = EVAL_NOW) -> dict[str, Any]:
    events = seed_events(village_id)
    shift = next((ev for ev in reversed(events) if ev["kind"] == "shift"), None)
    return {
        "village_id": village_id,
        "now": now,
        "timezone": "America/New_York",
        "kill_switch": False,
        "village_status": "active",
        "coordinator_id": "m_ana",
        "care_recipient_id": "m_carmen",
        "quiet_hours": "22:30-07:00",
        "rota_today": {
            "date": now[:10],
            "on_duty": (shift or {}).get("payload", {}).get("on_duty", "m_ana"),
            "backup": (shift or {}).get("payload", {}).get("backup", "m_lucia"),
        },
        "members": members(village_id),
        "dose_windows": [],
        "open_verifications": [],
        "recent_money_requests": [
            {"event_id": ev["id"], "at": ev["at"]} for ev in events if ev["kind"] == "money_request"
        ],
    }
