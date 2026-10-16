"""Mom-line tools Core's `/tools/{name}` dispatcher does not serve: ask_family, report_symptom, whats_my_schedule, get_today.

Each goes through the gate (`core.services.decide`, so a decision row exists) where a decision applies, answers in the
`voice_tools.schema.json#/$defs/response` shape, honours `lang` (es|en) and carries both lines in `data.say_es/say_en` (D18).
Reached via `POST /hooks/elevenlabs/tools/<tool>` (core.voice.voice_routes -> core.voice.tools.LOCAL_TOOLS).
"""
from __future__ import annotations

from typing import Any

from core import village


def _lang(body: dict[str, Any]) -> str:
    return "en" if str(body.get("lang") or body.get("language") or "es").lower().startswith("en") else "es"


def _vid(body: dict[str, Any]) -> str:
    return body.get("village_id") or village.default_village_id()


def _source(body: dict[str, Any]) -> dict[str, Any]:
    secs = body.get("call_secs") or 0
    try:
        secs = int(float(secs))
    except (TypeError, ValueError):
        secs = 0
    return {"kind": "call", "ref": body.get("conversation_id") or "conv_unknown", "secs": secs, "quote": str(body.get("utterance") or "")[:300]}


def _response(decision: str, rule_id: str, pair: dict[str, str], body: dict[str, Any], data: dict[str, Any], say_key: str | None = None, decision_id: str | None = None) -> dict[str, Any]:
    lang = _lang(body)
    out: dict[str, Any] = {
        "decision": decision,
        "say": (pair.get(lang) or pair.get("es") or "")[:400],
        "rule_id": rule_id,
        "lang": lang,
        "data": {**data, "say_es": pair.get("es", ""), "say_en": pair.get("en", "")},
    }
    if say_key:
        out["say_key"] = say_key
    if decision_id:
        out["decision_id"] = decision_id
    return out


def _names(vid: str) -> dict[str, str]:
    from core import services

    state = services._village_state(vid)
    on_duty = (state.get("rota_today") or {}).get("on_duty") or village.coordinator_id(vid)
    return {
        "on_duty_name": village.first_name(vid, on_duty) or village.first_name(vid, village.coordinator_id(vid)),
        "coordinator_name": village.first_name(vid, village.coordinator_id(vid)),
        "recipient_name": village.first_name(vid, village.care_recipient_id(vid)),
    }


def _join(*pairs: dict[str, str]) -> dict[str, str]:
    return {lang: " ".join(p[lang] for p in pairs if p.get(lang)) for lang in ("es", "en")}


async def ask_family(body: dict[str, Any]) -> dict[str, Any]:
    from core import services
    from core.gate.say import say

    vid = _vid(body)
    names = _names(vid)
    question = str(body.get("message") or body.get("question") or body.get("utterance") or "").strip()
    who = names["recipient_name"] or "Mom"
    message = await services.post_message(
        vid,
        author="village",
        kind="chat",
        text=f"{who} asked on the phone line: \"{question}\"",
        text_i18n={"es": f"{who} preguntó por teléfono: \"{question}\"", "en": f"{who} asked on the phone line: \"{question}\""},
        source=_source(body),
    )
    pair = say("family_notified", on_duty_name=names["on_duty_name"])
    return _response("escalate_family", "R-NOOP", pair, body, {"status": "sent", "message_id": message.get("id"), "to": body.get("to") or "family"}, say_key="family_notified")


async def report_symptom(body: dict[str, Any]) -> dict[str, Any]:
    from core import services
    from core.gate.say import say

    vid = _vid(body)
    subject = village.care_recipient_id(vid)
    emergency = bool(body.get("emergency_signals") is True or str(body.get("emergency_signals")).lower() == "true")
    payload = {
        "subject": subject,
        "type": body.get("type") if body.get("type") in {"symptom", "mood", "fall", "blood_pressure_reading", "blood_sugar_reading", "info_for_family"} else "symptom",
        "description": str(body.get("description") or body.get("utterance") or "")[:300],
        "emergency_signals": emergency,
        "utterance": str(body.get("utterance") or "")[:600],
    }
    if body.get("value"):
        payload["value"] = str(body["value"])[:40]
    decision = await services.decide(vid, {"village": vid, "kind": "symptom", "payload": payload, "actor": subject, "source": _source(body)})
    event = await services.record_event(vid, {"kind": "symptom", "payload": payload}, actor=subject, source=_source(body), decision_id=decision.get("id"))
    names = _names(vid)
    if decision.get("decision") == "advise_911":
        pair = decision.get("say") or say("advise_911_first")
        return _response("advise_911", decision.get("rule_id", "R-911"), pair, body, {"status": "emergency", "event_id": event["id"]}, decision.get("say_key"), decision.get("id"))
    pair = _join(say("dose_recorded"), say("family_notified", on_duty_name=names["on_duty_name"]))
    return _response("record", decision.get("rule_id", "R-NOOP"), pair, body, {"status": "recorded", "event_id": event["id"]}, "family_notified", decision.get("id"))


