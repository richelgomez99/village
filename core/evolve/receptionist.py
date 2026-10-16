"""Receptionist mode, Core side (D19): voice tool `screen_caller`.

When the village spec has receptionist mode on (policies[R-MONEY-UNKNOWN].params.receptionist_mode), the
mom-line agent answers unknown callers first and calls `screen_caller`:

  phase "screen" (no verification_id): known caller id + family word -> pass_through. A caller claiming to be a
    family member (or asking for money) -> the pure gate (R-MONEY-VERIFY / R-MONEY-UNKNOWN) through the normal
    start_verification path (app prompt + outbound call to the REAL member's number on file) -> status held.
  phase "await" (verification_id given): waits for the real member (<= 30 s) -> denied: "Marco says this isn't
    him. I won't put you through." / confirmed: put through (money still never moves) / no answer: refuse.

Spoken lines are English for the caller (captions); names and pronouns come from the village spec (D30).
"""
from __future__ import annotations

import copy
import re
from datetime import timedelta
from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db

MONEY_RE = re.compile(r"dinero|money|\$|dólares|dollars|tarjeta|gift card|transfer|wire|bitcoin|crypto|pagar|pay|bail|fianza", re.I)
_OBJ = {"he": "him", "she": "her", "they": "them"}
_POSS = {"he": "his", "she": "her", "they": "their"}


