from __future__ import annotations

from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db


def _v(village_id: str | None) -> str:
    return village_id or villages.default_village_id()


def _recipient(village_id: str | None) -> str | None:
    return villages.care_recipient_id(_v(village_id))


def _shift(village_id: str | None = None) -> dict[str, Any] | None:
    vid = _v(village_id)
    return next((ev for ev in reversed(db.events) if ev["kind"] == "shift" and ev.get("village", vid) == vid), None)


def _on_duty(village_id: str | None = None) -> str | None:
    shift = _shift(village_id)
    return (shift["payload"].get("on_duty") if shift else None) or villages.default_on_duty(_v(village_id))


def all_view_binds(village_id: str | None = None) -> set[str]:
    """Every bind any view of the village uses (the Control Room renders all of them)."""
    vid = _v(village_id)
    roles = set(db.specs.get(vid, {}).get("views", {})) | {r for (v, r) in db.views if v == vid}
    out: set[str] = set()
    for r in roles:
        out |= view_binds(r, vid)
    return out


def view_binds(role: str, village_id: str | None = None) -> set[str]:
    if role == "control":
        return {"*"}
    view = db.views.get((_v(village_id), role)) or db.specs.get(_v(village_id), {}).get("views", {}).get(role, {})
    binds: set[str] = set()
    for element in view.get("elements", {}).values():
        bind = element.get("props", {}).get("bind")
        if bind:
            binds.add(bind)
    return binds


def _ids_in(node: Any, ids: set[str], out: list[str]) -> None:
    if isinstance(node, str):
        if node in ids and node not in out:
            out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            _ids_in(value, ids, out)
    elif isinstance(node, list):
        for value in node:
            _ids_in(value, ids, out)


def call_targets(role: str, village_id: str | None = None) -> list[str]:
    """Members a view can call: elder -> coordinator; helper/coordinator -> care recipient; control -> everyone;
    plus any member id the view itself references (BigButton action_arg etc.)."""
    vid = _v(village_id)
    people = [p["id"] for p in villages.people(vid) if p.get("id")]
    if role == "control":
        return people
    out: list[str] = []
    first = villages.coordinator_id(vid) if role == "elder" else villages.care_recipient_id(vid)
    if first:
        out.append(first)
    _ids_in(db.views.get((vid, role)) or db.specs.get(vid, {}).get("views", {}).get(role, {}), set(people), out)
    return out


def member_record(member_id: str, village_id: str | None = None) -> dict[str, Any]:
    """`member:<id>` value: bv_person (member_id, name, phone) + id/display_name/role for call buttons."""
    vid = _v(village_id)
    person = villages.person(vid, member_id) or db.members.get(member_id) or {}
    name = str(person.get("name") or member_id)
    rec: dict[str, Any] = {"member_id": member_id, "id": member_id, "name": name.split()[0], "display_name": name,
                           "role": person.get("role", "member")}
    phone = villages.member_phone(vid, member_id)
    if phone:
        rec["phone"] = phone
    return rec


def _slot_meds(slot: str, village_id: str | None = None) -> list[str]:
    meds = []
    for med in _family(village_id).get("medications", []):
        if med.get("valid_until") or med.get("status") == "superseded":
            continue
        if any(entry.get("slot") == slot for entry in med.get("schedule", [])):
            meds.append(f"{med['name']} {med.get('dose', '')}".strip())
    return meds


