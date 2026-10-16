from __future__ import annotations

from typing import Any

from core.clock import clock
from core.db import db


def view_binds(role: str) -> set[str]:
    if role == "control":
        return {"*"}
    view = db.views.get(("v_reyes", role), {})
    binds: set[str] = set()
    for element in view.get("elements", {}).values():
        bind = element.get("props", {}).get("bind")
        if bind:
            binds.add(bind)
    return binds


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
    binds = view_binds(role)
    data: dict[str, Any] = {}
    if "*" in binds or "alerts:active" in binds:
        data["alerts:active"] = active_alerts(role)
    if member_id and ("*" in binds or "verifications:pending?member=me" in binds):
        data["verifications:pending?member=me"] = pending_verification_prompt(member_id)
    if member_id and ("*" in binds or "verifications:mine" in binds):
        data["verifications:mine"] = my_verification(member_id)
    if "*" in binds or "incidents:open" in binds:
        data["incidents:open"] = open_incidents()
    if "*" in binds or "facts:dose_event?subject=m_carmen&valid_at=today" in binds:
        data["facts:dose_event?subject=m_carmen&valid_at=today"] = dose_day("m_carmen", show_med_names=role != "elder")
    if "*" in binds or "facts:dose_event?subject=m_carmen&valid_at=week" in binds:
        data["facts:dose_event?subject=m_carmen&valid_at=week"] = dose_day("m_carmen", show_med_names=role != "elder")
    if "*" in binds or "facts:dose_event?subject=m_carmen&valid_at=today?count" in binds:
        data["facts:dose_event?subject=m_carmen&valid_at=today?count"] = len([ev for ev in db.events if ev["kind"] == "dose"])
    if member_id and ("*" in binds or "rota:current?member=me" in binds):
        data["rota:current?member=me"] = rota_me(member_id)
    return data


def changed(event: dict[str, Any], role: str, member_id: str | None = None) -> dict[str, Any]:
    if event["kind"] in {"verification_pending", "verification_confirmed", "verification_denied", "verification_timeout"}:
        data: dict[str, Any] = {"alerts:active": active_alerts(role)}
        verification_id = event.get("payload", {}).get("verification_id")
        verification = db.verifications.get(verification_id) if verification_id else None
        if member_id and verification and verification.get("claimed_member_id") == member_id:
            data["verifications:pending?member=me"] = pending_verification_prompt(member_id)
            data["verifications:mine"] = my_verification(member_id)
        return data
    if event["kind"] in {"incident", "ack"}:
        return {"incidents:open": open_incidents()}
    if event["kind"] == "dose":
        return {
            key: value
            for key, value in snapshot_data(role, member_id).items()
            if key.startswith("facts:dose_event")
        }
    return {}


def pending_verification_prompt(member_id: str) -> dict[str, Any] | None:
    verification = _latest_verification(member_id, states={"pending", "default_spoken"})
    if verification is None:
        return None
    return {
        "verification_id": verification["id"],
        "question": _verification_question(verification),
        "detail": _verification_detail(verification),
        "deadline": verification["deadline"],
        "subject": verification.get("subject", "m_carmen"),
    }


def my_verification(member_id: str) -> dict[str, Any] | None:
    verification = _latest_verification(member_id)
    if verification is None:
        return None
    return {
        "verification_id": verification["id"],
        "claimed_member_id": verification["claimed_member_id"],
        "claimed_name": verification.get("claimed_identity") or _member_name(verification["claimed_member_id"]),
        "status": verification["status"],
        "state": verification["state"],
        "deadline": verification["deadline"],
        "say": _say_for_verification(verification),
    }


def active_alerts(role: str) -> list[dict[str, Any]]:
    alerts = []
    for verification in db.verifications.values():
        if verification.get("status") not in {"pending", "denied", "timeout"}:
            continue
        if verification.get("status") == "pending":
            severity = "warn"
            title = {"es": "No mande dinero todavia"} if role == "elder" else {"en": "Possible scam"}
            body = (
                {"es": "Estamos confirmando con Marco."}
                if role == "elder"
                else {"en": f"Someone claiming to be {_member_name(verification['claimed_member_id'])} asked for money. Village is checking."}
            )
        elif verification.get("status") == "denied":
            severity = "danger"
            title = {"es": "Ese no era Marco"} if role == "elder" else {"en": "Scam stopped"}
            body = {"es": "No mande dinero."} if role == "elder" else {"en": "The request was denied by the real contact."}
        else:
            severity = "warn"
            title = {"es": "No se pudo confirmar"} if role == "elder" else {"en": "Could not confirm"}
            body = {"es": "No mande dinero."} if role == "elder" else {"en": "Village could not confirm the money request in time."}
        alerts.append({
            "id": f"al_{verification['id']}",
            "severity": severity,
            "title": title,
            "body": body,
            "verification": {
                "id": verification["id"],
                "claimed_member_id": verification["claimed_member_id"],
                "deadline": verification["deadline"],
                "status": verification["status"],
            },
            "at": verification.get("resolved_at") or verification.get("created_at") or clock.now().isoformat(),
        })
    return alerts


