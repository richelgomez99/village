from __future__ import annotations

from typing import Any

from core.db import db


def dose_day(subject: str = "m_carmen", *, show_med_names: bool = False) -> dict[str, Any]:
    result = {"subject": subject, "date": "2026-10-16", "slots": {}}
    for slot in ("morning", "evening"):
        event = next(
            (
                ev for ev in reversed(db.events)
                if ev["kind"] == "dose"
                and ev["payload"].get("subject") == subject
                and ev["payload"].get("slot") == slot
            ),
            None,
        )
        result["slots"][slot] = {
            "status": "taken" if event else "unknown",
            "event_id": event["id"] if event else None,
            "taken_at": event["payload"].get("taken_at") if event else None,
        }
    if show_med_names:
        result["meds"] = db.prescriptions.get("v_reyes", [])
    return result


def rota_me(member_id: str) -> dict[str, Any]:
    shift = next((ev for ev in reversed(db.events) if ev["kind"] == "shift"), None)
    on_duty = shift["payload"].get("on_duty") if shift else "m_marco"
    return {
        "member_id": member_id,
        "is_my_turn": member_id == on_duty,
        "on_duty": on_duty,
        "backup": shift["payload"].get("backup") if shift else "m_ana",
        "answer": "Yes. You're on tonight." if member_id == on_duty else "No. Marco is on tonight.",
    }


def snapshot_data(role: str, member_id: str | None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "facts:dose_event?subject=m_carmen&valid_at=today": dose_day("m_carmen", show_med_names=role != "elder"),
        "facts:dose_event?subject=m_carmen&valid_at=today?count": len([ev for ev in db.events if ev["kind"] == "dose"]),
    }
    if member_id:
        data["rota:current?member=me"] = rota_me(member_id)
    return data


def changed(event: dict[str, Any], role: str, member_id: str | None = None) -> dict[str, Any]:
    if event["kind"] == "dose":
        return snapshot_data(role, member_id)
    return {}
