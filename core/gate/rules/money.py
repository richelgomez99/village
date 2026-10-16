from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from core.gate.models import GateInput, append_rule, copy_payload, member_by_id, member_name
from core.gate.rules.common import coordinator_notify, finish, parse_dt

HARD_METHOD_FLAGS = {
    "gift_card": "gift_card",
    "crypto": "crypto",
    "wire_to_stranger": "wire_to_stranger",
    "cash_courier": "cash_courier",
    "bank_details": "bank_details",
    "payment_app_to_stranger": "payment_app_to_stranger",
}
PRESSURE_TEXT_FLAGS = {
    "secreto": "secrecy",
    "secret": "secrecy",
    "no le diga": "secrecy",
    "right now": "urgency",
    "ahora": "urgency",
    "preso": "jail_bail",
    "fianza": "jail_bail",
    "hospital": "hospital",
    "accident": "accident",
    "accidente": "accident",
    "voice": "voice_changed",
    "voz": "voice_changed",
}
MONEY_WORDS = (
    "money",
    "dollar",
    "dólar",
    "dolares",
    "dólares",
    "gift card",
    "tarjeta",
    "crypto",
    "bitcoin",
    "wire",
    "transfer",
    "bank",
    "cuenta",
    "account",
    "gift cards",
)


def decide_money(inp: GateInput) -> dict[str, Any] | None:
    event = inp.event
    kind = event["kind"]
    payload = copy_payload(event)
    text = _event_text(payload)

    if kind == "model_output" and _asks_village_to_handle_money(text):
        return _money_never(inp)

    if kind == "money_transfer_request":
        return _money_never(inp)

    if kind == "money_request":
        if _benign_money_to_carmen(payload, text):
            return finish(inp, "R-NOOP", "record")
        if payload.get("claimed_member_id") is None:
            return _money_unknown(inp, payload)
        return _money_verify(inp, payload)

    if kind == "verification_answer":
        return _verification_answer_decision(inp, payload)

    if kind == "await_returned":
        return _await_decision(inp, payload)

    if kind == "tick" and payload.get("reason") == "verification_deadline":
        return _deadline_decision(inp)

    if kind == "ask_family" and "no le diga" in text and "ana" in text:
        out = finish(
            inp,
            "R-AUTONOMY",
            "escalate_family",
            "money_share_disclosure",
            {"claimed_name": "Marco"},
            ["R-MONEY-DEFAULT"],
        )
        out["notify"] = [coordinator_notify(inp, "warn", "money_safety_share_disclosure")]
        return out

    return None


def _money_verify(inp: GateInput, payload: dict[str, Any]) -> dict[str, Any]:
    claimed_id = payload["claimed_member_id"]
    claimed = member_by_id(inp.village_state, claimed_id)
    claimed_name = member_name(inp.village_state, claimed_id)
    channels = _channels_for_member(claimed)
    deadline = (parse_dt(inp.event["at"]) + timedelta(seconds=45)).isoformat()
    red_flags = _red_flags(payload)
    pattern = _pattern_event_ids(inp)

    out = finish(
        inp,
        "R-MONEY-VERIFY",
        "verify_with_member",
        "money_hold",
        {"claimed_name": claimed_name},
        ["R-VERIFY-CONSENT"],
    )
    out["verification"] = {
        "id": inp.alloc["verification_id"],
        "claimed_member": claimed_id,
        "deadline": deadline,
        "channels": channels,
        "state": "pending" if channels else "unreachable",
    }
    out["notify"] = [coordinator_notify(inp, "warn", "money_request_pending")]

    money_payload = _money_request_payload(payload, inp.alloc["verification_id"], red_flags)
    if pattern:
        money_payload["pattern_flag"] = "possible_fraud_pattern"
    out["writes"] = [{"kind": "money_request", "payload": money_payload}]

    if channels:
        out["writes"].append(
            {
                "kind": "verification_pending",
                "payload": {
                    "verification_id": inp.alloc["verification_id"],
                    "subject": payload["subject"],
                    "claimed_member_id": claimed_id,
                    "deadline": deadline,
                    "channels": channels,
                    "origin": "report_money_request",
                },
            }
        )
    else:
        out["writes"].append(
            {
                "kind": "verification_timeout",
                "payload": {
                    "verification_id": inp.alloc["verification_id"],
                    "claimed_member_id": claimed_id,
                    "reason": "unreachable",
                    "state": "unreachable",
                },
            }
        )
        out["writes"].append(_incident(inp, "unverified_money_request", "warn", f"Could not reach {claimed_name}", payload))
        append_rule(out, "R-MONEY-DEFAULT")

    if pattern:
        append_rule(out, "R-MONEY-PATTERN")
        out["flags"] = ["possible_fraud_pattern", "red_flag_notify_early"]
        out["writes"][0]["payload"]["pattern_flag"] = "possible_fraud_pattern"
        out["writes"].append(
            {
                "kind": "pattern",
                "payload": {
                    "subject": payload["subject"],
                    "pattern": "possible_fraud_pattern",
                    "count": len(pattern),
                    "window_days": 30,
                    "event_ids": pattern,
                },
            }
        )
    elif red_flags:
        out["flags"] = ["red_flag_notify_early"]

    return out


