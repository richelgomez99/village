"""Setup agent v2 tools (D29): `create_village` and `submit_answer` -> the builder's founding session.

Core's `/tools/{name}` dispatcher (core/routes/tools.py -> services.handle_tool) does not know these tools, so the
ElevenLabs "Village Setup" agent calls `/hooks/elevenlabs/tools/<tool>` (grafted from core.voice.init_hook) and these
handlers call the builder routes in-process: `create_village` == `POST /villages`, `submit_answer` == `POST /villages/{id}/answers`.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

BUILDING_SAY = "Building it now. I'll ask you a few things while it comes together."
WAIT_FIRST_QUESTION_S = 6.0
WAIT_SESSION_S = 5.0


def _response(say: str, data: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    return {"decision": "allow", "say": say[:400], "rule_id": "R-NOOP", "lang": "es" if lang == "es" else "en", "data": data}


async def _current_question(village_id: str, wait_s: float) -> str | None:
    from core.builder import routes as builder

    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s
    while True:
        session = builder.SESSIONS.get(village_id)
        question = getattr(session, "question", None) if session is not None and getattr(session, "waiting", False) else None
        text = getattr(question, "text", None)
        if text:
            return str(text)
        if loop.time() >= deadline:
            return None
        await asyncio.sleep(0.2)


async def create_village(body: dict[str, Any], *, wait_s: float = WAIT_FIRST_QUESTION_S) -> dict[str, Any]:
    from core.builder import routes as builder

    lang = body.get("language") or "en"
    founding = {
        "description": body.get("description") or body.get("utterance") or "",
        "members": body.get("members") or [],
        "needs": body.get("needs") or [],
        "language": lang,
        "channel": "voice",
        "kind": "care",
    }
    if body.get("medications_mentioned"):
        founding["medications"] = body["medications_mentioned"]
    if body.get("village_id"):
        founding["village_id"] = body["village_id"]
    started = await builder.create_village(founding, None)
    village_id = started["village_id"]
    question = await _current_question(village_id, wait_s)
    say = f"{BUILDING_SAY} {question}" if question else BUILDING_SAY
    return _response(say, {"village_id": village_id, "plan": "founding started", "next_question": question or ""}, lang)


async def submit_answer(body: dict[str, Any], *, wait_s: float = WAIT_SESSION_S) -> dict[str, Any]:
    from core.builder import routes as builder

    village_id = str(body.get("village_id") or "")
    text = str(body.get("text") or body.get("answer") or "").strip()
    if not village_id or not text:
        raise HTTPException(status_code=422, detail="village_id and text required")
    await _current_question(village_id, wait_s)  # the founder may still be preparing the first question
    try:
        result = await builder.post_answer(village_id, {"text": text})
    except HTTPException as exc:
        if exc.status_code == 404:
            return _response("Give me a second, Village is still listening to the first part.", {"village_id": village_id, "accepted": False})
        raise
    next_question = result.get("next_question") or await _current_question(village_id, 3.0) or ""
    data = {
        "village_id": village_id,
        "accepted": bool(result.get("accepted")),
        "answered": result.get("answered") or "",
        "meter": result.get("meter") or "",
        "gaps": result.get("gaps") or [],
        "next_question": next_question,
    }
    return _response(next_question, data)