def dose_day(subject: str | None = None, *, show_med_names: bool = False, date: str | None = None, village_id: str | None = None) -> dict[str, Any]:
    """bv_dose_day: {date, slots: [bv_dose_slot]}; slot `meds` only for views with med names (never elder)."""
    subject = subject or _recipient(village_id)
    day = date or clock.now().date().isoformat()
    now_hhmm = clock.now().strftime("%H:%M")
    slots = []
    for slot, due in (("morning", "08:00"), ("evening", "19:30")):
        event = next(
            (
                ev for ev in reversed(db.events)
                if ev["kind"] == "dose"
                and ev["payload"].get("subject") == subject
                and ev["payload"].get("slot") == slot
                and str(ev["payload"].get("taken_at") or ev.get("at", "")).startswith(day)
            ),
            None,
        )
        if event:
            status = "uncertain" if event["payload"].get("confidence") == "uncertain" else "taken"
        elif day < clock.now().date().isoformat():
            status = "missed"
        else:
            status = "due" if now_hhmm >= due else "upcoming"
        via = event["payload"].get("via") if event else None
        item: dict[str, Any] = {
            "slot": slot,
            "status": status,
            "taken_at": event["payload"].get("taken_at") if event else None,
            "via": via if via in {"lid_qr", "phone_line", "app"} else None,
        }
        if show_med_names:
            item["meds"] = _slot_meds(slot, village_id)
        slots.append(item)
    return {"date": day, "slots": slots}


def dose_week(subject: str | None = None, *, show_med_names: bool = False, village_id: str | None = None) -> dict[str, Any]:
    from datetime import timedelta as _td

    today = clock.now().date()
    return {"days": [dose_day(subject, show_med_names=show_med_names, date=(today - _td(days=n)).isoformat(), village_id=village_id) for n in range(6, -1, -1)]}


def _person(member_id: str | None) -> dict[str, Any] | None:
    if not member_id:
        return None
    return {"member_id": member_id, "name": str(db.members.get(member_id, {}).get("name", member_id)).split()[0]}


def _next_shift(member_id: str, after: str, village_id: str | None = None) -> str | None:
    week = _family(village_id).get("care_rota", {}).get("week_of_2026-10-12", [])
    later = [day["date"] for day in week if day.get("on_duty") == member_id and day["date"] > after]
    return later[0] if later else None


def rota_me(member_id: str, village_id: str | None = None) -> dict[str, Any]:
    shift = _shift(village_id)
    on_duty = (shift["payload"].get("on_duty") if shift else None) or villages.default_on_duty(_v(village_id))
    backup = (shift["payload"].get("backup") if shift else None) or villages.default_backup(_v(village_id))
    date = shift["payload"].get("date") if shift else clock.now().date().isoformat()
    mine = member_id == on_duty
    name = _person(on_duty)["name"]
    return {
        "is_my_turn": mine,
        "date": date,
        "on_duty": _person(on_duty),
        "backup": _person(backup),
        "until": None,
        "next_shift": _next_shift(member_id, date, village_id),
        "answer": {"en": "Yes. Tonight until 9:30. Nothing to do unless Village calls you." if mine else f"No. {name} is on tonight."},
    }


def _family(village_id: str | None = None) -> dict[str, Any]:
    """The village's data file from data/villages/index.json (meds, rota); {} if it has none."""
    return villages.village_data(_v(village_id))


def _dose_mg(dose: str) -> float | None:
    try:
        return float(dose.lower().replace("mg", "").strip())
    except ValueError:
        return None


