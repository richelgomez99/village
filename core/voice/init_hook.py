from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from core import village
from core.voice.secret import require_secret

INIT_VAR_KEYS = (
    "village_id",
    "member_id",
    "member_short_name",
    "on_duty_name",
    "coordinator_name",
    "language",
    "today_summary",
    "receptionist",
    "caller_known",
    "greeting",
    "village_name",
)


def village_name_spoken(village_id: str) -> str:
    """'Familia Reyes' -> 'la familia Reyes' (first message: "la línea de {{village_name}}")."""
    name = str(village.village_name(village_id) or "").strip()
    if not name:
        return "la familia"
    return f"la {name[0].lower()}{name[1:]}" if name.lower().startswith("familia") else name


def greeting(village_id: str, values: dict[str, str]) -> str:
    """First line of the call (agent first_message is {{greeting}})."""
    if values["caller_known"] == "false":
        if values["receptionist"] == "on":
            recipient = _care_recipient(village_id) or {}
            owner = village.first_name(village_id, recipient.get("id")) if recipient else ""
            obj = {"he": "him", "she": "her", "they": "them"}.get(village.pronoun(recipient) if recipient else "they", "them")
            # D31: disclose up front that a program answers
            return f"{owner + chr(39) + 's' if owner else 'This'} phone, this is Village, a program that answers for {obj}. Who's calling?"
        return "Hola. Soy Luz, de la familia. ¿En qué le puedo ayudar?"
    if values["language"] == "en":
        return f"Hi {values['member_short_name']}, it's Luz, from the family. How are you doing?"
    return f"Hola, {values['member_short_name']}. Soy Luz, de la familia. ¿Cómo está?"


def receptionist_mode(village_id: str | None = None) -> str:
    """D19: "on" only after the receptionist proposal is approved (spec voice.receptionist) or forced by env."""
    env = os.getenv("VILLAGE_RECEPTIONIST", "").strip().lower()
    if env in {"on", "off"}:
        return env
    try:
        if village.receptionist_mode(village_id):  # evolve lane: policies[R-MONEY-UNKNOWN].params.receptionist_mode
            return "on"
        spec = village.spec(village_id) or {}
    except Exception:
        return "off"
    flag = (spec.get("voice") or {}).get("receptionist")
    if flag in {True, "on"}:
        return "on"
    for pol in spec.get("policies") or []:
        if pol.get("rule_id") == "P-RECEPTIONIST" and pol.get("enabled", True) and (pol.get("params") or {}).get("status") != "off":
            return "on"
    return "off"

VOICE_CALLS: list[dict[str, Any]] = []
AGENT_CONFIG = Path(__file__).resolve().parents[2] / "agents" / "agent_configs" / "mom-line.json"


def agent_defaults() -> dict[str, str]:
    """Every dynamic variable the mom-line agent references, with its default (agents/agent_configs/mom-line.json).
    ElevenLabs does NOT fill placeholders for variables missing from a webhook response (simulate proved it:
    "Missing required dynamic variables in first message"), so the init hook always returns the full set."""
    try:
        config = json.loads(AGENT_CONFIG.read_text())
        return {k: str(v) for k, v in config["conversation_config"]["agent"]["dynamic_variables"]["dynamic_variable_placeholders"].items()}
    except Exception:
        return {}


def first_message(values: dict[str, str]) -> str:
    if values["receptionist"] == "on" and values["caller_known"] == "false":
        return values["greeting"]
    return f"Hola, soy Luz, la línea de {values['village_name']}. Soy un programa, no una persona. ¿Cómo está?"


def _people(village_id: str | None = None) -> list[dict[str, Any]]:
    return village.people(village_id)


def _first_name(person: dict[str, Any]) -> str:
    return str(person.get("name", "Guest")).split()[0]


def _care_recipient(village_id: str | None = None) -> dict[str, Any] | None:
    return village.person(village_id, village.care_recipient_id(village_id))


def _demo_elder_caller_ids(village_id: str | None = None) -> set[str]:
    """DEMO_ELDER_CALLER_ID, plus the per-village form DEMO_<RECIPIENT FIRST NAME>_CALLER_ID (derived from the spec)."""
    ids = {os.getenv("DEMO_ELDER_CALLER_ID", "")}
    recipient = _care_recipient(village_id)
    if recipient:
        ids.add(os.getenv(f"DEMO_{_first_name(recipient).upper()}_CALLER_ID", ""))
    return {value for value in ids if value}


