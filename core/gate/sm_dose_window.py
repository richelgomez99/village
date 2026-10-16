"""Pure dose-window state machine."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from core.gate.rules.common import parse_dt


@dataclass
class FakeClock:
    current: str

    def now(self) -> str:
        return self.current

    def warp(self, *, minutes: int = 0, to: str | None = None) -> str:
        if to is not None:
            self.current = to
        else:
            self.current = (parse_dt(self.current) + timedelta(minutes=minutes)).isoformat()
        return self.current


def step_dose_window(window: dict[str, Any], event: dict[str, Any], now: str | datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current = deepcopy(window)
    now_s = now.isoformat() if isinstance(now, datetime) else str(now)
    ev = _normalize_event(event)

    if ev["type"] == "dose":
        return _record_dose(current, ev, now_s)
    if ev["type"] == "skip_ack":
        return _transition(current, "skipped_ack", now_s), [_notify(current, "dose_uncertain")]
    if ev["type"] != "tick":
        return current, []

    return _tick(current, now_s)


def _tick(current: dict[str, Any], now_s: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now_dt = parse_dt(now_s)
    due = _due_at(current, now_dt)
    state = current["state"]

    if state == "scheduled" and now_dt >= due - timedelta(minutes=30):
        return _transition(current, "window_open", now_s), []

    if state in {"window_open", "reminded"} and now_dt >= due + timedelta(minutes=90) and not current.get("escalation_placed_at"):
        current = _transition(current, "escalated_1", now_s)
        current["escalation_placed_at"] = now_s
        current["escalated_to"] = current.get("on_duty")
        return current, [_escalation(current, current.get("on_duty"), 1, "missed_dose")]

    if state == "window_open" and now_dt >= due + timedelta(minutes=45) and not current.get("reminder_placed_at"):
        if _in_quiet_hours(now_dt, current.get("quiet_hours")):
            return current, []
        current = _transition(current, "reminded", now_s)
        current["reminder_placed_at"] = now_s
        return current, [_reminder(current)]

    if state == "escalated_1" and current.get("escalation_placed_at"):
        placed = parse_dt(current["escalation_placed_at"])
        if now_dt >= placed + timedelta(minutes=15) and current.get("backup") and current.get("escalated_to") != current.get("backup"):
            current = _transition(current, "escalated_2", now_s)
            current["escalation_placed_at"] = now_s
            current["escalated_to"] = current.get("backup")
            return current, [_escalation(current, current.get("backup"), 2, "missed_dose")]

    if state in {"window_open", "reminded", "escalated_1", "escalated_2"} and now_dt >= due + timedelta(hours=4):
        current = _transition(current, "closed", now_s)
        if state in {"window_open", "reminded"}:
            return current, [_escalation(current, current.get("on_duty"), 1, "missed_dose")]
        return current, []

    return current, []


def _record_dose(current: dict[str, Any], ev: dict[str, Any], now_s: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current = _transition(current, "taken", now_s)
    current["dose_event_id"] = ev.get("event_id", current.get("dose_event_id") or "ev_pending")
    current["taken_at"] = ev.get("taken_at", now_s)
    current["confidence"] = ev.get("confidence", "confirmed")
    actions: list[dict[str, Any]] = []
    due = _due_at(current, parse_dt(now_s))
    taken = parse_dt(current["taken_at"])
    if not (due - timedelta(minutes=30) <= taken <= due + timedelta(hours=4)):
        actions.append({"type": "FLAG", "flag": "off_schedule"})
    return current, actions


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    if "type" in event:
        return dict(event)
    if event.get("kind") == "dose":
        payload = event.get("payload", {})
        return {
            "type": "dose",
            "event_id": event.get("id") or payload.get("event_id"),
            "taken_at": payload.get("taken_at") or event.get("at"),
            "confidence": payload.get("confidence", "confirmed"),
        }
    if event.get("kind") == "tick":
        return {"type": "tick"}
    return {"type": event.get("kind", "noop")}


def _transition(current: dict[str, Any], state: str, now_s: str) -> dict[str, Any]:
    if current["state"] != state:
        current["state"] = state
        current["version"] = int(current.get("version", 0)) + 1
    current["next_check_at"] = now_s
    return current


def _due_at(current: dict[str, Any], reference: datetime) -> datetime:
    date = current["date"]
    slot_time = current["slot_time"]
    offset = reference.strftime("%z")
    suffix = f"{offset[:3]}:{offset[3:]}" if offset else "+00:00"
    return parse_dt(f"{date}T{slot_time}:00{suffix}")


def _in_quiet_hours(now: datetime, window: str | None) -> bool:
    if not window:
        return False
    start_s, end_s = window.split("-", 1)
    start = _minutes(start_s)
    end = _minutes(end_s)
    value = now.hour * 60 + now.minute
    if start <= end:
        return start <= value < end
    return value >= start or value < end


def _minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def _reminder(current: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "CALL",
        "member_id": current["subject"],
        "event": {
            "kind": "reminder",
            "payload": {
                "subject": current["subject"],
                "slot": current["slot"],
                "channel": "outbound_call",
                "rule_id": "R-MISSED",
            },
        },
    }


def _notify(current: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"type": "NOTIFY", "member_id": current.get("on_duty"), "reason": reason}


def _escalation(current: dict[str, Any], member_id: str | None, level: int, reason: str) -> dict[str, Any]:
    return {
        "type": "CALL",
        "member_id": member_id,
        "event": {
            "kind": "escalation",
            "payload": {
                "to": member_id,
                "channel": "outbound_call",
                "reason": reason,
                "rule_id": "R-MISSED",
                "level": level,
                "status": "placed",
            },
        },
    }
