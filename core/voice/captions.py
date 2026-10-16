"""D18 live captions: every ElevenLabs transcript turn -> `control{kind: caption, payload: {es, en, speaker, final}}`.

Sources, in order of liveness:
1. While a call is active, poll `GET /v1/convai/conversations/{id}` every 2 s (`poll_conversation`); the poller starts
   from the init webhook (inbound: resolves the in-progress conversation of the agent) and from outbound calls.
2. The post-call webhook carries the full transcript; `emit_transcript(..., final=True)` flushes any turn the poller missed.
Translation is Haiku 5.5 through `core.llm.llm("haiku")`; if the LLM is off/unreachable the caption still goes out with `en=""`.
`VILLAGE_CAPTIONS=off` disables polling (tests never poll: no API key / injected fetcher).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

API = "https://api.elevenlabs.io/v1/convai"
POLL_SECS = 2.0
MAX_POLL_SECS = 900.0
DONE_STATUSES = {"done", "failed"}

_EMITTED: dict[str, int] = {}
_POLLERS: dict[str, asyncio.Task[Any]] = {}
_TRANSLATIONS: dict[str, str] = {}
CAPTIONS_SENT: list[dict[str, Any]] = []  # test/debug tap

SYSTEM = (
    "You translate one line of a live phone call for an English-speaking audience. "
    "If the line is Spanish (or mixed), output a natural English translation. If it is already English, output it unchanged. "
    "Output only the line, no quotes, no notes."
)

Translator = Callable[[str], Awaitable[str]]
Emitter = Callable[[str, dict[str, Any]], Awaitable[None]]


def enabled() -> bool:
    return os.getenv("VILLAGE_CAPTIONS", "on").lower() != "off"


def _translate_sync(text: str) -> str:
    from core.llm import llm

    client = llm("haiku")
    msg = client.messages.create(
        model=getattr(client, "village_model", "claude-haiku-5-5"),
        max_tokens=200,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    return "".join(getattr(block, "text", "") for block in msg.content).strip()


async def translate_es_en(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text in _TRANSLATIONS:
        return _TRANSLATIONS[text]
    try:
        out = await asyncio.wait_for(asyncio.to_thread(_translate_sync, text), timeout=4.0)
    except Exception as exc:  # LLM off, timeout, network: caption without English rather than no caption
        log.info("caption translation unavailable: %s", type(exc).__name__)
        return ""
    _TRANSLATIONS[text] = out
    return out


async def _control_emit(village_id: str, payload: dict[str, Any]) -> None:
    from core import services

    await services.control(village_id, "caption", payload)


async def emit_turn(
    village_id: str,
    speaker: str,
    text: str,
    *,
    final: bool = True,
    translate: Translator | None = None,
    emit: Emitter | None = None,
) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    en = await (translate or translate_es_en)(text)
    payload = {"es": text, "en": en, "speaker": speaker, "final": final}
    CAPTIONS_SENT.append({"village_id": village_id, **payload})
    await (emit or _control_emit)(village_id, payload)
    return payload


def speaker_for(role: str, names: dict[str, str] | None = None) -> str:
    names = names or {}
    if role == "agent":
        return names.get("agent", "Village")
    return names.get("user", "Caller")


async def emit_transcript(
    village_id: str,
    conversation_id: str,
    transcript: list[dict[str, Any]],
    *,
    names: dict[str, str] | None = None,
    final: bool = True,
    translate: Translator | None = None,
    emit: Emitter | None = None,
) -> list[dict[str, Any]]:
    """Emit the turns of `transcript` not yet captioned for this conversation (idempotent across poll + post-call)."""
    start = _EMITTED.get(conversation_id, 0)
    sent: list[dict[str, Any]] = []
    for index in range(start, len(transcript)):
        turn = transcript[index] or {}
        _EMITTED[conversation_id] = index + 1
        payload = await emit_turn(
            village_id,
            speaker_for(str(turn.get("role", "user")), names),
            str(turn.get("message") or ""),
            final=final,
            translate=translate,
            emit=emit,
        )
        if payload:
            sent.append(payload)
    return sent


async def fetch_conversation(conversation_id: str) -> dict[str, Any]:
    import httpx

    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{API}/conversations/{conversation_id}", headers={"xi-api-key": os.getenv("ELEVENLABS_API_KEY", "")})
        response.raise_for_status()
        return response.json()


async def poll_conversation(
    conversation_id: str,
    village_id: str,
    *,
    names: dict[str, str] | None = None,
    fetch: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    interval: float = POLL_SECS,
    max_secs: float = MAX_POLL_SECS,
    translate: Translator | None = None,
    emit: Emitter | None = None,
) -> int:
    fetch = fetch or fetch_conversation
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_secs
    while loop.time() < deadline:
        try:
            data = await fetch(conversation_id)
        except Exception as exc:
            log.info("caption poll %s failed: %s", conversation_id, type(exc).__name__)
            data = {}
        transcript = data.get("transcript") or []
        await emit_transcript(village_id, conversation_id, transcript, names=names, translate=translate, emit=emit)
        if data.get("status") in DONE_STATUSES:
            break
        await asyncio.sleep(interval)
    return _EMITTED.get(conversation_id, 0)


def start_poller(conversation_id: str, village_id: str, names: dict[str, str] | None = None) -> bool:
    if not conversation_id or not enabled() or not os.getenv("ELEVENLABS_API_KEY"):
        return False
    if conversation_id in _POLLERS and not _POLLERS[conversation_id].done():
        return False
    try:
        task = asyncio.get_running_loop().create_task(poll_conversation(conversation_id, village_id, names=names))
    except RuntimeError:
        return False
    _POLLERS[conversation_id] = task
    task.add_done_callback(lambda _t: _POLLERS.pop(conversation_id, None))
    return True


async def _find_active_conversation(agent_id: str, tries: int = 6) -> str | None:
    import httpx

    for _ in range(tries):
        await asyncio.sleep(1.0)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{API}/conversations",
                    params={"agent_id": agent_id, "page_size": 5},
                    headers={"xi-api-key": os.getenv("ELEVENLABS_API_KEY", "")},
                )
                response.raise_for_status()
                for row in response.json().get("conversations", []):
                    if row.get("status") in {"initiated", "in-progress", "processing"}:
                        return row.get("conversation_id")
        except Exception:
            continue
    return None


async def _watch(agent_id: str, conversation_id: str | None, village_id: str, names: dict[str, str]) -> None:
    conversation_id = conversation_id or await _find_active_conversation(agent_id)
    if conversation_id:
        start_poller(conversation_id, village_id, names)


def watch_inbound(payload: dict[str, Any], variables: dict[str, str]) -> bool:
    """Called by the init webhook: caption the call that is starting (conversation id resolved by agent)."""
    if not enabled() or not os.getenv("ELEVENLABS_API_KEY"):
        return False
    agent_id = payload.get("agent_id") or os.getenv("ELEVENLABS_AGENT_ID", "")
    names = {"user": variables.get("member_short_name") or "Caller", "agent": "Village"}
    if names["user"] in {"there", "señora"}:
        names["user"] = "Caller"
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    loop.create_task(_watch(agent_id, payload.get("conversation_id"), variables.get("village_id", ""), names))
    return True


def reset() -> None:
    _EMITTED.clear()
    CAPTIONS_SENT.clear()
    for task in list(_POLLERS.values()):
        task.cancel()
    _POLLERS.clear()