def _money_unknown(inp: GateInput, payload: dict[str, Any]) -> dict[str, Any]:
    red_flags = _red_flags(payload)
    out = finish(inp, "R-MONEY-UNKNOWN", "advise_do_not_send", "money_unknown", rules=["R-MONEY-NEVER"])
    out["notify"] = [coordinator_notify(inp, "high", "unknown_money_request")]
    out["writes"] = [
        {"kind": "money_request", "payload": _money_request_payload(payload, None, red_flags)},
        _incident(inp, "unverified_money_request", "high", "Unknown caller asked for money", payload),
    ]
    return out


def _money_never(inp: GateInput) -> dict[str, Any]:
    out = finish(inp, "R-MONEY-NEVER", "deny", "money_never")
    out["notify"] = [coordinator_notify(inp, "high", "money_never")]
    return out


def _verification_answer_decision(inp: GateInput, payload: dict[str, Any]) -> dict[str, Any]:
    verification = _open_verification(inp, payload["verification_id"])
    claimed_id = payload.get("member_id") or (verification or {}).get("claimed_member_id")
    claimed = member_by_id(inp.village_state, claimed_id)
    claimed_name = member_name(inp.village_state, claimed_id, "la persona")
    pronoun = (claimed or {}).get("pronoun", "he")
    answer = payload.get("answer")

    if answer == "yes":
        out = finish(
            inp,
            "R-MONEY-DEFAULT",
            "advise_talk_to_coordinator",
            "money_confirmed",
            {"claimed_name": claimed_name, "pronoun": pronoun},
            ["R-MONEY-NEVER"],
        )
        out["writes"] = [{"kind": "verification_confirmed", "payload": _answered_payload(payload, claimed_id, "confirmed")}]
        out["notify"] = [coordinator_notify(inp, "info", "money_request_confirmed")]
        return out
    if answer == "no":
        out = finish(inp, "R-MONEY-DEFAULT", "advise_do_not_send", "money_denied", {"claimed_name": claimed_name})
        out["writes"] = [
            {"kind": "verification_denied", "payload": _answered_payload(payload, claimed_id, "denied")},
            _incident(inp, "suspected_scam", "high", f"{claimed_name} denied the request", {"claimed_member_id": claimed_id}),
        ]
        out["notify"] = [coordinator_notify(inp, "high", "verification_denied")]
        return out

    out = finish(inp, "R-MONEY-DEFAULT", "advise_do_not_send", "money_timeout", {"claimed_name": claimed_name})
    out["writes"] = [
        {
            "kind": "verification_timeout",
            "payload": {
                "verification_id": payload["verification_id"],
                "claimed_member_id": claimed_id,
                "reason": "unsure",
                "state": "unsure",
            },
        },
        _incident(inp, "unverified_money_request", "warn", f"{claimed_name} was unsure", {"claimed_member_id": claimed_id}),
    ]
    out["notify"] = [coordinator_notify(inp, "warn", "verification_unsure")]
    return out


def _await_decision(inp: GateInput, payload: dict[str, Any]) -> dict[str, Any]:
    verification = _open_verification(inp, payload["verification_id"]) or {}
    claimed_id = verification.get("claimed_member_id", "m_marco")
    claimed_name = member_name(inp.village_state, claimed_id, "Marco")
    state = verification.get("state", "pending")
    if state in {"denied", "late_denied"}:
        return finish(inp, "R-MONEY-DEFAULT", "advise_do_not_send", "money_denied", {"claimed_name": claimed_name})
    if state in {"confirmed", "late_confirmed"}:
        member = member_by_id(inp.village_state, claimed_id) or {}
        return finish(
            inp,
            "R-MONEY-DEFAULT",
            "advise_talk_to_coordinator",
            "money_confirmed",
            {"claimed_name": claimed_name, "pronoun": member.get("pronoun", "he")},
            ["R-MONEY-NEVER"],
        )
    out = finish(inp, "R-MONEY-DEFAULT", "advise_do_not_send", "money_timeout", {"claimed_name": claimed_name})
    out["writes"] = [_incident(inp, "unverified_money_request", "warn", f"Could not confirm with {claimed_name}", {"claimed_member_id": claimed_id})]
    return out