def prescriptions_current(subject: str | None = None, village_id: str | None = None) -> dict[str, Any]:
    """bv_prescriptions (contract 1.2.0, D22): current meds from the village data file, with supersession
    from med_change ledger rows. Never bound on the elder view."""
    subject = subject or _recipient(village_id)
    family = _family(village_id)
    changes = {
        ev["payload"]["to"]["med_id"]: ev
        for ev in db.events
        if ev["kind"] == "med_change" and ev["payload"].get("subject", subject) == subject and ev["payload"].get("to")
    }
    changed_items: list[dict[str, Any]] = []
    other_items: list[dict[str, Any]] = []
    for med in family.get("medications", []):
        if med.get("valid_until") or med.get("status") == "superseded":
            continue
        dose = str(med.get("dose", ""))
        item: dict[str, Any] = {
            "med_id": med["id"],
            "name": med["name"],
            "dose_text": dose,
            "schedule": [slot["slot"] for slot in med.get("schedule", [])] or ["morning"],
            "valid_from": med.get("valid_from") or "2026-01-01",
        }
        mg = _dose_mg(dose)
        if mg:
            item = {"med_id": item["med_id"], "name": item["name"], "dose_mg": int(mg) if mg.is_integer() else mg, **{k: v for k, v in item.items() if k not in {"med_id", "name"}}}
        change = changes.get(med["id"])
        if change:
            payload = change["payload"]
            item["changed_by"] = "Dr. Park"
            item["superseded"] = {"dose_text": payload["from"]["dose"], "valid_until": payload.get("effective", item["valid_from"])}
            item["source"] = change["source"]
            caller = _member_name(change.get("actor") if str(change.get("actor", "")).startswith(("m_", "b_")) else villages.coordinator_id(_v(village_id)) or "")
            item["source_label"] = {"en": f"{caller}'s call, Oct 3", "es": f"Llamada de {caller}, 3 oct"}
            changed_items.append(item)
        else:
            other_items.append(item)
    owner = _on_duty(village_id)
    today = clock.now().date()
    days_to_friday = (4 - today.weekday()) % 7
    from datetime import timedelta as _td

    return {
        "subject": subject,
        "refill_day": "Fri",
        "next_refill": (today + _td(days=days_to_friday)).isoformat(),
        "owner_member_id": owner,
        "owner_name": str(db.members.get(owner, {}).get("name", owner)).split()[0],
        "items": changed_items + other_items,
    }


def scams_stopped_today(village_id: str | None = None) -> int:
    """Money verifications stopped today in this village: denied / late_denied / timed_out, from ledger rows
    (verification_denied / verification_timeout events, so it survives reconnects and replays) and live rows."""
    vid = _v(village_id)
    today = clock.now().date().isoformat()
    ids = {ev.get("payload", {}).get("verification_id") or ev["id"] for ev in db.events
           if ev["kind"] in {"verification_denied", "verification_timeout"} and ev.get("village", vid) == vid
           and str(ev.get("at", "")).startswith(today)}
    ids |= {row["id"] for row in db.verifications.values()
            if row.get("village", vid) == vid and row.get("state") in {"denied", "late_denied", "timed_out"}
            and str(row.get("resolved_at") or row.get("created_at") or "").startswith(today)}
    return len(ids)


_DAY_EN = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}
_DAY_ES = {"Mon": "el lunes", "Tue": "el martes", "Wed": "el miércoles", "Thu": "el jueves", "Fri": "el viernes", "Sat": "el sábado", "Sun": "el domingo"}
_SLOT_ES = {"morning": "mañana", "evening": "noche"}
_AREA_WORD = {"health": "Pills", "money": "Money", "people": "People"}


def life_areas(village_id: str | None = None) -> list[dict[str, Any]]:
    """Plain words per life area, computed from events in the village's own vocabulary (core.bindings_live);
    the label carries the area word ("Pills: …"), the status is the line ("morning taken · refill Friday · Marco")."""
    from core.bindings_live import area_word, life_area_status

    vid = _v(village_id)
    spec = db.specs.get(vid) or villages.spec(vid)
    out = []
    for area in spec.get("blueprint", {}).get("life_areas", []):
        label = str(area.get("label", area["id"]))
        if ":" in label:  # the village's own area word leads ("Health: pills" -> "Pills: pills"; a phrase keeps its head)
            label = f"{area_word(area)}: {label.split(':', 1)[1].strip()}"
        item: dict[str, Any] = {"id": area["id"], "label": label, "status": life_area_status(vid, area, spec)}
        if area.get("rules"):
            item["rules"] = area["rules"]
        if area.get("trusted_contacts"):
            item["trusted_contacts"] = area["trusted_contacts"]
        # 1.3.3: the needs this area serves, so the kit derives each person's tabs (spec order, no duplicates)
        need_ids = list(area.get("need_ids") or area.get("needs") or [])
        for need in spec.get("blueprint", {}).get("needs", []):
            if (need.get("life_area") or need.get("area")) == area["id"] and need.get("id") and need["id"] not in need_ids:
                need_ids.append(need["id"])
        item["need_ids"] = [str(n.get("id") if isinstance(n, dict) else n) for n in need_ids]
        out.append(item)
    return out


