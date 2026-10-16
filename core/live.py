from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from core.db import db
from core.ws_hub import hub


log = logging.getLogger("village.live")


class LiveStatus:
    status = "down"
    task: asyncio.Task[Any] | None = None


live_status = LiveStatus()


async def _run() -> None:
    queue = db.subscribe()
    live_status.status = "ok"
    while True:
        table, row = await queue.get()
        try:
            await _dispatch(table, row)
        except Exception:  # one bad row must never stop the fan-out
            log.exception("live dispatch failed for %s", table)


async def _dispatch(table: str, row: dict[str, Any]) -> None:
    if table == "event":
        await hub.broadcast_event(row)
    elif table == "message":
        await hub.broadcast_chat(row)
    elif table == "verification":
        await hub.broadcast_verification(row)
    elif table == "control":
        await hub.control(row["village"], row["kind"], row["payload"])


async def start_live() -> None:
    if live_status.task and not live_status.task.done():
        return
    live_status.task = asyncio.create_task(_run())
    await asyncio.sleep(0)


async def stop_live() -> None:
    if live_status.task:
        live_status.task.cancel()
        with suppress(asyncio.CancelledError):
            await live_status.task
    live_status.task = None
    live_status.status = "down"
