"""Pure money-verification state machine."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from core.gate.rules.common import parse_dt

STATUS_OF_STATE = {
    "pending": "pending",
    "default_spoken": "pending",
    "confirmed": "confirmed",
    "late_confirmed": "confirmed",
    "denied": "denied",
    "late_denied": "denied",
    "unsure": "timeout",
    "unreachable": "timeout",
    "timed_out": "timeout",
}
TERMINAL = {"confirmed", "late_confirmed", "denied", "late_denied", "unsure", "unreachable", "timed_out"}


def step_verification(verification: dict[str, Any], event: dict[str, Any], now: str | datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply one verification transition.

    ``event`` accepts either compact SM events like
    ``{"type": "answer", "answer": "no", ...}`` or gate candidate-shaped
    events with ``kind`` and ``payload``.
    """

    current = deepcopy(verification)
    now_s = now.isoformat() if isinstance(now, datetime) else str(now)
    ev = _normalize_event(event)
    emits: list[dict[str, Any]] = []

    if ev["type"] == "answer":
        next_v, answer_emits = _answer(current, ev, now_s)
        return next_v, answer_emits

    if ev["type"] == "await_returned":
        if current["state"] == "pending" and parse_dt(now_s) >= parse_dt(current["deadline"]):
            _transition(current, "timed_out", now_s, "deadline")
            current["resolved_at"] = now_s
            current["spoken_say_key"] = "money_timeout"
            current["incident_id"] = current.get("incident_id") or f"inc_{current['id']}"
            emits.append(
                {
                    "kind": "verification_timeout",
                    "payload": {
                        "verification_id": current["id"],
                        "claimed_member_id": current["claimed_member_id"],
                        "reason": "deadline",
                        "state": "timed_out",
                    },
                }
            )
            emits.append(_incident(current, "unverified_money_request", "warn"))
        elif current["state"] == "pending" and _seconds_since_created(current, now_s) >= 30:
            _transition(current, "default_spoken", now_s, "await_returned")
            current["await_returned_at"] = now_s
            current["spoken_say_key"] = "money_timeout"
            current["incident_id"] = current.get("incident_id") or f"inc_{current['id']}"
            emits.append(_incident(current, "unverified_money_request", "warn"))
        return _finalize(current), emits

    if ev["type"] == "tick":
        if current["state"] in {"pending", "default_spoken"} and parse_dt(now_s) >= parse_dt(current["deadline"]):
            _transition(current, "timed_out", now_s, "deadline")
            current["resolved_at"] = now_s
            if current.get("await_returned_at") is None and current.get("spoken_say_key") is None:
                current["spoken_say_key"] = "money_timeout"
            current["incident_id"] = current.get("incident_id") or f"inc_{current['id']}"
            emits.append(
                {
                    "kind": "verification_timeout",
                    "payload": {
                        "verification_id": current["id"],
                        "claimed_member_id": current["claimed_member_id"],
                        "reason": "deadline",
                        "state": "timed_out",
                    },
                }
            )
            if verification["state"] == "pending":
                emits.append(_incident(current, "unverified_money_request", "warn"))
        return _finalize(current), emits

    if ev["type"] == "unreachable":
        _transition(current, "unreachable", now_s, "unreachable")
        current["resolved_at"] = now_s
        current["spoken_say_key"] = "money_timeout"
        current["incident_id"] = current.get("incident_id") or f"inc_{current['id']}"
        emits.extend(
            [
                {
                    "kind": "verification_timeout",
                    "payload": {
                        "verification_id": current["id"],
                        "claimed_member_id": current["claimed_member_id"],
                        "reason": "unreachable",
                        "state": "unreachable",
                    },
                },
                _incident(current, "unverified_money_request", "warn"),
            ]
        )
        return _finalize(current), emits

    return _finalize(current), emits


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    if "type" in event:
        return dict(event)
    kind = event.get("kind")
    payload = event.get("payload", {})
    if kind == "verification_answer":
        return {
            "type": "answer",
            "answer": payload["answer"],
            "via": payload["via"],
            "member_id": payload["member_id"],
            "quote": payload.get("quote"),
        }
    if kind == "await_returned":
        return {"type": "await_returned"}
    if kind == "tick":
        return {"type": "tick"}
    return {"type": kind or "noop"}


