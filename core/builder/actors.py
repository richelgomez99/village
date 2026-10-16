"""D38 demo actors: family members played by the system in the chat, always labelled.

`DEMO_ACTORS=<first names or member ids>` (or POST /admin/demo-actors) names members; when Village asks one of them
(an ask/nudge), after 3–6 s they reply in character ("[demo] Sure, I can take Saturday.") and answer
the ask. With `VILLAGE_LLM_PROVIDER_ACTORS=openai|anthropic` the reply line is written in character by
`core.llm.llm("actors")` (the yes/no decision stays deterministic; any model error/timeout -> the canned line).
Never: verification prompts, the leader's approvals. Message marks: `source.kind: system`,
`refs` include `{kind: member, id}`, text prefixed "[demo] " (message schema has no demo flag)."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any

_RUNTIME: set[str] | None = None
CANNED = {
    "cover_yes": ["Sure, I can take {day}.", "Yes, I've got {day}.", "Okay, {day} is mine.", "I can do {day}, no problem."],
    "plan_yes": ["Yes, I can {what} on {day}.", "I've got it: {what}, {day}.", "Sure, I'll {what} {day}."],
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


ACTOR_TOOL = {"name": "say", "description": "The one short chat line this family member sends.",
              "input_schema": {"type": "object", "properties": {"text": {"type": "string", "description": "<= 15 words, casual, no emoji"}}, "required": ["text"]}}


def _model_line_sync(name: str, answer: str, day: str, question: str) -> str | None:
    from core.llm import llm, provider_explicit

    if not provider_explicit("actors"):
        return None
    client = llm("actors")
    if getattr(client, "provider", None) == "off" or not hasattr(client, "village_model"):
        return None
    msg = client.messages.create(
        model=client.village_model, max_tokens=120,
        system=(f"You play {name}, a family member in a family group chat that coordinates caring for an older relative. "
                "Reply in character with one short, natural line. Do not mention being an AI. Match the decision you are given."),
        messages=[{"role": "user", "content": f"Village asked you: \"{question}\" (about {day}). Your answer is {answer.upper()}. Write your reply."}],
        tools=[ACTOR_TOOL], tool_choice={"type": "tool", "name": "say"})
    block = next((b for b in msg.content if getattr(b, "type", "") == "tool_use"), None)
    text = str((block.input or {}).get("text", "")).strip() if block is not None else ""
    return text[:160] or None


async def model_line(name: str, answer: str, day: str, question: str, timeout_s: float = 8.0) -> str | None:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_model_line_sync, name, answer, day, question), timeout_s)
    except Exception as exc:  # never block the demo on the model
        import logging

        logging.getLogger("village.builder").info("demo actor line: canned (%s)", type(exc).__name__)
        return None


def delay_s() -> float:
    v = os.getenv("DEMO_ACTOR_DELAY_S")
    return float(v) if v is not None else random.uniform(3, 6)


def on_ask(village_id: str, ask_id: str, member: str, *, role: str) -> None:
    if not _is_actor(village_id, member):
        return
    from .asks import _spawn

    _spawn(_reply(village_id, ask_id, member, role))


async def _reply(village_id: str, ask_id: str, member: str, role: str) -> None:
    from core import village as villages
    from . import asks

    await asyncio.sleep(delay_s())
    gid = asks.BY_MEMBER_ASK.get(ask_id, (ask_id, member))[0]
    ask = asks.ASKS.get(gid)
    if not ask or ask["status"] != "open":
        return
    if role == "plan" or ask.get("type") == "plan":  # answer the actual ask: the what + when that was extracted
        line = random.choice(CANNED["plan_yes"]).format(day=ask["day"], what=ask.get("what") or "do it")
        answer = "yes"
    else:
        key = "cover_yes" if role == "cover" else "on_duty_no"
        line = random.choice(CANNED[key]).format(day=ask["day"])
        answer = "yes" if role == "cover" else "no"
    name = (ask.get("names") or {}).get(member) or member
    question = (ask.get("questions") or {}).get(member, "") or (ask.get("what") or "")
    line = await model_line(name, answer, ask["day"], question) or line
    gid = asks.BY_MEMBER_ASK.get(ask_id, (ask_id, member))[0]
    await asks.post(village_id, author=member, kind="chat", text=f"[demo] {line}", refs=[{"kind": "member", "id": member, "label": villages.first_name(village_id, member)}, {"kind": "ask", "id": ask_id, "label": "demo actor"}],
                    source={"kind": "system", "ref": "demo_actor"}, reply_to=(asks.ASKS.get(gid) or {}).get("message_id"))
    await asks.answer(ask_id, member, "yes" if role in ("cover", "plan") else "no")
