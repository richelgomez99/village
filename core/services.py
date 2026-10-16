from __future__ import annotations

import copy
import asyncio
import json
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from core import village as villages
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


def _vid(village_id: str | None) -> str:
    return village_id or villages.default_village_id()


def _recipient(village_id: str | None) -> str | None:
    return villages.care_recipient_id(_vid(village_id))


def _coord(village_id: str | None) -> str | None:
    return villages.coordinator_id(_vid(village_id))


def _verifier(village_id: str | None) -> str | None:
    return villages.default_verifier(_vid(village_id)) or villages.default_on_duty(_vid(village_id))


def _rel(village_id: str | None, lang: str = "en") -> str:
    """How the village speaks about its care recipient (spec theme.relationship_words / short_name)."""
    vid = _vid(village_id)
    return villages.relationship_word(vid, _recipient(vid), lang) or "them"


def _coord_name(village_id: str | None) -> str:
    vid = _vid(village_id)
    return villages.first_name(vid, _coord(vid), "the coordinator")


def _resolve_member(village_id: str | None, claimed: Any) -> str | None:
    """A member id (`m_`/`b_`), or a first name / alias matched against the village's spec people."""
    if not claimed:
        return None
    text = str(claimed)
    if text.startswith(("m_", "b_")):
        return text
    import unicodedata

    def fold(value: str) -> str:
        return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()

    for person in villages.people(_vid(village_id)):
        names = [part for part in str(person.get("name", "")).split() if part.rstrip(".").lower() not in {"mr", "mrs", "ms", "dr"}]
        if names and fold(names[0]) == fold(text.split()[0]):
            return person["id"]
    return None


def _next_id(prefix: str, rows: list[dict[str, Any]]) -> str:
    return f"{prefix}_{len(rows) + 1:04d}"


def _claimed_name(row: dict[str, Any]) -> str:
    member = db.members.get(row.get("claimed_member_id") or "", {})
    if member.get("name"):
        return str(member["name"]).split()[0]
    fallback = villages.first_name(row.get("village"), _verifier(row.get("village")), "the family member")
    return str(row.get("claimed_identity") or row.get("claimed_member_id") or fallback).split()[0]


def _say(key: str, **vars: Any) -> dict[str, str]:
    from core.gate import say as gate_say

    return gate_say(key, **vars)