def on_duty_person(village_id: str | None = None) -> dict[str, Any]:
    on_duty = _on_duty(village_id)
    return {"member_id": on_duty, "name": str(db.members.get(on_duty, {}).get("name", on_duty)).split()[0]}


def rota_week(village_id: str | None = None) -> list[dict[str, Any]]:
    week = _family(village_id).get("care_rota", {}).get("week_of_2026-10-12", [])
    days = {day["date"]: dict(day) for day in week}
    for ev in db.events:  # ledger shift rows override the planned rota
        if ev["kind"] == "shift" and ev["payload"].get("date") in days:
            days[ev["payload"]["date"]].update({k: ev["payload"][k] for k in ("on_duty", "backup") if ev["payload"].get(k)})
    return [{"date": d["date"], "day": d["day"], "on_duty": d["on_duty"], "backup": d["backup"]} for d in days.values()]


_TIMELINE_TEXT = {
    "med_change": lambda p: {"en": f"{p.get('med', 'med')} changed {p.get('from', {}).get('dose', '')} → {p.get('to', {}).get('dose', '')}", "es": f"{p.get('med', 'med')} cambió {p.get('from', {}).get('dose', '')} → {p.get('to', {}).get('dose', '')}"},
    "dose": lambda p: {"en": f"{p.get('slot', '')} pills taken", "es": f"pastillas ({p.get('slot', '')}) tomadas"},
    "money_request": lambda p: {"en": f"Money request in {p.get('claimed_identity', 'someone')}'s name", "es": f"Pedido de dinero a nombre de {p.get('claimed_identity', 'alguien')}"},
    "incident": lambda p: p.get("title") or {"en": "Incident", "es": "Incidente"},
    "verification_denied": lambda p: {"en": "Real contact said it wasn't them", "es": "El contacto real dijo que no fue"},
    "verification_timeout": lambda p: {"en": "Could not confirm in time", "es": "No se pudo confirmar a tiempo"},
    "verification_confirmed": lambda p: {"en": "Real contact confirmed", "es": "El contacto real confirmó"},
}


def _dose_text(payload: dict[str, Any], village_id: str | None) -> dict[str, str]:
    """Slot words come from the village data file (dose_slots[slot].spoken_es), never from code."""
    out = _TIMELINE_TEXT["dose"](payload)
    spoken = (_family(village_id).get("dose_slots", {}).get(payload.get("slot", "")) or {}).get("spoken_es")
    if spoken:
        out = {**out, "es": f"{spoken.split(' (')[0].removeprefix('las ')} tomadas"}
    return out


def timeline(subject: str | None = None, limit: int = 30, village_id: str | None = None) -> list[dict[str, Any]]:
    subject = subject or _recipient(village_id)
    superseded_meds = {ev["payload"].get("from", {}).get("med_id") for ev in db.events if ev["kind"] == "med_change"}
    items = []
    for ev in db.events:
        text_fn = _TIMELINE_TEXT.get(ev["kind"])
        payload = ev.get("payload", {})
        if text_fn is None or payload.get("subject", subject) != subject or not ev.get("source"):
            continue
        items.append({
            "event_id": ev["id"],
            "kind": ev["kind"],
            "at": ev["at"],
            "text": _dose_text(payload, village_id) if ev["kind"] == "dose" else text_fn(payload),
            "source": ev["source"],
            "superseded": ev["kind"] == "med_change" and payload.get("to", {}).get("med_id") in superseded_meds,
        })
    return items[-limit:]