async def _schedule(body: dict[str, Any], with_today: bool) -> dict[str, Any]:
    from core import services
    from core.clock import clock
    from core.db import db

    vid = _vid(body)
    subject = village.care_recipient_id(vid)
    payload = {"subject": subject}
    if body.get("slot"):
        payload["slot"] = body["slot"]
    decision = await services.decide(vid, {"village": vid, "kind": "schedule_query", "payload": payload, "actor": subject, "source": _source(body)})
    data: dict[str, Any] = {"status": "readback", "prescriptions": db.prescriptions.get(vid, [])[:12]}
    names = _names(vid)
    data["on_duty_name"] = names["on_duty_name"]
    if with_today:
        today = clock.now().date().isoformat()
        doses = [
            {"slot": ev["payload"].get("slot"), "taken_at": ev["payload"].get("taken_at")}
            for ev in db.events
            if ev.get("kind") == "dose" and ev.get("village", vid) == vid and str(ev["payload"].get("taken_at") or ev.get("at") or "").startswith(today)
        ]
        data["doses_today"] = doses
    pair = decision.get("say") or {"es": "", "en": ""}
    return _response(decision.get("decision", "remind"), decision.get("rule_id", "R-DOSE-ADVICE"), pair, body, data, decision.get("say_key"), decision.get("id"))


async def whats_my_schedule(body: dict[str, Any]) -> dict[str, Any]:
    return await _schedule(body, with_today=False)


async def get_today(body: dict[str, Any]) -> dict[str, Any]:
    return await _schedule(body, with_today=True)


def _hm(iso: str, village_id: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        return datetime.fromisoformat(iso).astimezone(ZoneInfo(village.timezone(village_id) or "America/New_York")).strftime("%H:%M")
    except Exception:
        return iso[11:16]


async def relay_message(body: dict[str, Any]) -> dict[str, Any]:
    """Receptionist: an unknown caller leaves a message / asks for a callback -> Village chat message + screened row."""
    from core import services
    from core.clock import clock
    from core.voice import screened

    vid = _vid(body)
    names = _names(vid)
    recipient = village.person(vid, village.care_recipient_id(vid)) or {}
    who_family = recipient.get("short_name") or names["recipient_name"] or "her"
    from_name = str(body.get("from_name") or "Someone").strip()[:80]
    text = str(body.get("text") or body.get("message") or body.get("utterance") or "").strip()[:400]
    caller = str(body.get("caller_id") or "")
    callback = str(body.get("callback_number") or "").strip()
    at = clock.now().isoformat()
    hm = _hm(at, vid)
    back = "at the same number" if not callback or callback == caller else f"at {callback}"
    back_es = "al mismo número" if not callback or callback == caller else f"al {callback}"
    asks_back = bool(body.get("callback_requested", True))
    who = f"{from_name}," if "," in from_name else from_name  # "Richard, from church, asked …"
    en = f"{who} asked {who_family} to call back {back}: \"{text}\" · screened call, {hm}" if asks_back else f"{who} left a message for {who_family}: \"{text}\" · screened call, {hm}"
    es = f"{who} pidió que {who_family} le devuelva la llamada {back_es}: \"{text}\" · llamada filtrada, {hm}" if asks_back else f"{who} dejó un mensaje para {who_family}: \"{text}\" · llamada filtrada, {hm}"
    message = await services.post_message(vid, author="village", kind="chat", text=en, text_i18n={"en": en, "es": es}, source=_source(body))
    screened.record(vid, str(body.get("conversation_id") or message.get("id")), "message_taken", at=at, claimed=from_name, message=en, callback=callback or caller or None)
    pair = {
        "en": f"Thank you. I'll pass your message to the family. They'll call you back {back}.",
        "es": f"Gracias. Le paso su mensaje a la familia. Le van a devolver la llamada {back_es}.",
    }
    return _response("escalate_family", "R-NOOP", pair, body, {"status": "message_taken", "message_id": message.get("id")}, "family_notified")


HANDLERS = {
    "relay_message": relay_message,
    "ask_family": ask_family,
    "report_symptom": report_symptom,
    "whats_my_schedule": whats_my_schedule,
    "get_today": get_today,
}