def _decision_for_verification(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("state")
    claimed_name = _claimed_name(row)
    if state in {"confirmed", "late_confirmed"}:
        say_key, decision, rules = "money_confirmed", "advise_talk_to_coordinator", ["R-MONEY-DEFAULT", "R-MONEY-NEVER"]
    elif state in {"denied", "late_denied"}:
        say_key, decision, rules = "money_denied", "advise_do_not_send", ["R-MONEY-DEFAULT", "R-MONEY-NEVER"]
    else:
        say_key, decision, rules = "money_timeout", "advise_do_not_send", ["R-MONEY-DEFAULT"]
    say_vars = {"claimed_name": claimed_name}
    vid = _vid(row.get("village"))
    claimed_person = villages.person(vid, row.get("claimed_member_id"))
    say_text = _say(
        say_key,
        claimed_name=claimed_name,
        pronoun=villages.pronoun(claimed_person) if claimed_person else "he",
        coordinator_name=_coord_name(vid),
        recipient_name=villages.first_name(vid, _recipient(vid), _rel(vid)),
    )
    out = {
        "id": f"dc_{row['id']}_{state or 'verification'}",
        "rule_id": "R-MONEY-DEFAULT",
        "decision": decision,
        "say": say_text,
        "say_key": say_key,
        "say_vars": say_vars,
        "verification": _decision_verification(row),
        "notify": [],
        "writes": [],
        "rules_fired": rules,
    }
    if state in {"denied", "late_denied"}:
        out["notify"] = [{"member_id": _coord(vid), "channel": "app", "severity": "high", "reason": "scam_stopped"}]
    return out


def _decision_verification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "claimed_member": row.get("claimed_member_id"),
        "deadline": row.get("deadline"),
        "channels": list(dict.fromkeys(
            channel.get("via", channel) if isinstance(channel, dict) else channel
            for channel in row.get("channels", [])
        )),
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
    normalized.setdefault("village", villages.member_village(normalized.get("claimed_member_id")))
    normalized.setdefault("subject", _recipient(normalized["village"]))
    normalized.setdefault("claimed_member_id", _verifier(normalized["village"]))
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


def _mode_for(decision: dict[str, Any]) -> str:
    """Kit autonomy chip (coordinator request; contract to follow): acted_alone | asked_human | refused."""
    kind = decision.get("decision", "")
    if kind in {"verify_with_member", "escalate_family", "ask_family", "advise_talk_to_coordinator"}:
        return "asked_human"
    if kind in {"refuse", "block", "refuse_advice", "advise_911_first"} or str(decision.get("rule_id", "")).startswith("R-MONEY-NEVER"):
        return "refused"
    return "acted_alone"


def _gate_decide(inp: dict[str, Any]) -> dict[str, Any]:
    try:
        from core.gate import decide as real_decide  # type: ignore
    except (ImportError, AttributeError):
        real_decide = fallback_decide
    return real_decide(inp)


def _village_state(village_id: str) -> dict[str, Any]:
    """GateInput.village_state from the village's live spec (D30: rules are parameters, read from the spec)."""
    spec = db.specs.get(village_id) or villages.fixture_spec(village_id)
    shift = next((ev for ev in reversed(db.events) if ev["kind"] == "shift" and ev.get("village", village_id) == village_id), None)
    today = clock.now().date().isoformat()
    rota = None
    if shift:
        rota = {
            "date": today,
            "on_duty": shift["payload"].get("on_duty") or villages.default_on_duty(village_id),
            "backup": shift["payload"].get("backup") or villages.default_backup(village_id),
        }
    state = villages.state_from_spec(
        spec,
        now=clock.now().isoformat(),
        rota_today=rota or {"date": today, "on_duty": villages.default_on_duty(village_id), "backup": villages.default_backup(village_id)},
        recent_money_requests=[
            {"event_id": ev["id"], "at": ev["at"]}
            for ev in db.events
            if ev["kind"] == "money_request" and ev.get("village", village_id) == village_id
        ],
    )
    state["village_id"] = village_id
    return state


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
        "verification_id": _next_id("ver", list(db.verifications.values())),
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
        "mode": _mode_for(decision),
        "refs": [],
        "source": candidate.get("source", {"kind": "system", "ref": "gate"}),
        "gate": copy.deepcopy(decision),
        "event_ids": [],
    }
    await db.create_decision(decision_row)
    public = {k: v for k, v in decision.items() if not k.startswith("_")}
    await control(village_id, "gate", {"decision": public, "input_kind": candidate.get("kind", "tick")})
    await reasoning(village_id, _reasoning_text(public, candidate), mode=_mode_for(public))
    # row exists before the ledger writes (bindings read it); its LIVE publish (-> prompt) waits until after them
    if decision.get("verification"):
        verification = decision["verification"]
        await db.upsert_verification({
            "id": verification["id"],
            "village": village_id,
            "subject": candidate.get("payload", {}).get("subject") or _recipient(village_id),
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
        }, publish=False)
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
    if decision.get("verification") and decision["verification"]["id"] in db.verifications:
        await db.publish("verification", db.verifications[decision["verification"]["id"]])
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
    if event["decision_id"] is None:
        del event["decision_id"]
    await db.create_event(event)
    return event


async def handle_tool(name: str, request: dict[str, Any]) -> dict[str, Any]:
    idem_key = None
    if request.get("conversation_id"):
        cached_probe = await db.get_idem(f"{request.get('conversation_id')}:{request.get('tool_call_id', name)}")
        if not (cached_probe and cached_probe.get("response")):
            village = _vid(request.get("village_id"))
            if request.get("utterance"):
                await caption(village, str(request["utterance"])[:300], speaker=_speaker(request))
    response = await _handle_tool(name, request)
    if request.get("conversation_id") and isinstance(response, dict):
        await ledger(
            _vid(request.get("village_id")),
            f"tool:{request.get('conversation_id')}:{request.get('tool_call_id', name)}",
            "done",
            f"Phone line · {name.replace('_', ' ')}",
            result=str(response.get("say_key") or response.get("decision") or "ok"),
            decision_id=response.get("decision_id"),
            role="Verifier" if "verification" in name or "money" in name else "Explainer",
        )
    return response