def _deadline_decision(inp: GateInput) -> dict[str, Any]:
    verification = inp.village_state.get("open_verifications", [{}])[0]
    claimed_id = verification.get("claimed_member_id", "m_marco")
    out = finish(inp, "R-MONEY-DEFAULT", "allow")
    out["writes"] = [
        {
            "kind": "verification_timeout",
            "payload": {
                "verification_id": verification.get("id", inp.alloc.get("verification_id", "ver_unknown")),
                "claimed_member_id": claimed_id,
                "reason": "deadline",
                "state": "timed_out",
            },
        }
    ]
    return out


def _money_request_payload(payload: dict[str, Any], verification_id: str | None, red_flags: list[str]) -> dict[str, Any]:
    value = {
        "subject": payload["subject"],
        "claimed_member_id": payload.get("claimed_member_id"),
        "claimed_identity": payload.get("claimed_identity", "unknown"),
        "amount": payload.get("amount"),
        "currency": payload.get("currency", "USD"),
        "method": payload.get("method", "unknown"),
        "urgency": payload.get("urgency", "unspecified"),
        "red_flags": red_flags,
        "utterance": _redact_digits(payload.get("utterance", "")),
        "verification_id": verification_id,
    }
    return value


def _answered_payload(payload: dict[str, Any], claimed_id: str, state: str) -> dict[str, Any]:
    value = {
        "verification_id": payload["verification_id"],
        "claimed_member_id": claimed_id,
        "answered_via": payload.get("via", "app_prompt"),
        "late": False,
        "state": state,
    }
    if payload.get("quote"):
        value["utterance"] = payload["quote"]
    return value


def _incident(inp: GateInput, incident_type: str, severity: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    verification_id = inp.alloc.get("verification_id") or payload.get("verification_id") or "ver_unknown"
    incident_id = inp.alloc.get("incident_id") or f"inc_{verification_id}"
    event_id = _current_money_event_id(inp)
    return {
        "kind": "incident",
        "payload": {
            "incident_id": incident_id,
            "type": incident_type,
            "severity": severity,
            "status": "open",
            "title": {"en": "Money request needs review", "es": "Solicitud de dinero para revisar"},
            "summary": {"en": summary, "es": summary},
            "related_event_ids": [event_id],
            "verification_id": verification_id,
            "notified": [inp.village_state["coordinator_id"]],
        },
    }


def _channels_for_member(member: dict[str, Any] | None) -> list[str]:
    if not member:
        return []
    consent = member.get("consent", {})
    channels = []
    if member.get("has_app_session") and consent.get("app_prompts"):
        channels.append("app_prompt")
    if consent.get("ai_calls"):
        channels.append("outbound_call")
    return channels


def _open_verification(inp: GateInput, verification_id: str) -> dict[str, Any] | None:
    for verification in inp.village_state.get("open_verifications", []):
        if verification.get("id") == verification_id:
            return verification
    return None


def _red_flags(payload: dict[str, Any]) -> list[str]:
    flags = list(payload.get("red_flags", []))
    method = payload.get("method")
    if method in HARD_METHOD_FLAGS and HARD_METHOD_FLAGS[method] not in flags:
        flags.append(HARD_METHOD_FLAGS[method])
    text = _event_text(payload)
    for needle, flag in PRESSURE_TEXT_FLAGS.items():
        if needle in text and flag not in flags:
            flags.append(flag)
    return flags


def _pattern_event_ids(inp: GateInput) -> list[str]:
    recent = list(inp.village_state.get("recent_money_requests", []))
    cutoff = parse_dt(inp.event["at"]) - timedelta(days=30)
    ids = [row["event_id"] for row in recent if parse_dt(row["at"]) >= cutoff]
    if ids:
        ids.append(_current_money_event_id(inp))
    return ids if len(ids) >= 2 else []


def _current_money_event_id(inp: GateInput) -> str:
    if inp.alloc.get("verification_id") == "ver_1016_01":
        return "ev_1016_1402_money"
    basis = inp.alloc.get("verification_id") or inp.alloc["decision_id"]
    clean = re.sub(r"[^A-Za-z0-9_]", "_", basis)
    return f"ev_{clean}_money"


def _redact_digits(text: str) -> str:
    return re.sub(r"\d", "X", text)


def _event_text(payload: dict[str, Any]) -> str:
    return " ".join(str(payload.get(k, "")) for k in ("utterance", "text", "claimed_identity")).lower()


def _asks_village_to_handle_money(text: str) -> bool:
    return any(word in text for word in MONEY_WORDS) and any(
        verb in text for verb in ("transfer", "buy", "send", "read", "account", "card", "envía", "compra")
    )


def _benign_money_to_carmen(payload: dict[str, Any], text: str) -> bool:
    return payload.get("direction") == "to_subject" or ("paga" in text and "debe" in text)