def open_incidents() -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in db.events:
        if event["kind"] != "incident":
            continue
        payload = event["payload"]
        latest[payload["incident_id"]] = event
    incidents = []
    for event in latest.values():
        payload = event["payload"]
        if payload.get("status") == "closed":
            continue
        verification = db.verifications.get(payload.get("verification_id", ""))
        request = verification.get("request", {}) if verification else {}
        incidents.append({
            "incident_id": payload["incident_id"],
            "type": payload["type"],
            "severity": payload["severity"],
            "status": payload["status"],
            "title": payload["title"],
            "summary": payload["summary"],
            "verification_id": payload.get("verification_id"),
            "verification_status": verification.get("status") if verification else None,
            "claimed_identity": verification.get("claimed_identity") if verification else None,
            "amount": request.get("amount"),
            "method": request.get("method", "unknown"),
            "red_flags": request.get("red_flags", []),
            "pattern_flag": payload.get("pattern_flag"),
            "provenance": _incident_provenance(event, verification),
            "at": event["at"],
        })
    return incidents


def verification_prompt_frame(verification: dict[str, Any], *, closed: bool = False) -> dict[str, Any]:
    frame = {
        "type": "prompt",
        "verification_id": verification["id"],
        "question": _verification_question(verification),
        "detail": _verification_detail(verification),
        "options": [
            {"id": "no", "label": {"en": "That wasn't me", "es": "No fui yo"}},
            {"id": "yes", "label": {"en": "Yes, it was me", "es": "Si, fui yo"}},
        ],
        "deadline": verification["deadline"],
    }
    if closed:
        frame["closed"] = True
    return frame


def _latest_verification(member_id: str, *, states: set[str] | None = None) -> dict[str, Any] | None:
    rows = [
        row
        for row in db.verifications.values()
        if row.get("claimed_member_id") == member_id and (states is None or row.get("state") in states)
    ]
    return max(rows, key=lambda row: row.get("created_at", "")) if rows else None


def _verification_question(verification: dict[str, Any]) -> dict[str, str]:
    amount = verification.get("request", {}).get("amount")
    amount_s = f"${amount:,.0f}" if isinstance(amount, (int, float)) and amount else "money"
    return {
        "en": f"Did you just call Mama asking for {amount_s}?",
        "es": f"Acaba de llamar a Mama pidiendo {amount_s}?",
    }


def _verification_detail(verification: dict[str, Any]) -> dict[str, str]:
    claimed = verification.get("claimed_identity") or _member_name(verification.get("claimed_member_id", ""))
    return {
        "en": f"Someone on the phone said they were {claimed}. She has not sent anything.",
        "es": f"Alguien por telefono dijo que era {claimed}. Ella no ha enviado nada.",
    }


def _say_for_verification(verification: dict[str, Any]) -> dict[str, str] | None:
    state = verification.get("state")
    if state in {"denied", "late_denied"}:
        return {"en": "Do not send money.", "es": "No mande dinero."}
    if state in {"timed_out", "unsure", "unreachable"}:
        return {"en": "Could not confirm. Do not send money.", "es": "No se pudo confirmar. No mande dinero."}
    if state in {"confirmed", "late_confirmed"}:
        return {"en": "Confirmed.", "es": "Confirmado."}
    return None


def _member_name(member_id: str) -> str:
    person = db.members.get(member_id, {})
    return str(person.get("name", member_id)).split()[0]


def _incident_provenance(event: dict[str, Any], verification: dict[str, Any] | None) -> list[dict[str, Any]]:
    provenance = []
    if verification and verification.get("conversation_id"):
        provenance.append({
            "label": "Original call",
            "source": {"kind": "call", "ref": verification["conversation_id"]},
        })
    if event.get("source"):
        provenance.append({"label": "Village decision", "source": event["source"]})
    return provenance