def _speaker(request: dict[str, Any]) -> str:
    caller = str(request.get("caller_id") or request.get("member_id") or "")
    vid = _vid(request.get("village_id"))
    for person in villages.people(vid):
        if caller and caller in {person["id"], person.get("phone")}:
            return villages.first_name(vid, person["id"]).lower() or "caller"
    if caller and any(caller in {mid, p.get("phone")} for mid, p in db.members.items()):
        return "caller"
    return villages.first_name(vid, _recipient(vid), "caller").lower()


async def _handle_tool(name: str, request: dict[str, Any]) -> dict[str, Any]:
    idem_key = None
    if request.get("conversation_id"):
        idem_key = f"{request.get('conversation_id')}:{request.get('tool_call_id', name)}"
        cached = await db.get_idem(idem_key)
        if cached and cached.get("response"):
            return copy.deepcopy(cached["response"])

    if name == "log_dose":
        village_id = _vid(request.get("village_id"))
        taken_at = request.get("taken_at") or clock.now().isoformat()
        candidate = {
            "village": village_id,
            "kind": "dose",
            "payload": {
                "subject": _recipient(village_id),
                "slot": request.get("slot") if request.get("slot") not in (None, "current") else "evening",
                "taken_at": taken_at,
                "confidence": "confirmed" if request.get("confidence") == "confirmed_by_caller" else "uncertain",
                "via": "phone_line",
            },
            "actor": _recipient(village_id),
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
        village_id = _vid(request.get("village_id"))
        deadline = (clock.now() + timedelta(seconds=45)).isoformat()
        claimed_member_id = _resolve_member(village_id, request.get("claimed_member"))
        candidate = {
            "village": village_id,
            "kind": "money_request",
            "payload": {
                "subject": _recipient(village_id),
                "claimed_member_id": claimed_member_id or _verifier(village_id),
                "claimed_identity": request.get("claimed_identity") or villages.first_name(village_id, claimed_member_id or _verifier(village_id)),
                "amount": request.get("amount", 0),
                "currency": request.get("currency", "USD"),
                "method": request.get("method", "unknown"),
                "urgency": request.get("urgency", "now"),
                "red_flags": request.get("red_flags", []),
                "utterance": request.get("utterance", ""),
                "deadline": deadline,
            },
            "actor": _recipient(village_id),
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

    if name == "screen_caller":
        from core.evolve.receptionist import screen_caller

        return await screen_caller(request, idem_key=idem_key)

    if name == "await_verification":
        result = await await_verification(request["verification_id"], max_wait_s=int(request.get("max_wait_s", 30)))
        row = db.verifications.get(request["verification_id"], {})
        decision_id = f"dc_{row.get('id')}_{row.get('state')}" if row.get("state") in TERMINAL_STATES else f"dc_{row.get('id')}_await"
        response = {
            "decision": result["decision"],
            "say": result["say"]["es"],
            "say_key": result["say_key"],
            "rule_id": "R-MONEY-DEFAULT",
            "lang": "es",
            "decision_id": decision_id,
            "data": {
                "status": result["status"],
                "verification_id": result["verification_id"],
                "state": result["state"],
                "answered_via": result["answered_via"],
                "answered_at_secs": int(result["answered_at_secs"]) if isinstance(result.get("answered_at_secs"), (int, float)) else None,
                "incident_id": result["incident_id"],
            },
        }
        if idem_key and result["state"] != "pending":
            await db.put_idem(idem_key, {"response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response

    if name == "submit_verification_answer":
        row = await answer_verification(
            request["verification_id"],
            request["verification_answer"],
            via=request.get("via") or "outbound_call",
            member_id=request.get("member_id") or db.verifications.get(request["verification_id"], {}).get("claimed_member_id"),
            quote=request.get("listener_quote"),
            call_sid=request.get("call_sid"),
        )
        response = {
            "decision": "allow",
            "say": "",
            "rule_id": "R-MONEY-VERIFY",
            "lang": "en",
            "data": {"status": row.get("status"), "state": row.get("state"), "outcome": row.get("outcome"), "verification_id": request["verification_id"]},
        }
        if idem_key:
            await db.put_idem(idem_key, {"response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response

    for example in _voice_examples():
        if example.get("tool") == name:
            response = copy.deepcopy(example["response"])
            if name == "log_dose":
                await record_event(
                    _vid(request.get("village_id")),
                    {
                        "kind": "dose",
                        "payload": {
                            "subject": _recipient(request.get("village_id")),
                            "slot": response.get("data", {}).get("slot", request.get("slot", "evening")),
                            "taken_at": response.get("data", {}).get("taken_at"),
                            "confidence": "confirmed",
                            "via": "phone_line",
                        },
                    },
                    actor=_recipient(request.get("village_id")),
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
    member_id = request.get("member_id") or _recipient(village_id)
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
        claimed = request.get("arg") or payload.get("claimed_member_id") or payload.get("claimed_member")
        claimed_member_id = _resolve_member(village_id, claimed) or _verifier(village_id)
        candidate = {
            "village": village_id,
            "kind": "money_request",
            "payload": {
                "origin": "start_verification",
                "subject": payload.get("subject") or _recipient(village_id),
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
    if name in {"approve_proposal", "reject_proposal"}:
        return await approve_proposal(village_id, name, request)
    if name == "ask_proposal_other":
        from core.proposal_ask import ask_other

        return await ask_other(village_id, request)
    raise KeyError(name)


async def approve_proposal(village_id: str, name: str, request: dict[str, Any]) -> dict[str, Any]:
    """Evolve seam: WS/app action approve_proposal | reject_proposal (leader only) -> core.evolve.proposals."""
    from core.evolve.proposals import handle_action as evolve_action

    return await evolve_action(village_id, name, request)


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
    row = db.verifications.get(verification["id"])
    if row and row.get("state") == "pending" and not row.get("call_placed_at"):
        from core.dialer import dial_in_background

        dial_in_background(verification["id"])
    return {
        "decision": decision,
        "status": "pending",
        "verification_id": verification["id"],
        "claimed_member_id": verification["claimed_member"],
        "channels": verification["channels"],
        "deadline": verification["deadline"],
    }


TERMINAL_STATES = {"confirmed", "denied", "timed_out", "unsure", "unreachable", "late_confirmed", "late_denied"}
_COUNTERS: dict[str, int] = {}


def _incident_text(row: dict[str, Any], incident_type: str) -> tuple[dict[str, str], dict[str, str]]:
    name = _claimed_name(row)
    rel_en, rel_es = _rel(row.get("village"), "en"), _rel(row.get("village"), "es")
    amount = row.get("request", {}).get("amount")
    amount_s = f"${amount:,.0f}" if isinstance(amount, (int, float)) and amount else "money"
    if incident_type == "suspected_scam":
        return (
            {"en": "Scam stopped", "es": "Estafa detenida"},
            {
                "en": f"Someone claiming to be {name} asked {rel_en} for {amount_s}. {name} confirmed it wasn't him. She was told not to send money.",
                "es": f"Alguien que dijo ser {name} le pidió {amount_s} a {rel_es}. {name} confirmó que no fue él. Le dijimos que no mande dinero.",
            },
        )
    return (
        {"en": "Money request not confirmed", "es": "Pedido de dinero sin confirmar"},
        {
            "en": f"Someone claiming to be {name} asked {rel_en} for {amount_s}. Village could not reach {name} in time. She was told not to send money.",
            "es": f"Alguien que dijo ser {name} le pidió {amount_s} a {rel_es}. Village no pudo confirmar con {name} a tiempo. Le dijimos que no mande dinero.",
        },
    )


def _enrich_incident(row: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    draft = copy.deepcopy(draft)
    payload = draft.setdefault("payload", {})
    title, summary = _incident_text(row, payload.get("type", "suspected_scam"))
    payload["title"] = title
    payload["summary"] = summary
    related = [
        ev["id"] for ev in db.events
        if ev.get("payload", {}).get("verification_id") == row["id"] and ev["kind"] != "incident"
    ]
    if related:
        payload["related_event_ids"] = related
    request = row.get("request", {})
    if request.get("pattern_flag"):
        payload["pattern_flag"] = request["pattern_flag"]
    payload["notified"] = [m for m in [_coord(row.get("village")), row.get("claimed_member_id")] if m]
    return draft


async def apply_verification_step(
    current: dict[str, Any],
    sm_event: dict[str, Any],
    *,
    actor: str,
    source: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Run one SM step, CAS-persist it, write its emits (incident enriched), and publish the terminal decision."""
    current = _normalize_verification(current)
    next_row, emits = step_verification(current, sm_event, clock.now())
    if sm_event.get("type") == "answer":
        next_row = _with_channel_status(next_row, sm_event.get("via", "app_prompt"), sm_event.get("member_id", actor), "answered")
        if sm_event.get("call_sid") and next_row.get("answers"):
            next_row["answers"][-1]["call_sid"] = sm_event["call_sid"]
    if next_row == current:
        return current, []
    was_terminal = current.get("state") in TERMINAL_STATES
    becomes_terminal = next_row.get("state") in TERMINAL_STATES
    decision = _decision_for_verification(next_row) if becomes_terminal and not was_terminal else None
    if decision:
        next_row["status"] = _verification_status_for_voice(next_row)
        next_row["resolved_at"] = next_row.get("resolved_at") or clock.now().isoformat()
    if any(d["kind"] == "incident" for d in emits):
        next_row["incident_id"] = next_row.get("incident_id") or f"inc_{current['id']}"
    updated = await db.cas_update("verification", current["id"], current.get("version", 0), next_row)
    if not updated:
        return None, []
    row = updated[0]
    village = _vid(row.get("village"))
    written = []
    for draft in emits:
        if draft["kind"] == "incident":
            draft = _enrich_incident(row, draft)
        if decision:
            decision["writes"].append({"kind": draft["kind"], "payload": draft.get("payload", {})})
        event_actor = actor if draft["kind"].startswith("verification_") else "gate"
        event_source = source if draft["kind"].startswith("verification_") else {"kind": "system", "ref": "gate"}
        written.append(await record_event(village, draft, actor=event_actor, source=event_source, decision_id=decision["id"] if decision else None))
    if decision:
        verification_event = next((ev for ev in written if ev["kind"].startswith("verification_")), written[0] if written else None)
        await db.create_decision({
            "id": decision["id"],
            "village_id": village,
            "at": clock.now().isoformat(),
            "actor": "gate",
            "kind": "decision",
            "text": decision["decision"],
            "rule_id": decision["rule_id"],
            "mode": _mode_for(decision),
            "refs": [{"kind": "verification", "id": row["id"]}],
            "source": source,
            "gate": copy.deepcopy(decision),
            "event_ids": [ev["id"] for ev in written],
        })
        gate_payload = {
            "decision": decision,
            "input_kind": "verification_answer" if sm_event.get("type") == "answer" else ("await_returned" if sm_event.get("type") == "await_returned" else "tick"),
        }
        if verification_event:
            gate_payload["event_id"] = verification_event["id"]
        await control(village, "gate", gate_payload)
        await reasoning(village, _terminal_reasoning(row), mode=_mode_for(decision))
        await ledger(village, f"ver:{row['id']}", "done", f"Verify money request with {_claimed_name(row)}", result=row.get("state"), decision_id=decision["id"], role="Verifier")
        if row.get("state") in {"denied", "late_denied", "timed_out"}:
            from core.bindings import scams_stopped_today

            # per village, today's denied/timed-out verifications (ws_hub re-sends it on every connect)
            _COUNTERS["scams_stopped"] = scams_stopped_today(village)
            await control(village, "counter", {"name": "scams_stopped", "value": _COUNTERS["scams_stopped"], "label": "scams stopped today"})
        _evolve_port(village, row)
    for ev in written:
        if ev["kind"] == "incident":
            await _incident_message(village, ev)
    return row, written


def _evolve_port(village_id: str, row: dict[str, Any]) -> None:
    """Watcher trigger port (evolve lane): a money verification resolved -> maybe propose (background, never raises)."""
    try:
        from core.evolve.trigger import on_verification_resolved
    except ImportError:
        return
    on_verification_resolved(village_id, row)


async def _incident_message(village_id: str, event: dict[str, Any]) -> None:
    hook = globals().get("post_incident_message")
    if hook:
        await hook(village_id, event)


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
    sm_event = {"type": "answer", "answer": answer, "via": via, "member_id": member_id, "quote": quote, "call_sid": call_sid}
    row, _ = await apply_verification_step(
        current,
        sm_event,
        actor=member_id,
        source={"kind": "app" if via == "app_prompt" else "call", "ref": member_id},
    )
    if row is None:
        return {**db.verifications[verification_id], "outcome": "conflict"}
    outcome = (row.get("answers") or [{}])[-1].get("outcome", "applied")
    return {**row, "outcome": outcome}


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
        stepped, _ = await apply_verification_step(
            row, {"type": "await_returned"}, actor="gate", source={"kind": "system", "ref": "await_verification"}
        )
        row = stepped or db.verifications[verification_id]

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


def _reasoning_text(decision: dict[str, Any], candidate: dict[str, Any]) -> str:
    verification = decision.get("verification")
    if verification:
        name = str(db.members.get(verification.get("claimed_member", ""), {}).get("name", "the family member")).split()[0]
        by = " and phone" if "outbound_call" in verification.get("channels", []) else ""
        consent = " (he consented)" if by else ""
        recipient = villages.first_name(candidate.get("village"), _recipient(candidate.get("village")), "the caller")
        return f"Money request in {name}'s name → check with the real {name} by app{by}{consent} → hold {recipient} on the line."
    say_en = (decision.get("say") or {}).get("en", "")
    text = f"{candidate.get('kind', 'input')} → {decision.get('rule_id')}: {decision.get('decision')}"
    return f"{text} · “{say_en}”"[:400] if say_en else text[:400]


def _terminal_reasoning(row: dict[str, Any]) -> str:
    name = _claimed_name(row)
    state = row.get("state")
    vid = row.get("village")
    rel, coord = _rel(vid), _coord_name(vid)
    if state in {"denied", "late_denied"}:
        return f"{name} said it wasn't him → tell {rel} not to send any money → incident to {coord}."
    if state in {"confirmed", "late_confirmed"}:
        return f"{name} confirmed it was him → Village still never sends money → {rel} talks to {coord} first."
    return f"No answer from {name} by the deadline → default is don't send → incident to {coord}."


async def reasoning(village_id: str, text: str, *, source: str = "gate", kind: str = "decision", mode: str | None = None) -> None:
    payload: dict[str, Any] = {"source": source, "kind": kind, "text": text[:400], "village": village_id}
    if mode:
        payload["mode"] = mode
    await control(village_id, "reasoning", payload)


async def ledger(village_id: str, row_id: str, status: str, what: str, *, result: str | None = None,
                 decision_id: str | None = None, role: str = "Verifier") -> None:
    """Control Room work log row (kit V2; contract to follow): {id, status, what, result?, decision_id?, role, time}."""
    payload: dict[str, Any] = {"id": row_id, "at": clock.now().isoformat(), "status": status, "what": what, "role": role.lower()}
    if result is not None:
        payload["result"] = result
    if decision_id:
        payload["decision_id"] = decision_id
    await control(village_id, "ledger", payload)


async def caption(village_id: str, es: str, en: str = "", *, speaker: str | None = None) -> None:
    payload: dict[str, Any] = {"es": es, "en": en}
    if speaker:
        payload["speaker"] = speaker
    await control(village_id, "caption", payload)


async def control(village_id: str, kind: str, payload: dict[str, Any]) -> None:
    await broadcast(village_id, {"type": "control", "kind": kind, "payload": payload}, to="control")
    # through the LIVE queue (not straight to the hub) so control frames keep ledger order with event frames
    from core.live import live_status

    if live_status.status == "ok":
        await db.publish("control", {"village": village_id, "kind": kind, "payload": payload})
    else:
        await hub.control(village_id, kind, payload)


_CHAT_TASKS: set[asyncio.Task[Any]] = set()
_NUDGED: set[str] = set()
_INCIDENT_POSTED: set[str] = set()
ASK_FALLBACK_TEXT = "I can't look that up right now. Every decision Village made is in the decision log; the coordinator can open it from the app."


def _message_id() -> str:
    return f"msg_{clock.now():%m%d_%H%M}_{len(db.messages) + 1:03d}"


async def post_message(
    village_id: str,
    *,
    author: str,
    kind: str,
    text: str,
    refs: tuple[Any, ...] | list[Any] = (),
    source: dict[str, Any],
    text_i18n: dict[str, str] | None = None,
    mention: str | None = None,
    reply_to: str | None = None,
    routed: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Append one chat row; the LIVE consumer fans it out as `chat{message}` (non-elder sockets + control)."""
    message: dict[str, Any] = {
        "id": _message_id(),
        "village": village_id,
        "author": author,
        "kind": kind,
        "text": text[:2000],
        "mention": mention,
        "reply_to": reply_to,
        "refs": [ref if isinstance(ref, dict) else _ref_for_id(str(ref)) for ref in refs][:12],
        "source": source,
        "at": (await now()).isoformat(),
    }
    if text_i18n:
        message["text_i18n"] = text_i18n
    if routed:
        message["routed"] = routed
    if trace_id:
        message["trace_id"] = trace_id
    _MESSAGE_LOG.append(message)
    await db.create_message(message)
    return message


def _ref_for_id(ref_id: str) -> dict[str, str]:
    prefix = ref_id.split("_", 1)[0]
    kind = {"ev": "event", "dc": "decision", "ver": "verification", "inc": "incident", "prop": "proposal", "rel": "release", "m": "member"}.get(prefix, "rule")
    return {"kind": kind, "id": ref_id}


async def post_member_message(
    village_id: str,
    member_id: str,
    text: str,
    *,
    mention: str | None = None,
    reply_to: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    idem = f"chat:{member_id}:{idempotency_key}" if idempotency_key else None
    if idem:
        cached = await db.get_idem(idem)
        if cached and cached.get("response"):
            return copy.deepcopy(cached["response"])
    addresses_village = mention == "village" or text.lstrip().lower().startswith("@village")
    routed = "ask" if addresses_village else "none"
    message = await post_message(
        village_id,
        author=member_id,
        kind="chat",
        text=text,
        refs=[],
        source={"kind": "app", "ref": member_id},
        mention="village" if addresses_village else None,
        reply_to=reply_to,
        routed=routed,
    )
    if addresses_village:
        task = asyncio.get_running_loop().create_task(_answer_village_question(village_id, message))
        _CHAT_TASKS.add(task)
        task.add_done_callback(_CHAT_TASKS.discard)
    result = {"message": message, "routed": routed}
    if idem:
        await db.put_idem(idem, {"response": copy.deepcopy(result), "at": clock.now().isoformat()})
    return result


async def drain_chat() -> None:
    while _CHAT_TASKS:
        await asyncio.gather(*list(_CHAT_TASKS), return_exceptions=True)


def _fallback_refs(village_id: str) -> list[dict[str, str]]:
    rows = [row for row in db.decisions if row.get("village_id", village_id) == village_id]
    refs = [{"kind": "decision", "id": row["id"], "label": f"rule {row.get('rule_id', '')}"[:80]} for row in rows[-2:]]
    return refs or [{"kind": "rule", "id": "R-MONEY-VERIFY", "label": "rule R-MONEY-VERIFY"}]


async def _answer_village_question(village_id: str, question: dict[str, Any]) -> dict[str, Any]:
    text = question["text"]
    stripped = text.lstrip()
    question_text = stripped[len("@village"):].strip(" ,:") if stripped.lower().startswith("@village") else stripped
    answer_text: str | None = None
    refs: list[Any] = []
    trace_id = None
    try:
        from core.builder import ask as builder_ask  # type: ignore

        result = builder_ask(village_id, question_text)
        if asyncio.iscoroutine(result):
            result = await asyncio.wait_for(result, timeout=20)
        if isinstance(result, str):
            answer_text = result
        elif isinstance(result, dict):
            answer_text = result.get("text") or result.get("answer")
            refs = result.get("refs") or []
            trace_id = result.get("trace_id")
    except Exception:
        answer_text = None
    if not answer_text:
        answer_text = ASK_FALLBACK_TEXT
    if not refs:
        refs = _fallback_refs(village_id)
    return await post_message(
        village_id,
        author="village",
        kind="answer",
        text=answer_text,
        refs=refs,
        source={"kind": "system", "ref": "builder"},
        reply_to=question["id"],
        trace_id=trace_id if isinstance(trace_id, str) and len(trace_id) == 32 else None,
    )


async def post_incident_message(village_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
    payload = event.get("payload", {})
    incident_id = payload.get("incident_id")
    if not incident_id or incident_id in _INCIDENT_POSTED:
        return None
    _INCIDENT_POSTED.add(incident_id)
    verification_id = payload.get("verification_id")
    row = db.verifications.get(verification_id or "", {})
    name = _claimed_name(row) if row else villages.first_name(village_id, _verifier(village_id), "a family member")
    rel_en, rel_es = _rel(village_id, "en"), _rel(village_id, "es")
    amount = row.get("request", {}).get("amount") if row else None
    amount_s = f"${amount:,.0f}" if isinstance(amount, (int, float)) and amount else "money"
    if payload.get("type") == "suspected_scam":
        en = f"Someone called {rel_en} as {name}, asking for {amount_s}. I asked {name}; he said it wasn’t him. I told her not to send money. Nothing was sent."
        es = f"Alguien llamó a {rel_es} diciendo ser {name} y pidió {amount_s}. Le pregunté a {name}; dijo que no fue él. Le dije a ella que no mande dinero. No se envió nada."
    else:
        en = f"Someone called {rel_en} as {name}, asking for {amount_s}. I couldn’t reach {name} in time, so I told her not to send money."
        es = f"Alguien llamó a {rel_es} diciendo ser {name} y pidió {amount_s}. No pude confirmar con {name} a tiempo; le dije a ella que no mande dinero."
    refs: list[dict[str, str]] = [{"kind": "event", "id": event["id"], "label": "incident"}]
    if verification_id:
        refs.append({"kind": "verification", "id": verification_id, "label": f"{name} answered" if payload.get("type") == "suspected_scam" else "check"})
    refs.append({"kind": "incident", "id": incident_id, "label": "why"})
    return await post_message(
        village_id,
        author="village",
        kind="incident",
        text=en,
        text_i18n={"en": en, "es": es},
        refs=refs,
        source={"kind": "system", "ref": "gate"},
    )


async def rota_nudge_tick(village_id: str | None = None) -> int:
    """At/after 15:00 local, post one nudge per day to the on-duty member, citing the shift row."""
    village_id = _vid(village_id)
    now_dt = clock.now()
    if now_dt.hour < 15:
        return 0
    key = f"{village_id}:{now_dt.date().isoformat()}"
    if key in _NUDGED:
        return 0
    shift = next((ev for ev in reversed(db.events) if ev["kind"] == "shift" and ev.get("village", village_id) == village_id), None)
    if shift is None:
        return 0
    _NUDGED.add(key)
    on_duty = shift["payload"].get("on_duty") or villages.default_on_duty(village_id)
    rel_en, rel_es = _rel(village_id, "en"), _rel(village_id, "es")
    name = str(db.members.get(on_duty, {}).get("name", on_duty)).split()[0]
    await post_message(
        village_id,
        author="village",
        kind="nudge",
        text=f"{name}, you're on tonight. Evening pills are at 8:00; I'll call {rel_en} and let you know.",
        text_i18n={
            "en": f"{name}, you're on tonight. Evening pills are at 8:00; I'll call {rel_en} and let you know.",
            "es": f"{name}, hoy te toca. Las pastillas de la noche son a las 8:00; yo llamo a {rel_es} y te aviso.",
        },
        refs=[{"kind": "event", "id": shift["id"], "label": "tonight's rota"}],
        source={"kind": "system", "ref": "scheduler"},
    )
    return 1


def reset_chat_state() -> None:
    _NUDGED.clear()
    _INCIDENT_POSTED.clear()
    _COUNTERS.clear()
    _MESSAGE_LOG.clear()
    _BROADCAST_LOG.clear()


def stub_logs() -> dict[str, Any]:
    return {"broadcasts": copy.deepcopy(_BROADCAST_LOG), "messages": copy.deepcopy(_MESSAGE_LOG)}


async def handle_ack(village_id: str, member_id: str | None, frame: dict[str, Any]) -> dict[str, Any]:
    """WS `ack{event_id, status}`: writes an ack ledger row (closes the incident banner for everyone)."""
    of_event = next((ev for ev in db.events if ev["id"] == frame.get("event_id")), None)
    payload: dict[str, Any] = {"of_event_id": frame.get("event_id"), "status": frame.get("status", "got_it"), "channel": "app"}
    if of_event and of_event.get("payload", {}).get("incident_id"):
        payload["incident_id"] = of_event["payload"]["incident_id"]
    event = await record_event(
        village_id,
        {"kind": "ack", "payload": payload},
        actor=member_id or "control",
        source={"kind": "app", "ref": member_id or "control"},
        decision_id=None,
    )
    return {"type": "result", "req_id": frame.get("req_id") or f"ack_{event['id']}", "ok": of_event is not None, "event_id": event["id"]}


async def handle_voice_tool(tool_name: str, body: dict[str, Any], variant: str | None = None) -> dict[str, Any]:
    """Entry point for core.voice.tools.ToolHandler: every voice tool goes through the real services."""
    del variant
    return await handle_tool(tool_name, body)
