"""Member-app bindings computed from events, decisions and the spec (core-glue 2; docs/UX-UPGRADE.md
"Village-agnostic by construction"): words come from the spec, counts from events. No village literals.

rounds:latest                     coordinator + control
events:since_last_turn?member=me  helper
blueprint:life_areas[].status     every view that binds it
scams stopped today / incidents   per village, from today's denied/timed-out verifications
proposal:<id>                     extra Evolve proposal fields (bv_proposal is additionalProperties:false)"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db

STOPPED_STATES = {"denied", "late_denied", "timed_out"}
_ROLE_FOR_ACTOR = {"gate": "verifier", "evolve": "watcher", "watcher": "watcher", "builder": "builder", "founder": "founder"}


def _today() -> str:
    return clock.now().date().isoformat()


def _first(village_id: str, member_id: str | None) -> str:
    return villages.first_name(village_id, member_id, member_id or "")


def _word(village_id: str, member_id: str | None, lang: str) -> str:
    """Relationship word for the center person from the spec's relationship_words, else first name."""
    return villages.relationship_word(village_id, member_id, lang)


def _plural(n: int, en: str, en_pl: str | None = None) -> str:
    return en if n == 1 else (en_pl or en + "s")


# ---- (1) rounds:latest ----------------------------------------------------------------------------

def rounds_latest(village_id: str) -> dict[str, Any]:
    try:
        from core.watcher.routes import LATEST, VAR
    except Exception:
        return {}
    result = LATEST.get(village_id)
    if result is None:
        try:
            import json

            p = VAR / f"latest_{village_id}.json"
            result = json.loads(p.read_text()) if p.exists() else None
        except Exception:
            result = None
    if not result:
        return {}
    counts = result.get("counts") or {}
    return {
        "night": str(result.get("round_at") or result.get("ran_at") or "")[:10],
        "counts": {k: int(counts.get(k, 0)) for k in ("acted_alone", "asked_human", "refused")},
        "rows": [{"at": r.get("at") or result.get("round_at") or result.get("ran_at"), "role": _ROLE_FOR_ACTOR.get(str(r.get("actor")), "watcher"), "text": r.get("text", ""),
                  "mode": r.get("mode"), "decision_id": r.get("id")} for r in result.get("rows", [])],
    }


# ---- (4) scams stopped today + incidents ----------------------------------------------------------

def stopped_verifications_today(village_id: str) -> list[dict[str, Any]]:
    today = _today()
    return [row for row in db.verifications.values()
            if row.get("village", village_id) == village_id and row.get("state") in STOPPED_STATES
            and str(row.get("resolved_at") or row.get("created_at") or "")[:10] == today]


def scams_stopped_today(village_id: str) -> int:
    from core.bindings import scams_stopped_today as count

    return count(village_id)

def scams_stopped_week(village_id: str, days: int = 7) -> int:
    """Stopped money requests in the last `days` (seeded ledger rows + live ones), deduped by verification."""
    since = (clock.now() - timedelta(days=days)).isoformat()
    ids = {ev.get("payload", {}).get("verification_id") or ev["id"] for ev in db.events
           if ev.get("village", village_id) == village_id and ev["kind"] in {"verification_denied", "verification_timeout"}
           and str(ev.get("at", "")) >= since[:10]}
    ids |= {row["id"] for row in db.verifications.values()
            if row.get("village", village_id) == village_id and row.get("state") in STOPPED_STATES
            and str(row.get("resolved_at") or row.get("created_at") or "") >= since[:10]}
    return len(ids)


def synthesized_incidents(village_id: str, have: set[str]) -> list[dict[str, Any]]:
    """Today's denied/timed-out verifications with no open incident row yet -> bv_incident."""
    out = []
    for row in stopped_verifications_today(village_id):
        if row["id"] in have:
            continue
        claimed = row.get("claimed_identity") or _first(village_id, row.get("claimed_member_id"))
        timed_out = row.get("state") == "timed_out"
        req = row.get("request") or {}
        out.append({
            "incident_id": row.get("incident_id") or f"inc_{row['id'].removeprefix('ver_')}"[:60],
            "type": "money_scam_suspected",
            "severity": "high",
            "status": "open",
            "title": {"en": f"Money asked in {claimed}'s name", "es": f"Pidieron dinero a nombre de {claimed}"},
            "summary": ({"en": f"No answer from {claimed} in time; Village said don't send.", "es": f"{claimed} no contestó a tiempo; Village dijo que no mande nada."}
                        if timed_out else
                        {"en": f"{claimed} said it wasn't them; Village said don't send.", "es": f"{claimed} dijo que no era; Village dijo que no mande nada."}),
            "verification_id": row["id"],
            "verification_status": row.get("status") or ("timeout" if timed_out else "denied"),
            "claimed_identity": claimed,
            "amount": req.get("amount"),
            "method": req.get("method", "unknown"),
            "red_flags": req.get("red_flags", []),
            "provenance": [{"label": "verification", "source": {"kind": "system", "ref": row["id"]}}],
            "at": row.get("resolved_at") or row.get("created_at") or clock.now().isoformat(),
        })
    return out