def _answer(current: dict[str, Any], ev: dict[str, Any], now_s: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    emits: list[dict[str, Any]] = []
    answer = {
        "answer": ev["answer"],
        "via": ev.get("via", "app_prompt"),
        "member_id": ev.get("member_id", current["claimed_member_id"]),
        "at": now_s,
        "secs_since_created": _seconds_since_created(current, now_s),
        "outcome": "applied",
    }
    if ev.get("quote"):
        answer["quote"] = ev["quote"]

    applied = _applied_answer(current)
    if applied is not None:
        answer["outcome"] = "dup" if applied["answer"] == answer["answer"] else "conflict"
        current.setdefault("answers", []).append(answer)
        if answer["outcome"] == "conflict":
            emits.append(
                {
                    "kind": "verification_answer_conflict",
                    "payload": {
                        "verification_id": current["id"],
                        "winner": {"answer": applied["answer"], "via": applied["via"]},
                        "loser": {"answer": answer["answer"], "via": answer["via"]},
                    },
                }
            )
            if applied["answer"] == "yes":
                _transition(current, "unsure", now_s, "answer")
                current["resolved_at"] = now_s
                emits.append(_timeout_emit(current, "unsure"))
                emits.append(_incident(current, "unverified_money_request", "warn"))
        return _finalize(current), emits

    if current["state"] not in {"pending", "default_spoken"}:
        answer["outcome"] = "ignored"
        current.setdefault("answers", []).append(answer)
        return _finalize(current), emits

    current.setdefault("answers", []).append(answer)
    late = current["state"] == "default_spoken"

    if answer["answer"] == "yes":
        new_state = "late_confirmed" if late else "confirmed"
        _transition(current, new_state, now_s, "answer")
        current["resolved_at"] = now_s
        emits.append(
            {
                "kind": "verification_confirmed",
                "payload": _answered_payload(current, answer, late, new_state),
            }
        )
    elif answer["answer"] == "no":
        new_state = "late_denied" if late else "denied"
        _transition(current, new_state, now_s, "answer")
        current["resolved_at"] = now_s
        current["incident_id"] = current.get("incident_id") or f"inc_{current['id']}"
        emits.append({"kind": "verification_denied", "payload": _answered_payload(current, answer, late, new_state)})
        emits.append(_incident(current, "suspected_scam", "high"))
    else:
        _transition(current, "unsure", now_s, "answer")
        current["resolved_at"] = now_s
        current["incident_id"] = current.get("incident_id") or f"inc_{current['id']}"
        emits.append(_timeout_emit(current, "unsure"))
        emits.append(_incident(current, "unverified_money_request", "warn"))

    return _finalize(current), emits


def _transition(current: dict[str, Any], to_state: str, at: str, cause: str) -> None:
    from_state = current["state"]
    if from_state == to_state:
        return
    current["state"] = to_state
    current.setdefault("transitions", []).append({"from": from_state, "to": to_state, "at": at, "cause": cause})
    current["version"] = int(current.get("version", 0)) + 1


def _finalize(current: dict[str, Any]) -> dict[str, Any]:
    current["status"] = STATUS_OF_STATE[current["state"]]
    return current


def _applied_answer(current: dict[str, Any]) -> dict[str, Any] | None:
    for answer in current.get("answers", []):
        if answer.get("outcome") == "applied":
            return answer
    return None


def _seconds_since_created(current: dict[str, Any], now_s: str) -> float:
    return (parse_dt(now_s) - parse_dt(current["created_at"])).total_seconds()


def _answered_payload(current: dict[str, Any], answer: dict[str, Any], late: bool, state: str) -> dict[str, Any]:
    payload = {
        "verification_id": current["id"],
        "claimed_member_id": current["claimed_member_id"],
        "answered_via": answer["via"],
        "late": late,
        "state": state,
    }
    if answer.get("quote"):
        payload["utterance"] = answer["quote"]
    return payload


def _timeout_emit(current: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "kind": "verification_timeout",
        "payload": {
            "verification_id": current["id"],
            "claimed_member_id": current["claimed_member_id"],
            "reason": reason,
            "state": current["state"],
        },
    }


def _incident(current: dict[str, Any], incident_type: str, severity: str) -> dict[str, Any]:
    return {
        "kind": "incident",
        "payload": {
            "incident_id": current.get("incident_id") or f"inc_{current['id']}",
            "type": incident_type,
            "severity": severity,
            "status": "open",
            "title": {"en": "Money request needs review", "es": "Solicitud de dinero para revisar"},
            "summary": {"en": "Verification did not confirm the request.", "es": "La verificación no confirmó la solicitud."},
            "related_event_ids": [current.get("money_request_event_id") or f"ev_{current['id']}_money"],
            "verification_id": current["id"],
            "notified": [m for m in [current.get("coordinator_id")] if m],
        },
    }