def _find_by_phone(caller_id: str, village_id: str | None = None) -> dict[str, Any] | None:
    from core import demo_caller

    recipient = _care_recipient(village_id)
    presenter = caller_id in _demo_elder_caller_ids(village_id) or (recipient is not None and caller_id == recipient.get("phone"))
    if presenter and demo_caller.role() == "unknown":
        return None  # stage switch: the presenter's phone plays an unknown caller (receptionist beat)
    if caller_id in _demo_elder_caller_ids(village_id):
        return recipient
    for person in _people(village_id):
        if person.get("phone") == caller_id:
            return person
    return None


def dynamic_vars(caller_id: str, village_id: str | None = None) -> dict[str, str]:
    village_id = village_id or village.default_village_id()
    if caller_id == "":
        person = _care_recipient(village_id)
    else:
        person = _find_by_phone(caller_id, village_id)

    coordinator = village.first_name(village_id, village.coordinator_id(village_id))
    on_duty = coordinator  # init vars name the coordinator as the escalation contact (as before)
    village_lang = village.spec(village_id).get("village", {}).get("lang", "en")
    if person is None:
        values = {
            "village_id": village_id,
            "member_id": "m_unknown",
            "member_short_name": "there",
            "on_duty_name": on_duty,
            "coordinator_name": coordinator,
            "language": village_lang,
            "today_summary": "Guest caller. Do not share private family details. Money requests still go through the gate.",
            "receptionist": receptionist_mode(village_id),
            "caller_known": "false",
        }
    else:
        is_recipient = person["id"] == village.care_recipient_id(village_id)
        lang = person.get("lang") or person.get("language") or (village_lang if is_recipient else "en")
        verifier = village.default_verifier(village_id)
        verifier_name = village.first_name(village_id, verifier) if verifier else ""
        summary = f"{village.village_name(village_id)}."
        if verifier_name:
            summary += f" {verifier_name} is the money verifier for requests claiming to be {verifier_name}."
        summary += " Use the gate-owned say text."
        values = {
            "village_id": village_id,
            "member_id": person["id"],
            "member_short_name": _first_name(person),
            "on_duty_name": on_duty,
            "coordinator_name": coordinator,
            "language": lang,
            "today_summary": summary,
            "receptionist": receptionist_mode(village_id),
            "caller_known": "true",
        }
    receptionist = values["receptionist"] == "on"
    if receptionist and person is None:
        recipient = _care_recipient(village_id)
        name = _first_name(recipient) if recipient else "the family"
        values["today_summary"] = (
            f"Receptionist mode: you answer {name}'s line for unknown callers. Say: \"{name}'s phone, this is Village. Who's calling?\" "
            "Then call screen_caller with what they claim. Never put a caller through who claims to be family or asks for money "
            "until screen_caller says pass_through. Do not share private family details."
        )
    values["greeting"] = greeting(village_id, values)
    values["village_name"] = village_name_spoken(village_id)
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
    require_secret(x_village_secret)

    payload = await request.json()
    variables = dynamic_vars(payload.get("caller_id", ""), payload.get("village_id") or village.default_village_id())
    record_voice_call(payload, variables)
    try:  # D18: caption the live inbound call on the Control Room (no-op in tests / without an API key)
        from core.voice.captions import watch_inbound

        watch_inbound(payload, variables)
    except Exception:
        pass
    body: dict[str, Any] = {"type": "conversation_initiation_client_data", "dynamic_variables": {**agent_defaults(), **variables}}
    # The agent's static first message ("la línea de la familia") is the fallback if this hook fails; here it names the
    # village, or (D19, receptionist on + unknown caller) Village answers first in English.
    agent: dict[str, Any] = {"first_message": first_message(variables)}
    if variables["receptionist"] == "on" and variables["caller_known"] == "false":
        agent["language"] = "en"
    body["conversation_config_override"] = {"agent": agent}
    return body



# Setup-agent tools, receptionist screening, /voice/token and caption control ride the same graft (core/app.py grafts /hooks/).
from core.voice.voice_routes import router as _voice_router  # noqa: E402

app.router.routes.extend(_voice_router.routes)  # flat routes: core/app.py's graft reads route.path
