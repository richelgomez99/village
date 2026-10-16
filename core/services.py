from __future__ import annotations

import copy
import asyncio
import json
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from core.clock import clock
from core.db import db
from core.gate import step_verification
from core.gate_fallback import decide as fallback_decide
from core.settings import ROOT
from core.ws_hub import hub


FIXTURES = ROOT / "contracts" / "fixtures"
SCHEMAS = ROOT / "contracts" / "schemas"

_BROADCAST_LOG: list[dict[str, Any]] = []
_MESSAGE_LOG: list[dict[str, Any]] = []


def _load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def _gate_examples() -> list[dict[str, Any]]:
    return _load_json(SCHEMAS / "gate.schema.json").get("examples", [])


def _voice_examples() -> list[dict[str, Any]]:
    return _load_json(SCHEMAS / "voice_tools.schema.json").get("examples", [])


def _scam_exchanges() -> dict[str, Any]:
    return _load_json(FIXTURES / "scam_call_tool_requests.json")


async def now() -> datetime:
    return clock.now()


def _next_id(prefix: str, rows: list[dict[str, Any]]) -> str:
    return f"{prefix}_{len(rows) + 1:04d}"


def _decision_for_verification(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("state")
    claimed_name = str(row.get("claimed_identity") or row.get("claimed_member_id") or "Marco").split()[0]
    if state in {"confirmed", "late_confirmed"}:
        return {
            "id": f"dc_{row['id']}_confirmed",
            "rule_id": "R-MONEY-DEFAULT",
            "decision": "advise_talk_to_coordinator",
            "say": {
                "es": f"{claimed_name} dice que si fue el. Village nunca envia dinero; hable con Ana antes de hacer algo.",
                "en": f"{claimed_name} confirmed it was him. Village never sends money; talk with Ana first.",
            },
            "say_key": "money_confirmed",
            "say_vars": {"claimed_name": claimed_name},
            "verification": _decision_verification(row),
            "writes": [],
            "rules_fired": ["R-MONEY-DEFAULT", "R-MONEY-NEVER"],
        }
    if state in {"denied", "late_denied"}:
        say_es = f"Ese no era {claimed_name}. No mande dinero. Ana ya lo sabe."
        say_en = f"That was not {claimed_name}. Do not send any money. Ana already knows."
        say_key = "money_denied"
        decision = "advise_do_not_send"
    else:
        say_es = f"No pude confirmar con {claimed_name}. No mande dinero. Le aviso a Ana."
        say_en = f"I could not confirm with {claimed_name}. Do not send any money. I am letting Ana know."
        say_key = "money_timeout"
        decision = "advise_do_not_send"
    return {
        "id": f"dc_{row['id']}_{row.get('state', 'verification')}",
        "rule_id": "R-MONEY-DEFAULT",
        "decision": decision,
        "say": {"es": say_es, "en": say_en},
        "say_key": say_key,
        "say_vars": {"claimed_name": claimed_name},
        "verification": _decision_verification(row),
        "writes": [],
        "rules_fired": ["R-MONEY-DEFAULT"],
    }


def _decision_verification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "claimed_member": row.get("claimed_member_id"),
        "deadline": row.get("deadline"),
        "channels": [
            channel.get("via", channel)
            for channel in row.get("channels", [])
        ],
        "state": row.get("state"),
    }


def _applied_answer(row: dict[str, Any]) -> dict[str, Any] | None:
    for answer in row.get("answers", []):
        if answer.get("outcome") == "applied":
            return answer
    return None


def _verification_status_for_voice(row: dict[str, Any]) -> str:
    state = row.get("state")
    if state in {"confirmed", "late_confirmed"}:
        return "confirmed"
    if state in {"denied", "late_denied"}:
        return "denied"
    if state == "unsure":
        return "unsure"
    if state == "unreachable":
        return "unreachable"
    return "timeout"


