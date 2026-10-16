"""D39: when someone is needed, Village asks the PEOPLE concerned (not the leader), in the thread.

need message → Village replies in the thread ("Tomorrow's <day>, <on-duty>'s night. <on-duty>, still good?
<cover>, can you cover if not?") → one `nudge` per person concerned (addressee in refs + text_i18n) →
answers (app action `answer_ask`, POST /villages/{id}/asks/{ask_id}/answer, or a demo actor) →
cover yes + on-duty can't/no answer → Village writes the `shift` event itself and says so. The leader
is asked only when nobody answers within ASK_TIMEOUT_S or people disagree."""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

ASKS: dict[str, dict[str, Any]] = {}
TASKS: set[asyncio.Task] = set()


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


async def start_need(village_id: str, message: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from core import services

    on, cover = ctx["on_duty"], ctx["cover"]
    on_n, cov_n = ctx["on_duty_name"], ctx["cover_name"]
    day, when = ctx["day"], ctx["when"]
    reply = f"{when}'s {day}, {on_n}'s night." + (f" {on_n}, still good? {cov_n}, can you cover if not?" if cover else f" {on_n}, still good?")
    await services.post_message(village_id, author="village", kind="answer", text=reply, refs=[{"kind": "member", "id": m} for m in (on, cover) if m],
                                source={"kind": "system", "ref": "builder"}, reply_to=message.get("id"))
    ask_id = f"ask_{uuid.uuid4().hex[:10]}"
    ask = {"id": ask_id, "village": village_id, "date": ctx["date"], "day": day, "on_duty": on, "cover": cover, "asker": message.get("author"),
           "names": {on: on_n, **({cover: cov_n} if cover else {})}, "answers": {}, "status": "open", "center_word": ctx.get("center_word", "")}
    ASKS[ask_id] = ask
    questions = {on: f"{on_n}, are you still good for {day}?"}
    if cover:
        questions[cover] = f"{cov_n}, can you cover {day} if {on_n} can't?"
    for member, q in questions.items():
        await services.post_message(village_id, author="village", kind="nudge", text=q, refs=[{"kind": "member", "id": member, "label": ask["names"][member]}],
                                    source={"kind": "system", "ref": "builder"}, text_i18n={"en": q, "es": q})
        await push_prompt(village_id, member, ask_id, q)
    try:
        from .actors import on_ask

        for member, q in questions.items():
            on_ask(village_id, ask_id, member, role="on_duty" if member == on else "cover")
    except Exception:
        pass
    _spawn(_window(ask_id))
    return ask


async def push_prompt(village_id: str, member: str, ask_id: str, question: str) -> None:
    """Yes · Can't on the member's phone. Contract 1.3.0 has no ask prompt yet → sent as `chat`-adjacent
    frame `{type: prompt, kind: ask, ask_id, question, options}` only to that member's sockets."""
    try:
        from core.ws_hub import hub

        frame = {"type": "prompt", "kind": "ask", "ask_id": ask_id, "question": {"en": question, "es": question},
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
    ask = ASKS.get(ask_id)
    if ask is None:
        raise KeyError("unknown ask")
    if member not in ask["names"]:
        raise PermissionError("not asked")
    if ask["status"] != "open":
        return ask
    ask["answers"][member] = "yes" if str(value).lower() in ("yes", "si", "sí", "y", "true") else "no"
    await _resolve(ask, final=False)
    return ask


async def _resolve(ask: dict[str, Any], *, final: bool) -> None:
    from core import services

    on, cover = ask["on_duty"], ask["cover"]
    a_on, a_cov = ask["answers"].get(on), ask["answers"].get(cover) if cover else None
    vid = ask["village"]
    if a_on == "yes":
        ask["status"] = "resolved"
        await services.post_message(vid, author="village", kind="answer", text=f"{ask['names'][on]}'s still on for {ask['day']}. Nothing changes.",
                                    refs=[{"kind": "member", "id": on}], source={"kind": "system", "ref": "builder"})
        return
    if a_cov == "yes" and (a_on == "no" or final):
        await write_swap(ask)
        return
    if final or (a_on == "no" and a_cov == "no"):
        ask["status"] = "escalated"
        coord = _coordinator(vid)
        names = " or ".join(ask["names"][m] for m in (cover, on) if m and m not in ask["answers"]) or " and ".join(ask["names"].values())
        lead = f"No answer from {names}." if any(m not in ask["answers"] for m in ask["names"]) else f"{' and '.join(ask['names'].values())} can't."
        coord_name = _first(vid, coord)
        q = f"{lead} {coord_name}, want me to keep asking or take {ask['day']} yourself?"
        await services.post_message(vid, author="village", kind="nudge", text=q, refs=[{"kind": "member", "id": coord, "label": coord_name}],
                                    source={"kind": "system", "ref": "builder"}, text_i18n={"en": q, "es": q})


async def write_swap(ask: dict[str, Any]) -> dict[str, Any]:
    from core import services

    vid, on, cover = ask["village"], ask["on_duty"], ask["cover"]
    ask["status"] = "resolved"
    ev = await services.record_event(vid, {"kind": "shift", "payload": {"date": ask["date"], "on_duty": cover, "backup": on, "change": "swapped"}},
                                     actor=cover, source={"kind": "app", "ref": cover})
    ask["event_id"] = ev["id"]
    center = ask.get("center_word") or "they"
    text = f"{ask['day']}: {ask['names'][cover]} covers for {ask['names'][on]}. {center[:1].upper() + center[1:]} will be told at her check-in."
    await services.post_message(vid, author="village", kind="answer", text=text, refs=[{"kind": "event", "id": ev["id"], "label": "rota"}, {"kind": "member", "id": cover}],
                                source={"kind": "system", "ref": "builder"})
    try:
        from core.ws_hub import hub

        await hub.broadcast_event(ev)
    except Exception:
        pass
    return ev


async def _window(ask_id: str) -> None:
    await asyncio.sleep(timeout_s())
    ask = ASKS.get(ask_id)
    if ask and ask["status"] == "open":
        await _resolve(ask, final=True)


def _coordinator(vid: str) -> str | None:
    from core import village as villages

    return villages.coordinator_id(vid)


def _first(vid: str, mid: str | None) -> str:
    from core import village as villages

    return villages.first_name(vid, mid, "the leader")
