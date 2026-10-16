"""D39/ASKS-2: when someone is needed, Village asks the PEOPLE concerned, in ONE thread message.

"I need someone to cover for <on-duty> tomorrow" → the on-duty person is out: ask the eligible others
(not on duty, not the asker, available that day). "need someone tomorrow" → ask the on-duty person and a
cover. One `kind: answer` message carries the facts + question(s) and the asks as refs
`{kind: "ask", id, member, answered, answered_at}`; each asked phone gets `prompt{kind: ask}`. Answers
(app action, HTTP, a demo actor's reply with `refs:[{kind: ask, id}]`) update the ask and re-send the
message (same id) so the kit shows "<on-duty>: can't · <cover>: can do". A cover's yes (with the on-duty
person out) → Village writes the `shift` itself. The leader is asked only on timeout or disagreement."""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

ASKS: dict[str, dict[str, Any]] = {}  # group id → ask group
BY_MEMBER_ASK: dict[str, tuple[str, str]] = {}  # member ask id → (group id, member)
TASKS: set[asyncio.Task] = set()
DAY_ABBR = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}


def real_now() -> str:
    """Live chat rows use wall time, not the warped demo clock."""
    return datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")


def timeout_s() -> float:
    try:
        return float(os.getenv("ASK_TIMEOUT_S", "20"))
    except ValueError:
        return 20.0


def _spawn(coro: Any) -> asyncio.Task:
    t = asyncio.get_running_loop().create_task(coro)
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)
    try:
        from core import services

        services._CHAT_TASKS.add(t)
        t.add_done_callback(services._CHAT_TASKS.discard)
    except Exception:
        pass
    return t


def excluded_members(village_id: str, text: str) -> set[str]:
    """Members the message already rules out: "cover for <name>", "<name> can't", "<name> is out"."""
    from core import village as villages
    from .conversation import fold

    out = set()
    ft = fold(text)
    for p in villages.people(village_id):
        first = fold(p["name"].split()[0])
        if re.search(rf"\b(cover|covering|fill in|sub) for {first}\b|\b{first} (can'?t|cannot|is out|isn'?t (available|free)|won'?t be|is sick|has to work)\b|\binstead of {first}\b", ft):
            out.add(p["id"])
    return out


def eligible_covers(village_id: str, day: str, *, exclude: set[str]) -> list[str]:
    from core import village as villages

    abbr = DAY_ABBR.get(day, day[:3])
    out = []
    coord = villages.coordinator_id(village_id)
    for p in villages.people(village_id):
        if p["id"] in exclude or p.get("role") == "care_recipient" or not (p.get("view") or p.get("phone")):
            continue
        if p.get("role") not in ("caregiver", "professional_caregiver", "coordinator", "volunteer"):
            continue
        avail = (p.get("profile") or {}).get("availability") or []
        if avail and not any(abbr in a.get("days", []) for a in avail):
            continue
        out.append(p["id"])
    out.sort(key=lambda m: m == coord)  # the leader last
    return out


def _ref(gid: str, member: str, ask: dict[str, Any]) -> dict[str, Any]:
    a = ask["answers"].get(member)
    return {"kind": "ask", "id": ask["member_ask"][member], "member": member, "label": ask["questions"][member][:80],
            "answered": a["answer"] if a else None, "answered_at": a["at"] if a else None}


def _summary(ask: dict[str, Any]) -> str:
    bits = []
    for m in ask["asked"]:
        a = ask["answers"].get(m)
        word = "can do" if a and a["answer"] == "yes" else ("can't" if a else "asked")
        if m == ask["on_duty"] and a:
            word = "still on" if a["answer"] == "yes" else "can't"
        bits.append(f"{ask['names'][m]}: {word}")
    return " · ".join(bits)