# ---- (3) life area status lines -------------------------------------------------------------------

def _dose_events_today(village_id: str, subject: str | None) -> list[dict[str, Any]]:
    today = _today()
    return [ev for ev in db.events if ev.get("village", village_id) == village_id and ev["kind"] == "dose"
            and (not subject or ev.get("payload", {}).get("subject") == subject) and str(ev.get("at", ""))[:10] == today]


def _refill_day(village_id: str) -> str | None:
    try:
        from core.bindings import prescriptions_current

        rx = prescriptions_current(villages.care_recipient_id(village_id), village_id) or {}
        return rx.get("refill_day"), rx.get("owner_member_id")
    except Exception:
        return None, None


def _on_duty(village_id: str) -> str | None:
    from core.bindings import _on_duty as on_duty

    return on_duty(village_id)


def _checked_today(village_id: str, members: list[str]) -> int:
    today = _today()
    seen = {ev.get("payload", {}).get("member_id") or ev.get("actor") for ev in db.events
            if ev.get("village", village_id) == village_id and str(ev.get("at", ""))[:10] == today
            and ev["kind"] in {"ack", "help_request", "symptom", "dose"}}
    return len([m for m in members if m in seen])


_DAYS = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}


_DAYS_ES = {"mon": "lunes", "tue": "martes", "wed": "miércoles", "thu": "jueves", "fri": "viernes", "sat": "sábado", "sun": "domingo"}


def area_word(area: dict[str, Any]) -> str:
    """The village's own one-word name for the area: 'Health: pills' -> 'Pills', 'Money: scam calls' -> 'Money'
    (a one-word tail is the specific word; a phrase falls back to the head)."""
    label = str(area.get("label") or area.get("id") or "")
    head, _, tail = label.partition(":")
    word = tail.strip() if tail.strip() and len(tail.split()) == 1 else head.strip()
    return (word[:1].upper() + word[1:]) if word else str(area.get("id"))


def life_area_status(village_id: str, area: dict[str, Any], spec: dict[str, Any]) -> dict[str, str]:
    aid = area.get("id")
    recipient = villages.care_recipient_id(village_id)
    on_duty = _on_duty(village_id)
    parts_en: list[str] = []
    parts_es: list[str] = []
    needs = [n for n in spec.get("blueprint", {}).get("needs", []) if n.get("life_area") == aid]
    if aid == "health" and recipient:
        doses = _dose_events_today(village_id, recipient)
        slots = sorted({ev["payload"].get("slot") for ev in doses if ev.get("payload", {}).get("slot")})
        if slots:
            parts_en.append(f"{' & '.join(slots)} taken")
            parts_es.append(f"{' y '.join(slots)} tomada{'s' if len(slots) > 1 else ''}")
        else:
            parts_en.append("nothing logged yet today")
            parts_es.append("nada registrado hoy")
        day, owner = _refill_day(village_id)
        if day:
            key = str(day).lower()[:3]
            parts_en.append(f"refill {_DAYS.get(key, str(day).capitalize())}")
            parts_es.append(f"reponer el {_DAYS_ES.get(key, str(day))}")
        who = owner or on_duty
        if who:
            parts_en.append(_first(village_id, who))
            parts_es.append(_first(village_id, who))
    elif aid == "money":
        n = scams_stopped_today(village_id)
        if n:
            parts_en.append(f"{n} {_plural(n, 'scam')} stopped today")
            parts_es.append(f"{n} {_plural(n, 'estafa')} detenida{'s' if n != 1 else ''} hoy")
        else:
            w = scams_stopped_week(village_id)
            parts_en.append(f"{w} {_plural(w, 'scam')} stopped this week" if w else "no scam calls this week")
            parts_es.append(f"{w} {_plural(w, 'estafa')} detenida{'s' if w != 1 else ''} esta semana" if w else "ninguna estafa esta semana")
        checker = villages.default_verifier(village_id)
        if checker:
            parts_en.append(f"{_first(village_id, checker)} checks money calls")
            parts_es.append(f"{_first(village_id, checker)} revisa las llamadas de dinero")
    elif aid == "people" and on_duty:
        parts_en.append(f"{_first(village_id, on_duty)} on duty tonight")
        parts_es.append(f"{_first(village_id, on_duty)} de turno esta noche")
    else:
        # group villages: the people this area's needs are about, checked today (from events)
        subjects: list[str] = []
        for n in needs:
            for m in n.get("subject_member_ids") or []:
                if m not in subjects:
                    subjects.append(m)
        if subjects:
            role = (villages.person(village_id, subjects[0]) or {}).get("role", "person")
            k = _checked_today(village_id, subjects)
            parts_en.append(f"{k} of {len(subjects)} {_plural(len(subjects), role)} checked")
            parts_es.append(f"{k} de {len(subjects)} revisados")
        elif needs:
            parts_en.append(f"{len(needs)} {_plural(len(needs), 'need')}")
            parts_es.append(f"{len(needs)} {_plural(len(needs), 'necesidad', 'necesidades')}")
    if aid == "money" and villages.receptionist_mode(village_id):  # Evolve D19/D35: the Money area says what changed
        parts_en.insert(0, "Village answers unknown calls first")
        parts_es.insert(0, "Village contesta primero a desconocidos")
    if not parts_en:
        return {"en": "ok", "es": "bien"}
    return {"en": " · ".join(parts_en), "es": " · ".join(parts_es)}


