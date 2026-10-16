from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

ROOT = Path(__file__).resolve().parents[2]
REYES_SPEC = ROOT / "contracts" / "fixtures" / "reyes_spec.json"

INIT_VAR_KEYS = (
    "village_id",
    "member_id",
    "member_short_name",
    "on_duty_name",
    "coordinator_name",
    "language",
    "today_summary",
)

VOICE_CALLS: list[dict[str, Any]] = []


def _reyes_spec() -> dict[str, Any]:
    return json.loads(REYES_SPEC.read_text())


def _people() -> list[dict[str, Any]]:
    return _reyes_spec()["blueprint"]["people"]


def _first_name(person: dict[str, Any]) -> str:
    return str(person.get("name", "Guest")).split()[0]


def _find_by_phone(caller_id: str) -> dict[str, Any] | None:
    demo_carmen = os.getenv("DEMO_CARMEN_CALLER_ID", "")
    if demo_carmen and caller_id == demo_carmen:
        return next(person for person in _people() if person["id"] == "m_carmen")
    for person in _people():
        if person.get("phone") == caller_id:
            return person
    return None


def _care_recipient() -> dict[str, Any]:
    return next(person for person in _people() if person["id"] == "m_carmen")


def dynamic_vars(caller_id: str, village_id: str = "v_reyes") -> dict[str, str]:
    if caller_id == "":
        person = _care_recipient()
    else:
        person = _find_by_phone(caller_id)

    if person is None:
        values = {
            "village_id": village_id,
            "member_id": "m_unknown",
            "member_short_name": "there",
            "on_duty_name": "Ana",
            "coordinator_name": "Ana",
            "language": "es",
            "today_summary": "Guest caller. Do not share private family details. Money requests still go through the gate.",
        }
    else:
        lang = person.get("lang") or person.get("language") or ("es" if person["id"] == "m_carmen" else "en")
        values = {
            "village_id": village_id,
            "member_id": person["id"],
            "member_short_name": _first_name(person),
            "on_duty_name": "Ana",
            "coordinator_name": "Ana",
            "language": lang,
            "today_summary": "Reyes village. Marco is the money verifier for requests claiming to be Marco. Use the gate-owned say text.",
        }
    return {key: values[key] for key in INIT_VAR_KEYS}


def record_voice_call(payload: dict[str, Any], variables: dict[str, str]) -> None:
    VOICE_CALLS.append({
        "conversation_id": payload.get("conversation_id", ""),
        "village": variables["village_id"],
        "member_id": variables["member_id"],
        "agent_id": payload.get("agent_id", ""),
        "direction": "web" if payload.get("caller_id", "") == "" else "inbound",
        "caller_id": payload.get("caller_id", ""),
        "call_sid": payload.get("call_sid", ""),
        "init_vars": variables,
    })


app = FastAPI(title="Village ElevenLabs init hook")


@app.post("/hooks/elevenlabs/init")
async def init_hook(
    request: Request,
    x_village_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    expected = os.getenv("VILLAGE_SECRET")
    if expected and x_village_secret != expected:
        raise HTTPException(status_code=401, detail="bad voice secret")

    payload = await request.json()
    variables = dynamic_vars(payload.get("caller_id", ""), payload.get("village_id", "v_reyes"))
    record_voice_call(payload, variables)
    return {"dynamic_variables": variables}