async def start_need(village_id: str, message: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from core import village as villages

    text, asker = message.get("text", ""), message.get("author")
    on, day, when = ctx["on_duty"], ctx["day"], ctx["when"]
    out = excluded_members(village_id, text)
    on_out = on in out
    covers = eligible_covers(village_id, day, exclude=out | {on, asker})
    names = {m: villages.first_name(village_id, m) for m in [on] + covers if m}
    asked = ([] if on_out else [on]) + covers[: (3 if on_out else 1)]
    gid = f"ask_{uuid.uuid4().hex[:8]}"
    questions: dict[str, str] = {}
    if not on_out:
        questions[on] = f"{names[on]}, still good?"
    for c in asked:
        if c != on:
            questions[c] = f"{names[c]}, can you cover?" if on_out else f"{names[c]}, can you cover if not?"
    facts = f"{when}'s {day}, {names.get(on, 'nobody')}'s night."
    body = " ".join([facts] + [questions[m] for m in asked]) if asked else f"{facts} Nobody else is free that day."
    ask = {"id": gid, "village": village_id, "date": ctx["date"], "day": day, "on_duty": on, "on_duty_out": on_out, "asker": asker,
           "asked": asked, "names": names, "questions": questions, "answers": {}, "status": "open", "center_word": ctx.get("center_word", ""),
           "member_ask": {m: f"{gid}_{m}" for m in asked}, "message_id": None, "reply_to": message.get("id")}
    for m in asked:
        BY_MEMBER_ASK[ask["member_ask"][m]] = (gid, m)
    ASKS[gid] = ask
    msg = await post(village_id, kind="answer", text=body, refs=[_ref(gid, m, ask) for m in asked] or [{"kind": "member", "id": on}], reply_to=message.get("id"))
    ask["message_id"] = msg["id"]
    for m in asked:
        await push_prompt(village_id, m, ask["member_ask"][m], questions[m])
    try:
        from .actors import on_ask

        for m in asked:
            on_ask(village_id, ask["member_ask"][m], m, role="on_duty" if m == on else "cover")
    except Exception:
        pass
    if not asked:
        await _ask_leader(ask)
    else:
        _spawn(_window(gid))
    return ask


async def post(village_id: str, *, kind: str, text: str, refs: list[dict[str, Any]], reply_to: str | None = None, author: str = "village",
               source: dict[str, Any] | None = None) -> dict[str, Any]:
    """One chat row with wall-clock `at` (live post), fanned out like core's post_message."""
    from core import services
    from core.db import db

    message = {"id": services._message_id(), "village": village_id, "author": author, "kind": kind, "text": text[:2000], "mention": None,
               "reply_to": reply_to, "refs": [r for r in refs if not (r.get("kind") == "source" and not r.get("label"))][:12], "source": source or {"kind": "system", "ref": "builder"}, "at": real_now()}
    services._MESSAGE_LOG.append(message)
    await db.create_message(message)
    return message


async def _refresh(ask: dict[str, Any]) -> None:
    """Re-send the ask message (same id) with updated refs + the one-line status."""
    from core.db import db

    row = next((m for m in db.messages if m.get("id") == ask["message_id"]), None)
    if row is None:
        return
    row["refs"] = [_ref(ask["id"], m, ask) for m in ask["asked"]][:12]
    row["text_i18n"] = {"en": row["text"].split(" — ")[0] + " — " + _summary(ask), "es": row["text"].split(" — ")[0] + " — " + _summary(ask)}
    await db.publish("message", row)


async def push_prompt(village_id: str, member: str, member_ask_id: str, question: str) -> None:
    try:
        from core.ws_hub import hub

        frame = {"type": "prompt", "kind": "ask", "ask_id": member_ask_id, "question": {"en": question, "es": question},
                 "options": [{"id": "yes", "label": {"en": "Yes", "es": "Sí"}}, {"id": "no", "label": {"en": "Can't", "es": "No puedo"}}]}
        for c in list(hub.clients):
            if c.village == village_id and c.member_id == member and not c.view_as:
                try:
                    await c.ws.send_json(frame)
                except Exception:
                    hub.disconnect(c.ws)
    except Exception:
        pass


async def answer(ask_id: str, member: str, value: str) -> dict[str, Any]:
    """ask_id = a member ask id (from the prompt/ref) or the group id (then `member` picks the row)."""
    gid, m = BY_MEMBER_ASK.get(ask_id, (ask_id, member))
    ask = ASKS.get(gid)
    if ask is None:
        raise KeyError("unknown ask")
    if member != m or m not in ask["asked"]:
        raise PermissionError("not asked")
    if m in ask["answers"]:
        return ask
    ask["answers"][m] = {"answer": "yes" if str(value).lower() in ("yes", "si", "sí", "y", "true") else "no", "at": real_now()}
    await _refresh(ask)
    if ask["status"] == "open":
        await _resolve(ask, final=False)
    return ask


async def _resolve(ask: dict[str, Any], *, final: bool) -> None:
    if ask.get("type") == "plan":
        from .plan_need import resolve_plan

        await resolve_plan(ask, final=final)
        return
    on = ask["on_duty"]
    a = {m: v["answer"] for m, v in ask["answers"].items()}
    covers = [m for m in ask["asked"] if m != on]
    if not ask["on_duty_out"] and a.get(on) == "yes":
        ask["status"] = "resolved"
        await post(ask["village"], kind="answer", text=f"{ask['names'][on]}'s still on for {ask['day']}. Nothing changes.", refs=[{"kind": "member", "id": on}])
        return
    yes = next((c for c in covers if a.get(c) == "yes"), None)
    on_clear = ask["on_duty_out"] or a.get(on) == "no" or final
    if yes and on_clear:
        await write_swap(ask, yes)
        return
    everyone_no = all(a.get(m) == "no" for m in ask["asked"])
    if final or everyone_no:
        await _ask_leader(ask)


async def _ask_leader(ask: dict[str, Any]) -> None:
    from core import village as villages

    vid = ask["village"]
    ask["status"] = "escalated"
    coord = villages.coordinator_id(vid)
    coord_name = villages.first_name(vid, coord, "the leader")
    silent = [ask["names"][m] for m in ask["asked"] if m not in ask["answers"]]
    if silent:
        lead = f"No answer from {' or '.join(reversed(silent))}."
    elif ask["asked"]:
        lead = f"{' and '.join(ask['names'][m] for m in ask['asked'])} can't."
    else:
        lead = "Nobody else is free that day."
    q = f"{lead} {coord_name}, want me to keep asking or take {ask['day']} yourself?"
    await post(vid, kind="nudge", text=q, refs=[{"kind": "member", "id": coord, "label": coord_name}])


async def write_swap(ask: dict[str, Any], cover: str) -> dict[str, Any]:
    from core import services

    vid, on = ask["village"], ask["on_duty"]
    ask["status"] = "resolved"
    ev = await services.record_event(vid, {"kind": "shift", "payload": {"date": ask["date"], "on_duty": cover, "backup": on, "change": "swapped"}},
                                     actor=cover, source={"kind": "app", "ref": cover})
    ask["event_id"] = ev["id"]
    center = ask.get("center_word") or "they"
    text = f"{ask['day']}: {ask['names'][cover]} covers for {ask['names'][on]}. {center[:1].upper() + center[1:]} will be told at her check-in."
    await post(vid, kind="answer", text=text, refs=[{"kind": "event", "id": ev["id"], "label": "rota"}, {"kind": "member", "id": cover}])
    return ev


async def _window(gid: str) -> None:
    await asyncio.sleep(timeout_s())
    ask = ASKS.get(gid)
    if ask and ask["status"] == "open":
        await _resolve(ask, final=True)