# ---- (2) events since this member's last turn -----------------------------------------------------

def _last_turn_end(village_id: str, member_id: str) -> datetime:
    now = clock.now()
    today = now.date().isoformat()
    dates = sorted({ev["payload"].get("date") for ev in db.events
                    if ev.get("village", village_id) == village_id and ev["kind"] == "shift"
                    and ev.get("payload", {}).get("on_duty") == member_id and str(ev["payload"].get("date", "")) < today})
    if dates:
        try:
            d = datetime.fromisoformat(f"{dates[-1]}T21:30:00").replace(tzinfo=now.tzinfo)
            return d
        except ValueError:
            pass
    return now - timedelta(hours=24)


def events_since_last_turn(village_id: str, member_id: str | None) -> list[dict[str, Any]]:
    if not member_id:
        return []
    since = _last_turn_end(village_id, member_id)
    recipient = villages.care_recipient_id(village_id)
    word_en, word_es = _word(village_id, recipient, "en"), _word(village_id, recipient, "es")
    lines: list[dict[str, Any]] = []

    def after(at: Any) -> bool:
        try:
            return datetime.fromisoformat(str(at)) >= since
        except ValueError:
            return False

    for ev in db.events:
        if ev.get("village", village_id) != village_id or not after(ev.get("at")):
            continue
        kind, p = ev["kind"], ev.get("payload", {})
        if kind == "ack" and p.get("status") in (None, "got_it", "accepted"):
            lines.append({"at": ev["at"], "text": {"en": f"{word_en} answered the check-in", "es": f"{word_es} contestó la llamada de control"}})
        elif kind in {"verification_denied", "verification_timeout"}:
            lines.append({"at": ev["at"], "text": {"en": "Village stopped a scam call", "es": "Village detuvo una llamada de estafa"}})
        elif kind == "dose" and p.get("subject") == recipient and p.get("slot"):
            lines.append({"at": ev["at"], "text": {"en": f"{word_en}'s {p['slot']} pills taken", "es": f"{word_es} tomó las pastillas ({p['slot']})"}})
    for d in db.decisions:
        if d.get("village", d.get("village_id", village_id)) != village_id or not after(d.get("at")):
            continue
        gate = d.get("gate") if isinstance(d.get("gate"), dict) else d
        if gate.get("decision") == "ask_family" and member_id in str(gate.get("data") or gate.get("refs") or member_id):
            lines.append({"at": d.get("at"), "text": {"en": f"{word_en} asked you to call tonight", "es": f"{word_es} pidió que la llames esta noche"}})
    lines.sort(key=lambda r: str(r["at"]), reverse=True)
    return lines[:3]


# ---- (6) proposal extras --------------------------------------------------------------------------

PROPOSAL_EXTRAS = ("rationale", "stays_the_same", "checked", "allow_ask_other", "release_stage", "asked_other")


def proposal_extras(proposal: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"proposal_id": proposal["id"]}
    for key in PROPOSAL_EXTRAS:
        if proposal.get(key) is not None:
            out[key] = proposal[key]
    return out
