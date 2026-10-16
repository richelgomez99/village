from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.settings import ROOT


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
    return datetime.now().astimezone()


async def decide(
    village_id: str,
    candidate: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    actor_token: str | None = None,
) -> dict[str, Any]:
    """Stub gate seam: return the matching contract example decision."""
    del village_id, idempotency_key, actor_token
    kind = candidate.get("kind")
    for example in _gate_examples():
        if example.get("input", {}).get("event", {}).get("kind") == kind:
            return copy.deepcopy(example["decision"])
    return {
        "id": candidate.get("alloc", {}).get("decision_id", "dc_stub"),
        "rule_id": "R-NOOP",
        "decision": "allow",
        "say": {"es": "", "en": ""},
        "notify": [],
        "writes": [],
        "flags": [],
        "rules_fired": ["R-NOOP"],
    }


async def record_event(
    village_id: str,
    draft: dict[str, Any],
    *,
    actor: str,
    source: dict[str, Any],
    decision_id: str | None = None,
) -> dict[str, Any]:
    event = {
        "id": draft.get("id", f"ev_stub_{len(_BROADCAST_LOG) + 1}"),
        "village": village_id,
        "kind": draft["kind"],
        "payload": draft.get("payload", {}),
        "actor": actor,
        "source": source,
        "decision_id": decision_id,
        "at": (await now()).isoformat(),
    }
    await broadcast(village_id, {"type": "event", "event": event, "data": {}})
    return event


async def handle_tool(name: str, request: dict[str, Any]) -> dict[str, Any]:
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


async def start_verification(
    village_id: str,
    candidate: dict[str, Any],
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    del village_id, candidate, idempotency_key
    for example in _voice_examples():
        if example.get("tool") == "report_money_request":
            return copy.deepcopy(example["response"]["data"])
    return {"status": "unverifiable"}


async def answer_verification(
    verification_id: str,
    answer: str,
    *,
    via: str,
    member_id: str,
    quote: str | None = None,
    call_sid: str | None = None,
) -> dict[str, Any]:
    return {
        "id": verification_id,
        "status": "denied" if answer == "no" else "confirmed" if answer == "yes" else "timeout",
        "state": "denied" if answer == "no" else "confirmed" if answer == "yes" else "unsure",
        "answers": [{"answer": answer, "via": via, "member_id": member_id, "quote": quote, "call_sid": call_sid}],
    }


async def await_verification(verification_id: str, *, max_wait_s: int = 30) -> dict[str, Any]:
    del max_wait_s
    return {
        "verification_id": verification_id,
        "decision": "advise_do_not_send",
        "say_key": "money_timeout",
        "status": "timeout",
        "state": "default_spoken",
        "incident_id": f"inc_{verification_id}",
    }


async def broadcast(village_id: str, msg: dict[str, Any], *, to: str = "all") -> None:
    _BROADCAST_LOG.append({"village_id": village_id, "to": to, "msg": copy.deepcopy(msg)})


async def control(village_id: str, kind: str, payload: dict[str, Any]) -> None:
    await broadcast(village_id, {"type": "control", "kind": kind, "payload": payload}, to="control")


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
