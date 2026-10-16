"""Wiring for core's lifespan (one call each; none of it is on the safety path):

    from core.memory import runtime as memory_runtime
    await memory_runtime.start(db)      # in lifespan, after reset_demo
    await memory_runtime.stop()         # on shutdown
    memory_runtime.health()             # -> {"queued", "sent", "dead", "last_error"} for /health.outbox
"""
from __future__ import annotations

import asyncio
from typing import Any

from core.memory.client import get_client
from core.memory.ledger_subscriber import LedgerSubscriber
from core.memory.outbox import Outbox

_state: dict[str, Any] = {}


async def _voice_loop(sub: LedgerSubscriber, interval: float) -> None:
    while True:
        try:
            sub.consume_voice_outbox()
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(interval)


async def start(db: Any, *, backfill: bool = True, interval: float = 2.0, path: Any = None, client: Any = None) -> dict[str, Any]:
    if _state:
        return _state
    ob = Outbox(path, client or get_client()) if path else Outbox(client=client or get_client())
    sub = LedgerSubscriber(ob)
    if backfill:  # events already in the ledger (seed) -> idempotent enqueue
        for e in list(getattr(db, "events", [])):
            sub.on_event(e)
        from core.memory.founding import enqueue_founding

        enqueue_founding(ob)  # founding facts from each village's data file (idempotent ids)
    sub.start(db)
    ob.start(interval)
    _state.update(outbox=ob, subscriber=sub, voice=asyncio.create_task(_voice_loop(sub, 5.0), name="memory-voice-outbox"))
    return _state


async def stop() -> None:
    if not _state:
        return
    _state["voice"].cancel()
    await _state["subscriber"].stop()
    await _state["outbox"].stop()
    _state.clear()


def health() -> dict[str, Any]:
    ob = _state.get("outbox")
    return ob.stats() if ob else {"queued": 0, "sent": 0, "dead": 0, "last_error": None, "running": False}
