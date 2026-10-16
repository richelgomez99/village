"""D38 demo actors: family members played by the system in the chat, always labelled.

`DEMO_ACTORS=<first names or member ids>` (or POST /admin/demo-actors) names members; when Village asks one of them
(an ask/nudge), after 3–6 s they reply in character ("[demo] Sure, I can take Saturday.") and answer
the ask. Never: verification prompts, the leader's approvals. Message marks: `source.kind: system`,
`refs` include `{kind: member, id}`, text prefixed "[demo] " (message schema has no demo flag)."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any

_RUNTIME: set[str] | None = None
CANNED = {
    "cover_yes": ["Sure, I can take {day}.", "Yes, I've got {day}.", "Okay, {day} is mine.", "I can do {day}, no problem."],
    "on_duty_no": ["Can't this time, sorry. Work.", "I can't {day}, sorry.", "Not this {day}, something came up.", "Can't make it {day}."],
}


def actors() -> set[str]:
    if _RUNTIME is not None:
        return set(_RUNTIME)
    return {a.strip().lower() for a in os.getenv("DEMO_ACTORS", "").split(",") if a.strip()}


def set_actors(names: list[str] | None) -> set[str]:
    global _RUNTIME
    _RUNTIME = {n.strip().lower() for n in (names or []) if n.strip()}
    return set(_RUNTIME)


def _is_actor(village_id: str, member: str) -> bool:
    from core import village as villages
    from .conversation import fold

    names = actors()
    if not names or member == villages.coordinator_id(village_id):  # never the leader
        return False
    first = fold(villages.first_name(village_id, member, ""))
    return member in names or first in names or member.removeprefix("m_") in names


def delay_s() -> float:
    v = os.getenv("DEMO_ACTOR_DELAY_S")
    return float(v) if v is not None else random.uniform(3, 6)


def on_ask(village_id: str, ask_id: str, member: str, *, role: str) -> None:
    if not _is_actor(village_id, member):
        return
    from .asks import _spawn

    _spawn(_reply(village_id, ask_id, member, role))


async def _reply(village_id: str, ask_id: str, member: str, role: str) -> None:
    from core import services
    from . import asks

    await asyncio.sleep(delay_s())
    gid = asks.BY_MEMBER_ASK.get(ask_id, (ask_id, member))[0]
    ask = asks.ASKS.get(gid)
    if not ask or ask["status"] != "open":
        return
    key = "cover_yes" if role == "cover" else "on_duty_no"
    line = random.choice(CANNED[key]).format(day=ask["day"])
    gid = asks.BY_MEMBER_ASK.get(ask_id, (ask_id, member))[0]
    await asks.post(village_id, author=member, kind="chat", text=f"[demo] {line}", refs=[{"kind": "member", "id": member}, {"kind": "ask", "id": ask_id}],
                    source={"kind": "system", "ref": "demo_actor"}, reply_to=(asks.ASKS.get(gid) or {}).get("message_id"))
    await asks.answer(ask_id, member, "yes" if role == "cover" else "no")