def _normalize_verification(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    created_at = normalized.get("created_at") or clock.now().isoformat()
    normalized.setdefault("village", "v_reyes")
    normalized.setdefault("subject", "m_carmen")
    normalized.setdefault("claimed_member_id", "m_marco")
    normalized.setdefault("claimed_identity", normalized["claimed_member_id"])
    normalized.setdefault("origin", "report_money_request")
    normalized.setdefault("conversation_id", None)
    normalized.setdefault("request", {"amount": None, "currency": "USD", "method": "unknown", "urgency": "now", "red_flags": []})
    normalized.setdefault("state", "pending")
    normalized.setdefault("status", "pending")
    normalized.setdefault("channels", [])
    normalized.setdefault("answers", [])
    normalized.setdefault("created_at", created_at)
    normalized.setdefault("deadline", (datetime.fromisoformat(created_at) + timedelta(seconds=45)).isoformat())
    normalized.setdefault("call_placed_at", None)
    normalized.setdefault("await_returned_at", None)
    normalized.setdefault("resolved_at", None)
    normalized.setdefault("spoken_say_key", None)
    normalized.setdefault("incident_id", None)
    normalized.setdefault("version", 0)
    normalized.setdefault("transitions", [])
    return normalized


def _with_channel_status(row: dict[str, Any], via: str, member_id: str, status: str) -> dict[str, Any]:
    channels = []
    found = False
    for channel in row.get("channels", []):
        if isinstance(channel, str):
            channel = {"via": channel, "member_id": member_id, "status": "sent", "at": row.get("created_at", clock.now().isoformat())}
        channel = dict(channel)
        if channel.get("via") == via and channel.get("member_id", member_id) == member_id:
            channel["status"] = status
            channel["at"] = clock.now().isoformat()
            found = True
        channels.append(channel)
    if not found:
        channels.append({"via": via, "member_id": member_id, "status": status, "at": clock.now().isoformat()})
    return {**row, "channels": channels}


def _last_event_id(verification_id: str, kinds: set[str]) -> str | None:
    for event in reversed(db.events):
        if event["kind"] in kinds and event.get("payload", {}).get("verification_id") == verification_id:
            return event["id"]
    return None


def _incident_event_id(incident_id: str | None) -> str | None:
    for event in reversed(db.events):
        if event["kind"] == "incident" and event.get("payload", {}).get("incident_id") == incident_id:
            return event["id"]
    return None


def _gate_decide(inp: dict[str, Any]) -> dict[str, Any]:
    try:
        from core.gate import decide as real_decide  # type: ignore
    except (ImportError, AttributeError):
        real_decide = fallback_decide
    return real_decide(inp)


def _village_state(village_id: str) -> dict[str, Any]:
    spec = db.specs.get(village_id, {})
    members = []
    for person in spec.get("blueprint", {}).get("people", []):
        consent = person.get("consent", {})
        members.append({
            "id": person["id"],
            "name": person["name"].split()[0],
            "aliases": [person["name"].split()[0].lower()],
            "role": person["role"],
            "pronoun": "she" if person["id"] in {"m_carmen", "m_ana", "m_lucia"} else "he",
            "has_app_session": person["id"] != "m_carmen",
            "consent": {
                "ai_calls": bool(consent.get("ai_calls")),
                "app_prompts": bool(consent.get("app_prompts")),
                "dose_logging": bool(consent.get("dose_logging", False)),
                "money_verifier": bool(consent.get("money_verifier", False)),
                "share_with": consent.get("share_with", []),
                "money_safety_share_with": consent.get("money_safety_share_with", []),
            },
        })
    shift = next((ev for ev in reversed(db.events) if ev["kind"] == "shift"), None)
    today = clock.now().date().isoformat()
    return {
        "village_id": village_id,
        "now": clock.now().isoformat(),
        "timezone": "America/New_York",
        "kill_switch": False,
        "coordinator_id": "m_ana",
        "care_recipient_id": "m_carmen",
        "quiet_hours": "22:30-07:00",
        "rota_today": {
            "date": today,
            "on_duty": shift["payload"].get("on_duty") if shift else "m_marco",
            "backup": shift["payload"].get("backup") if shift else "m_ana",
        },
        "members": members,
        "dose_windows": [],
        "open_verifications": [],
        "recent_money_requests": [
            {"event_id": ev["id"], "at": ev["at"]} for ev in db.events if ev["kind"] == "money_request"
        ],
    }


async def decide(
    village_id: str,
    candidate: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    actor_token: str | None = None,
) -> dict[str, Any]:
    del actor_token
    alloc = {
        "decision_id": _next_id("dc", db.decisions),
        "verification_id": _next_id("ver", []),
        "incident_id": "inc_stub",
    }
    inp = {"village_state": _village_state(village_id), "event": candidate, "alloc": alloc}
    if idempotency_key:
        cached = await db.get_idem(idempotency_key)
        if cached:
            return copy.deepcopy(cached["decision"])
        inp["idempotency_key"] = idempotency_key
    decision = _gate_decide(inp)
    decision["id"] = decision.get("id") or alloc["decision_id"]
    decision_row = {
        "id": decision["id"],
        "village_id": village_id,
        "at": clock.now().isoformat(),
        "actor": "gate",
        "kind": "decision",
        "text": decision["decision"],
        "rule_id": decision["rule_id"],
        "refs": [{"kind": "mode", "id": "acted_alone"}],
        "source": candidate.get("source", {"kind": "system", "ref": "gate"}),
        "gate": copy.deepcopy(decision),
        "event_ids": [],
    }
    await db.create_decision(decision_row)
    await control(village_id, "gate", {"decision": decision})
    if decision.get("verification"):
        verification = decision["verification"]
        await db.upsert_verification({
            "id": verification["id"],
            "village": village_id,
            "subject": candidate.get("payload", {}).get("subject", "m_carmen"),
            "claimed_member_id": verification["claimed_member"],
            "claimed_identity": candidate.get("payload", {}).get("claimed_identity", verification["claimed_member"]),
            "origin": candidate.get("payload", {}).get("origin", "report_money_request"),
            "conversation_id": candidate.get("source", {}).get("ref"),
            "request": candidate.get("payload", {}),
            "state": verification["state"],
            "status": "pending",
            "channels": [
                {"via": channel, "member_id": verification["claimed_member"], "status": "sent", "at": candidate["at"]}
                for channel in verification["channels"]
            ],
            "answers": [],
            "created_at": candidate["at"],
            "deadline": verification["deadline"],
            "call_placed_at": None,
            "await_returned_at": None,
            "resolved_at": None,
            "spoken_say_key": None,
            "incident_id": None,
            "version": 0,
            "transitions": [{"from": "created", "to": verification["state"], "at": candidate["at"], "cause": "created"}],
        })
    written_events = []
    for draft in decision.get("writes", []):
        event = await record_event(
            village_id,
            draft,
            actor=candidate["actor"],
            source=candidate["source"],
            decision_id=decision["id"],
        )
        written_events.append(event)
        decision_row["event_ids"].append(event["id"])
        if draft.get("kind") == "escalation" and decision.get("escalate"):
            decision["escalate"]["related_event_id"] = event["id"]
    decision["_events"] = written_events
    if idempotency_key:
        await db.put_idem(idempotency_key, {"decision_id": decision["id"], "decision": copy.deepcopy(decision), "at": clock.now().isoformat()})
    return decision


async def record_event(
    village_id: str,
    draft: dict[str, Any],
    *,
    actor: str,
    source: dict[str, Any],
    decision_id: str | None = None,
) -> dict[str, Any]:
    event = {
        "id": draft.get("id", _next_id("ev", db.events)),
        "village": village_id,
        "kind": draft["kind"],
        "payload": draft.get("payload", {}),
        "actor": actor,
        "source": source,
        "decision_id": decision_id,
        "at": draft.get("at") or (await now()).isoformat(),
    }
    await db.create_event(event)
    return event


async def handle_tool(name: str, request: dict[str, Any]) -> dict[str, Any]:
    idem_key = None
    if request.get("conversation_id"):
        idem_key = f"{request.get('conversation_id')}:{request.get('tool_call_id', name)}"
        cached = await db.get_idem(idem_key)
        if cached and cached.get("response"):
            return copy.deepcopy(cached["response"])

    if name == "log_dose":
        village_id = request.get("village_id", "v_reyes")
        taken_at = request.get("taken_at") or clock.now().isoformat()
        candidate = {
            "village": village_id,
            "kind": "dose",
            "payload": {
                "subject": "m_carmen",
                "slot": request.get("slot") if request.get("slot") not in (None, "current") else "evening",
                "taken_at": taken_at,
                "confidence": "confirmed" if request.get("confidence") == "confirmed_by_caller" else "uncertain",
                "via": "phone_line",
            },
            "actor": "m_carmen",
            "source": {
                "kind": "call",
                "ref": request.get("conversation_id", "conv_stub"),
                "secs": int(request.get("call_secs", 0)),
                "quote": request.get("utterance", ""),
            },
            "at": taken_at,
        }
        decision = await decide(
            village_id,
            candidate,
            idempotency_key=idem_key,
        )
        events = decision.get("_events", [])
        first_event = events[0] if events else None
        say = decision.get("say", {}).get("es", "")
        response = {
            "decision": decision["decision"],
            "say": say,
            "say_key": decision.get("say_key"),
            "rule_id": decision["rule_id"],
            "lang": "es",
            "decision_id": decision["id"],
            "data": {
                "status": "recorded" if decision["decision"] == "record" else decision["decision"],
                "slot": candidate["payload"]["slot"],
                "dose_event_id": first_event["id"] if first_event else None,
                "taken_at": candidate["payload"]["taken_at"],
            },
        }
        if idem_key:
            await db.put_idem(idem_key, {"decision_id": decision["id"], "decision": copy.deepcopy(decision), "response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response

    if name == "report_money_request":
        village_id = request.get("village_id", "v_reyes")
        deadline = (clock.now() + timedelta(seconds=45)).isoformat()
        claimed = request.get("claimed_member")
        claimed_member_id = claimed if str(claimed).startswith("m_") else "m_marco" if claimed in {"marco", None} else None
        candidate = {
            "village": village_id,
            "kind": "money_request",
            "payload": {
                "subject": "m_carmen",
                "claimed_member_id": claimed_member_id or "m_marco",
                "claimed_identity": request.get("claimed_identity", "Marco"),
                "amount": request.get("amount", 0),
                "currency": request.get("currency", "USD"),
                "method": request.get("method", "unknown"),
                "urgency": request.get("urgency", "now"),
                "red_flags": request.get("red_flags", []),
                "utterance": request.get("utterance", ""),
                "deadline": deadline,
            },
            "actor": "m_carmen",
            "source": {"kind": "call", "ref": request.get("conversation_id", "conv_stub"), "secs": int(request.get("call_secs", 0)), "quote": request.get("utterance", "")},
            "at": clock.now().isoformat(),
        }
        result = await start_verification(village_id, candidate, idempotency_key=idem_key or f"{request.get('conversation_id', 'conv_stub')}:{name}")
        decision = result["decision"]
        response = {
            "decision": decision["decision"],
            "say": decision["say"]["es"],
            "say_key": decision.get("say_key"),
            "rule_id": decision["rule_id"],
            "lang": "es",
            "decision_id": decision["id"],
            "data": {
                "status": result["status"],
                "verification_id": result["verification_id"],
                "claimed_member_id": result["claimed_member_id"],
                "channels": result["channels"],
                "deadline": result["deadline"],
                "deadline_secs": 45,
                "next": "await_verification",
            },
        }
        if idem_key:
            await db.put_idem(idem_key, {"decision_id": decision["id"], "decision": copy.deepcopy(decision), "response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response

    for example in _voice_examples():
        if example.get("tool") == name:
            response = copy.deepcopy(example["response"])
            if name == "log_dose":
                await record_event(
                    request.get("village_id", "v_reyes"),
                    {
                        "kind": "dose",
                        "payload": {
                            "subject": "m_carmen",
                            "slot": response.get("data", {}).get("slot", request.get("slot", "evening")),
                            "taken_at": response.get("data", {}).get("taken_at"),
                            "confidence": "confirmed",
                            "via": "phone_line",
                        },
                    },
                    actor="m_carmen",
                    source={
                        "kind": "call",
                        "ref": request.get("conversation_id", "conv_stub"),
                        "secs": int(request.get("call_secs", 0)),
                        "quote": request.get("utterance", ""),
                    },
                    decision_id=response.get("decision_id"),
                )
            return response

    fixture = _scam_exchanges()
    for variant in fixture.get("variants", {}).values():
        for exchange in variant.get("exchanges", []):
            if exchange.get("tool") == name:
                return copy.deepcopy(exchange["response"])

    raise KeyError(name)


async def handle_action(village_id: str, name: str, request: dict[str, Any]) -> dict[str, Any]:
    member_id = request.get("member_id", "m_carmen")
    req_id = request.get("req_id")
    idem_key = f"{member_id}:{req_id}" if req_id else None
    if idem_key:
        cached = await db.get_idem(idem_key)
        if cached and cached.get("response"):
            return copy.deepcopy(cached["response"])

    if name == "log_dose":
        body = {
            "village_id": village_id,
            "conversation_id": request.get("req_id", f"app_{village_id}_log_dose"),
            "caller_id": member_id,
            "call_secs": request.get("call_secs", 0),
            "utterance": request.get("utterance", "app action"),
            "slot": request.get("slot", "evening"),
            "confidence": "confirmed_by_caller",
            "tool_call_id": request.get("req_id", "app_action"),
        }
        response = await handle_tool("log_dose", body)
        result = {"type": "result", "req_id": req_id, "ok": True, "decision": response}
        if idem_key:
            await db.put_idem(idem_key, {"response": copy.deepcopy(result), "at": clock.now().isoformat()})
        return result
    if name == "answer_verification":
        payload = request.get("payload") or request
        row = await answer_verification(
            payload["verification_id"],
            payload["answer"],
            via=payload.get("via", "app_prompt"),
            member_id=member_id,
            quote=payload.get("quote") or payload.get("listener_quote"),
            call_sid=payload.get("call_sid"),
        )
        decision = _decision_for_verification(row)
        result = {
            "type": "result",
            "req_id": req_id,
            "ok": row.get("outcome") != "conflict",
            "decision": decision,
            "event_id": _last_event_id(row["id"], {"verification_confirmed", "verification_denied", "verification_timeout"}),
        }
        if idem_key:
            await db.put_idem(idem_key, {"response": copy.deepcopy(result), "at": clock.now().isoformat()})
        return result
    if name == "start_verification":
        payload = request.get("payload") or request
        claimed = request.get("arg") or payload.get("claimed_member_id") or payload.get("claimed_member") or "m_marco"
        claimed_member_id = claimed if str(claimed).startswith("m_") else "m_marco"
        candidate = {
            "village": village_id,
            "kind": "money_request",
            "payload": {
                "origin": "start_verification",
                "subject": payload.get("subject", "m_carmen"),
                "claimed_member_id": claimed_member_id,
                "claimed_identity": payload.get("claimed_identity", claimed_member_id),
                "amount": payload.get("amount"),
                "currency": payload.get("currency", "USD"),
                "method": payload.get("method", "unknown"),
                "urgency": payload.get("urgency", "now"),
                "red_flags": payload.get("red_flags", []),
                "utterance": payload.get("utterance", "app verification request"),
                "deadline": (clock.now() + timedelta(seconds=45)).isoformat(),
            },
            "actor": member_id,
            "source": {"kind": "app", "ref": member_id},
            "at": clock.now().isoformat(),
        }
        started = await start_verification(village_id, candidate, idempotency_key=idem_key or f"{member_id}:start_verification")
        result = {"type": "result", "req_id": req_id, "ok": True, "decision": started["decision"]}
        if idem_key:
            await db.put_idem(idem_key, {"response": copy.deepcopy(result), "at": clock.now().isoformat()})
        return result
    if name == "ack_incident":
        incident_id = request.get("arg") or request.get("incident_id")
        event = await record_event(
            village_id,
            {
                "kind": "ack",
                "payload": {
                    "of_event_id": _incident_event_id(incident_id),
                    "status": request.get("status", "got_it"),
                    "channel": "app",
                    "incident_id": incident_id,
                },
            },
            actor=member_id,
            source={"kind": "app", "ref": member_id},
            decision_id=None,
        )
        result = {"type": "result", "req_id": req_id, "ok": True, "event_id": event["id"], "decision": {"decision": "allow", "data": {"incident_id": incident_id}}}
        if idem_key:
            await db.put_idem(idem_key, {"response": copy.deepcopy(result), "at": clock.now().isoformat()})
        return result
    if name in {"check_in_ok", "need_help"}:
        return {"type": "result", "req_id": req_id, "ok": True, "decision": {"decision": "allow", "data": {"action": name}}}
    raise KeyError(name)


async def start_verification(
    village_id: str,
    candidate: dict[str, Any],
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    decision = await decide(village_id, candidate, idempotency_key=idempotency_key)
    verification = decision.get("verification")
    if not verification:
        return {"status": "unverifiable", "decision": decision}
    return {
        "decision": decision,
        "status": "pending",
        "verification_id": verification["id"],
        "claimed_member_id": verification["claimed_member"],
        "channels": verification["channels"],
        "deadline": verification["deadline"],
    }


async def answer_verification(
    verification_id: str,
    answer: str,
    *,
    via: str,
    member_id: str,
    quote: str | None = None,
    call_sid: str | None = None,
) -> dict[str, Any]:
    current = db.verifications.get(verification_id)
    if current is None:
        raise KeyError(verification_id)
    current = _normalize_verification(current)
    next_row, emits = step_verification(
        current,
        {"type": "answer", "answer": answer, "via": via, "member_id": member_id, "quote": quote, "call_sid": call_sid},
        clock.now(),
    )
    next_row = _with_channel_status(next_row, via, member_id, "answered")
    if call_sid and next_row.get("answers"):
        next_row["answers"][-1]["call_sid"] = call_sid
    updated = await db.cas_update("verification", verification_id, current.get("version", 0), next_row)
    if not updated:
        latest = db.verifications[verification_id]
        return {**latest, "outcome": "conflict"}
    for draft in emits:
        await record_event(
            current["village"],
            draft,
            actor=member_id if draft["kind"].startswith("verification_") else "gate",
            source={"kind": "app" if via == "app_prompt" else "call", "ref": member_id},
            decision_id=None,
        )
    outcome = next_row.get("answers", [{}])[-1].get("outcome", "applied")
    return {**updated[0], "outcome": outcome}


async def await_verification(verification_id: str, *, max_wait_s: int = 30) -> dict[str, Any]:
    max_wait_s = min(max_wait_s, 30)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_wait_s
    row = db.verifications.get(verification_id)
    if row is None:
        raise KeyError(verification_id)
    row = _normalize_verification(row)
    if row != db.verifications.get(verification_id):
        await db.upsert_verification(row)

    while row.get("state") == "pending" and loop.time() < deadline:
        await asyncio.sleep(min(0.25, max(deadline - loop.time(), 0)))
        row = db.verifications.get(verification_id)
        if row is None:
            raise KeyError(verification_id)
        row = _normalize_verification(row)

    if row.get("state") == "pending":
        next_row, emits = step_verification(row, {"type": "await_returned"}, clock.now())
        if next_row.get("state") == "default_spoken":
            updated = await db.cas_update("verification", verification_id, row.get("version", 0), next_row)
            if updated:
                row = updated[0]
                for draft in emits:
                    await record_event(
                        row["village"],
                        draft,
                        actor="gate",
                        source={"kind": "system", "ref": "await_verification"},
                        decision_id=None,
                    )
        else:
            row = next_row

    applied = _applied_answer(row)
    status = _verification_status_for_voice(row)
    decision = _decision_for_verification(row)
    return {
        "verification_id": verification_id,
        "decision": decision["decision"],
        "say": decision["say"],
        "say_key": decision["say_key"],
        "status": status,
        "state": row.get("state"),
        "answered_via": applied.get("via") if applied else None,
        "answered_at_secs": applied.get("secs_since_created") if applied else None,
        "incident_id": row.get("incident_id"),
    }


async def broadcast(village_id: str, msg: dict[str, Any], *, to: str = "all") -> None:
    _BROADCAST_LOG.append({"village_id": village_id, "to": to, "msg": copy.deepcopy(msg)})


async def control(village_id: str, kind: str, payload: dict[str, Any]) -> None:
    await broadcast(village_id, {"type": "control", "kind": kind, "payload": payload}, to="control")
    await hub.control(village_id, kind, payload)


async def post_message(
    village_id: str,
    *,
    author: str,
    kind: str,
    text: str,
    refs: tuple[str, ...] | list[str] = (),
    source: dict[str, Any],
) -> dict[str, Any]:
    message = {
        "id": f"msg_stub_{len(_MESSAGE_LOG) + 1}",
        "village": village_id,
        "author": author,
        "kind": kind,
        "text": text,
        "refs": list(refs),
        "source": source,
        "at": (await now()).isoformat(),
    }
    _MESSAGE_LOG.append(message)
    await broadcast(village_id, {"type": "chat", "message": message})
    return message


def stub_logs() -> dict[str, Any]:
    return {"broadcasts": copy.deepcopy(_BROADCAST_LOG), "messages": copy.deepcopy(_MESSAGE_LOG)}