def with_source_labels(message: dict[str, Any]) -> dict[str, Any]:
    """Village posts: a ref (or the post's source) that comes from a call is labelled as that call, e.g.
    "from her check-in call" (the center person has no app, so never "from her phone")."""
    if message.get("author") not in {"village", "system"}:
        return message
    vid = message.get("village")
    recipient = villages.care_recipient_id(vid)
    poss = {"she": "her", "he": "his"}.get(villages.pronoun(villages.person(vid, recipient)), "their")
    events = {ev["id"]: ev for ev in db.events if ev.get("village", vid) == vid}

    def call_label(src: dict[str, Any] | None, actor: str | None = None) -> str | None:
        if not isinstance(src, dict) or src.get("kind") != "call":
            return None
        whose = poss if actor in (None, recipient) else "the"
        return f"from {whose} check-in call"

    out = dict(message)
    refs = []
    for ref in message.get("refs") or []:
        ref = dict(ref)
        ev = events.get(ref.get("id")) if ref.get("kind") == "event" else None
        label = call_label(ev.get("source"), ev.get("actor")) if ev else (call_label({"kind": "call"}) if ref.get("kind") == "call" else None)
        if label:  # a call-sourced event is always "from her check-in call", whatever the post said
            ref["label"] = label
        elif ev and ref.get("label", "").startswith("from") and ev.get("actor") == recipient and "phone" in ref.get("label", ""):
            ref["label"] = {"scan": f"from {poss} pill organizer"}.get((ev.get("source") or {}).get("kind"), ref["label"])
        refs.append(ref)
    out["refs"] = refs  # message.source is additionalProperties:false, so the label rides on the ref chips only
    return out


def snapshot_data(role: str, member_id: str | None, village_id: str | None = None) -> dict[str, Any]:
    vid = _v(village_id)
    binds = view_binds(role, vid)
    subject = _recipient(vid)
    if role == "control":
        # Control Room three-phones region renders the default verifier's per-member cards
        member_id = member_id or villages.default_verifier(vid) or villages.default_on_duty(vid)
    data: dict[str, Any] = {}
    if "*" in binds or "alerts:active" in binds:
        data["alerts:active"] = active_alerts(role, vid)
    if member_id and ("*" in binds or "verifications:pending?member=me" in binds):
        data["verifications:pending?member=me"] = pending_verification_prompt(member_id)
    if member_id and ("*" in binds or "verifications:mine" in binds):
        data["verifications:mine"] = my_verification(member_id)
    if "*" in binds or "incidents:open" in binds:
        data["incidents:open"] = open_incidents(vid)
    if subject:
        today_key = f"facts:dose_event?subject={subject}&valid_at=today"
        week_key = f"facts:dose_event?subject={subject}&valid_at=week"
        if "*" in binds or today_key in binds:
            data[today_key] = dose_day(subject, show_med_names=role != "elder", village_id=vid)
        if "*" in binds or week_key in binds:
            data[week_key] = dose_week(subject, show_med_names=role != "elder", village_id=vid)
    if member_id and ("*" in binds or "rota:current?member=me" in binds):
        data["rota:current?member=me"] = rota_me(member_id, vid)
    if "*" in binds or "blueprint:life_areas" in binds:
        data["blueprint:life_areas"] = life_areas(vid)
    if "*" in binds or "rota:week" in binds:
        data["rota:week"] = rota_week(vid)
    if subject and ("*" in binds or f"timeline:subject={subject}" in binds):
        data[f"timeline:subject={subject}"] = timeline(subject, village_id=vid)
    if "*" in binds or "rota:current.on_duty" in binds:
        data["rota:current.on_duty"] = on_duty_person(vid)
    if subject and role != "elder" and ("*" in binds or "prescriptions:current" in binds):
        data["prescriptions:current"] = prescriptions_current(subject, vid)
    for target in call_targets(role, vid):
        data[f"member:{target}"] = member_record(target, vid)
    if "*" in binds or "proposals:pending" in binds:
        data["proposals:pending"] = proposals_pending(vid)
    if role != "elder":  # chat:village for every non-elder socket, bound or not (VillageChat lands with V2 views)
        data["chat:village"] = [with_source_labels(m) for m in db.messages if m.get("village", vid) == vid][-50:]
        for author in {m.get("author") for m in data["chat:village"]}:
            if author and f"member:{author}" not in data and villages.person(vid, author):
                data[f"member:{author}"] = member_record(author, vid)
    from core import bindings_live as live
    from core import bindings_v3

    data.update(bindings_v3.resolve_all(all_view_binds(vid) if role == "control" else binds, vid))

    if role in {"coordinator", "control"} or "rounds:latest" in binds:
        data["rounds:latest"] = live.rounds_latest(vid)
    if member_id and (role == "helper" or "events:since_last_turn?member=me" in binds):
        data["events:since_last_turn?member=me"] = live.events_since_last_turn(vid, member_id)
    if "*" in binds or "proposals:pending" in binds:
        try:
            data.update(proposal_details(vid))
        except Exception:
            pass
    return data