def _norm(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def _known_person(village_id: str, caller_id: str | None) -> dict[str, Any] | None:
    if not caller_id:
        return None
    return next((p for p in villages.people(village_id) if caller_id in {p.get("phone"), p.get("id")}), None)


def _resp(decision: str, say: str, rule: str, status: str, *, decision_id: str | None = None, **data: Any) -> dict[str, Any]:
    out = {"decision": decision, "say": say, "say_key": f"screen_{status}", "rule_id": rule, "lang": "en",
           "data": {"status": status, **{k: v for k, v in data.items() if v is not None}}}
    if decision_id:
        out["decision_id"] = decision_id
    return out


async def screen_caller(request: dict[str, Any], *, idem_key: str | None = None) -> dict[str, Any]:
    from core import services

    vid = request.get("village_id") or villages.default_village_id()
    key = f"{idem_key or request.get('conversation_id', 'conv_screen')}:screen" + (":await" if request.get("verification_id") else "")
    cached = await db.get_idem(key)
    if cached and cached.get("response"):
        return copy.deepcopy(cached["response"])
    recipient_id = villages.care_recipient_id(vid)
    recipient = villages.first_name(vid, recipient_id, "them")

    if request.get("verification_id"):
        response = await _await(vid, request, recipient)
        if response["data"]["status"] != "held":
            await db.put_idem(key, {"response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response

    if not villages.receptionist_mode(vid):
        return _resp("allow", "", "R-NOOP", "receptionist_off", next="connect")

    utterance = str(request.get("utterance") or "")
    claimed_raw = request.get("claimed_identity") or request.get("claimed_member")
    claimed_id = services._resolve_member(vid, claimed_raw) if claimed_raw else None
    known = _known_person(vid, request.get("caller_id"))
    word = villages.family_word(vid)
    said_word = bool(word and not word.startswith("[") and _norm(word) in _norm(utterance))

    if known and said_word and known.get("id") != recipient_id and not MONEY_RE.search(utterance):
        name = villages.first_name(vid, known["id"])
        response = _resp("allow", f"Thanks, {name}. Putting you through to {recipient}.", "R-MONEY-UNKNOWN", "pass_through",
                         member_id=known["id"], next="connect")
        await services.ledger(vid, f"screen:{request.get('conversation_id')}", "done", "Receptionist · known caller",
                              result=f"{name}: caller id + family word; put through", role="Verifier")
        await db.put_idem(key, {"response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response

    if not claimed_id and not MONEY_RE.search(utterance) and not claimed_raw:
        return _resp("allow", f"Thanks. What is this about? {recipient} asked me to take a message for callers I don't know.",
                     "R-MONEY-UNKNOWN", "ask_purpose", next="screen_caller")

    candidate = {
        "village": vid, "kind": "money_request",
        "payload": {
            "origin": "screen_caller", "subject": recipient_id,
            "claimed_member_id": claimed_id,
            "claimed_identity": str(claimed_raw or "unknown caller")[:80],
            "amount": request.get("amount", 0), "currency": request.get("currency", "USD"),
            "method": request.get("method", "unknown"), "urgency": request.get("urgency", "now"),
            "red_flags": sorted(set(list(request.get("red_flags") or []) + (["claimed_family_member", "new_number"] if claimed_id else ["new_number"]))),
            "utterance": utterance, "deadline": (clock.now() + timedelta(seconds=45)).isoformat(),
        },
        "actor": recipient_id,
        "source": {"kind": "call", "ref": request.get("conversation_id", "conv_screen"), "secs": int(float(request.get("call_secs") or 0)), "quote": utterance},
        "at": clock.now().isoformat(),
    }
    if not claimed_id:
        candidate["payload"].pop("claimed_member_id")
    result = await services.start_verification(vid, candidate, idempotency_key=key + ":gate")
    decision = result["decision"]
    if result.get("status") != "pending":
        response = _resp("refuse", f"I can't confirm who you are, so I won't put you through to {recipient}. Goodbye.",
                         decision.get("rule_id", "R-MONEY-UNKNOWN"), "refused", decision_id=decision.get("id"), next="end_call")
        await db.put_idem(key, {"response": copy.deepcopy(response), "at": clock.now().isoformat()})
        return response
    name = villages.first_name(vid, result["claimed_member_id"])
    response = _resp("verify_with_member", f"Thanks. I'm checking with {name} now on {_POSS.get(villages.pronoun(villages.person(vid, result['claimed_member_id'])), 'their')} own phone. Please hold.",
                     decision.get("rule_id", "R-MONEY-VERIFY"), "held", decision_id=decision.get("id"),
                     verification_id=result["verification_id"], claimed_member_id=result["claimed_member_id"],
                     deadline=result.get("deadline"), next="screen_caller")
    await services.ledger(vid, f"screen:{request.get('conversation_id')}", "running", "Receptionist · unknown caller held",
                          result=f"claims to be {name}; checking with the real {name}", decision_id=decision.get("id"), role="Verifier")
    await db.put_idem(key, {"response": copy.deepcopy(response), "at": clock.now().isoformat()})
    return response


async def _await(vid: str, request: dict[str, Any], recipient: str) -> dict[str, Any]:
    from core import services

    vid_ = request["verification_id"]
    out = await services.await_verification(vid_, max_wait_s=int(request.get("max_wait_s", 30)))
    row = db.verifications.get(vid_, {})
    claimed = row.get("claimed_member_id")
    name = villages.first_name(vid, claimed, "they")
    obj = _OBJ.get(villages.pronoun(villages.person(vid, claimed)), "them")
    state = out.get("state")
    data = {"verification_id": vid_, "state": state, "answered_via": out.get("answered_via"), "incident_id": out.get("incident_id")}
    if state in {"denied", "late_denied"}:
        say, status, decision, nxt = f"{name} says this isn't {obj}. I won't put you through.", "refused", "refuse", "end_call"
    elif state in {"confirmed", "late_confirmed"}:
        say, status, decision, nxt = (f"{name} confirmed it's {obj}. Putting you through to {recipient}. Village never sends money.",
                                      "pass_through", "allow", "connect")
    elif state == "pending":
        say, status, decision, nxt = f"Still checking with {name}. Please hold.", "held", "verify_with_member", "screen_caller"
    else:
        say, status, decision, nxt = (f"I couldn't reach {name}, so I won't put you through. If this is really family, call back from a number we know.",
                                      "refused", "refuse", "end_call")
    await services.ledger(vid, f"screen:{request.get('conversation_id')}", "done" if status != "held" else "running",
                          "Receptionist · unknown caller", result=f"{state}: {say}"[:400], role="Verifier")
    if status != "held":
        await services.caption(vid, "", say, speaker="village")
    return _resp(decision, say, "R-MONEY-VERIFY" if status != "pass_through" else "R-MONEY-DEFAULT", status,
                 decision_id=f"dc_{vid_}_{state}", next=nxt, **data)