PENDING_PROPOSAL_STATUSES = {"proposed", "ready", "verifying"}


def proposals_pending(village_id: str | None = None) -> list[dict[str, Any]]:
    """proposals:pending -> [bv_proposal]: open Evolve proposals (proposed | ready | verifying) for the Proposal card."""
    from core.evolve.proposals import bv_row, list_proposals

    vid = _v(village_id)
    return [bv_row(vid, p) for p in list_proposals(vid) if p.get("status") in PENDING_PROPOSAL_STATUSES]


def proposal_details(village_id: str | None = None) -> dict[str, dict[str, Any]]:
    """`proposal:<id>` -> evolve fields bv_proposal can't carry (rationale, stays_the_same, checked, ...)."""
    from core.bindings_live import proposal_extras
    from core.evolve.proposals import list_proposals

    return {f"proposal:{p['id']}": proposal_extras(p) for p in list_proposals(_v(village_id))
            if p.get("status") in PENDING_PROPOSAL_STATUSES}


def changed(event: dict[str, Any], role: str, member_id: str | None = None, village_id: str | None = None) -> dict[str, Any]:
    vid = village_id or event.get("village") or _v(None)
    if event["kind"] in {"verification_pending", "verification_confirmed", "verification_denied", "verification_timeout"}:
        data: dict[str, Any] = {"alerts:active": active_alerts(role, vid)}
        verification_id = event.get("payload", {}).get("verification_id")
        verification = db.verifications.get(verification_id) if verification_id else None
        if member_id and verification and verification.get("claimed_member_id") == member_id:
            data["verifications:pending?member=me"] = pending_verification_prompt(member_id)
            data["verifications:mine"] = my_verification(member_id)
        binds = view_binds(role, vid)
        if verification and verification.get("origin") == "screen_caller":  # a screened call moved: held -> passed/refused
            from core.bindings_v3 import screened_calls

            if "*" in binds or "calls:screened" in binds:
                data["calls:screened"] = screened_calls(vid)
        if event["kind"] in {"verification_denied", "verification_timeout"}:
            if "*" in binds or "incidents:open" in binds:
                data["incidents:open"] = open_incidents(vid)
            if "*" in binds or "blueprint:life_areas" in binds:
                data["blueprint:life_areas"] = life_areas(vid)
        return data
    if event["kind"] in {"incident", "ack"}:
        data = {"incidents:open": open_incidents(vid)}
        if event["kind"] == "incident":
            data["alerts:active"] = active_alerts(role, vid)
            binds = view_binds(role, vid)
            if "*" in binds or "blueprint:life_areas" in binds:
                data["blueprint:life_areas"] = life_areas(vid)
        return data
    if event["kind"] in {"med_change", "shift"} and role != "elder":
        binds = view_binds(role, vid)
        if "*" in binds or "prescriptions:current" in binds:
            return {"prescriptions:current": prescriptions_current(None, vid)}
        return {}
    if event["kind"] == "dose":
        return {
            key: value
            for key, value in snapshot_data(role, member_id, vid).items()
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
        "subject": verification.get("subject") or _recipient(verification.get("village")),
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


def active_alerts(role: str, village_id: str | None = None) -> list[dict[str, Any]]:
    vid = _v(village_id)
    alerts = []
    for verification in db.verifications.values():
        if verification.get("status") not in {"pending", "denied", "timeout"}:
            continue
        if verification.get("village", vid) != vid:
            continue
        claimed_name = _member_name(verification["claimed_member_id"])
        if verification.get("status") == "pending":
            severity = "warn"
            title = {"es": "No mande dinero todavia"} if role == "elder" else {"en": "Possible scam"}
            body = (
                {"es": f"Estamos confirmando con {claimed_name}."}
                if role == "elder"
                else {"en": f"Someone claiming to be {_member_name(verification['claimed_member_id'])} asked for money. Village is checking."}
            )
        elif verification.get("status") == "denied":
            severity = "danger"
            title = {"es": f"Ese no era {claimed_name}"} if role == "elder" else {"en": "Scam stopped"}
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


def open_incidents(village_id: str | None = None) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in db.events:
        if event["kind"] != "incident":
            continue
        if village_id and event.get("village", village_id) != village_id:
            continue
        payload = event["payload"]
        latest[payload["incident_id"]] = event
    incidents = []
    for event in latest.values():
        payload = event["payload"]
        if payload.get("status") in {"closed", "acked"}:  # acknowledged -> incidents:all / timeline only
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
        incidents[-1] = {k: v for k, v in incidents[-1].items() if v is not None}
    if village_id:
        from core.bindings_live import synthesized_incidents

        have = {ev.get("payload", {}).get("verification_id") for ev in db.events
                if ev["kind"] == "incident" and ev.get("village", village_id) == village_id}
        incidents += [{k: v for k, v in i.items() if v is not None} for i in synthesized_incidents(village_id, have)]
    return incidents


def verification_prompt_frame(verification: dict[str, Any], *, closed: bool = False) -> dict[str, Any]:
    frame = {
        "type": "prompt",
        "verification_id": verification["id"],
        "question": _verification_question(verification),
        "detail": _verification_detail(verification),
        "options": [
            {"id": "no", "label": {"en": "That wasn't me", "es": "No fui yo"}},
            {"id": "yes", "label": {"en": "Yes, it was me", "es": "Sí, fui yo"}},
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
    vid = verification.get("village")
    word_en = villages.relationship_word(vid, verification.get("subject") or _recipient(vid), "en")
    word_es = villages.relationship_word(vid, verification.get("subject") or _recipient(vid), "es")
    return {
        "en": f"Did you just call {word_en} asking for {amount_s}?",
        "es": f"¿Acaba de llamar a {word_es} pidiendo {amount_s}?",
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
    vid = event.get("payload", {}).get("verification_id")
    money = next((ev for ev in db.events if ev["kind"] == "money_request" and ev.get("payload", {}).get("verification_id") == vid), None)
    if money and money.get("source"):
        src = money["source"]
        secs = src.get("secs")
        vid = event.get("village")
        word = villages.relationship_word(vid, (verification or {}).get("subject") or _recipient(vid), "en")
        label = f"{word}'s call, at {int(secs) // 60}:{int(secs) % 60:02d}" if isinstance(secs, (int, float)) else f"{word}'s call"
        provenance.append({"label": label, "source": {k: v for k, v in src.items() if k in {"kind", "ref", "secs", "url"}}})
    answered = next((ev for ev in db.events if ev["kind"] in {"verification_denied", "verification_confirmed"} and ev.get("payload", {}).get("verification_id") == vid), None)
    if answered and answered.get("source"):
        name = _member_name(answered["payload"].get("claimed_member_id", ""))
        provenance.append({"label": f"{name} answered in app" if answered["source"].get("kind") == "app" else f"{name} answered", "source": answered["source"]})
    if not provenance and event.get("source"):
        provenance.append({"label": "Village decision", "source": event["source"]})
    return provenance
