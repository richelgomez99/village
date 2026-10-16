"""Durable memory outbox: JSONL under var/memory/outbox.jsonl + a background flusher.

Memory writes never sit on the safety path: callers `enqueue()` (one file append,
sub-millisecond) and return; the flusher sends in enqueue order (supersession needs
order), backs off 1 s ... 10 min on 5xx/timeouts, marks 4xx as dead. Idempotent on id
(normally the ledger event id + fact key). The file is an append-only log of
enqueue/sent/retry/dead records folded on load, so a restart resumes where it stopped.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from core.settings import ROOT

DEFAULT_PATH = ROOT / "var" / "memory" / "outbox.jsonl"
BACKOFF_MIN_S = 1.0
BACKOFF_MAX_S = 600.0
INTERVAL_S = 2.0


class Outbox:
    def __init__(self, path: Path | str = DEFAULT_PATH, client: Any = None, *, clock=time.time) -> None:
        self.path = Path(path)
        self.client = client
        self.clock = clock
        self.items: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.last_error: str | None = None
        self._load()

    # ------------------------------------------------------------ persistence
    def _append(self, rec: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            op, rid = rec.get("op"), rec.get("id")
            if op == "enqueue" and rid not in self.items:
                self.items[rid] = {"id": rid, "kind": rec["kind"], "args": rec["args"], "status": "queued",
                                   "attempts": 0, "next_at": 0.0, "created_at": rec.get("at")}
            elif rid in self.items:
                item = self.items[rid]
                if op == "sent":
                    item.update(status="sent", result=rec.get("result"))
                elif op == "retry":
                    item.update(attempts=rec.get("attempts", 1), next_at=rec.get("next_at", 0.0), last_error=rec.get("error"))
                elif op == "dead":
                    item.update(status="dead", last_error=rec.get("error"))

    # ------------------------------------------------------------ API
    def enqueue(self, item_id: str, kind: str, args: dict[str, Any]) -> bool:
        """Returns False when the id is already known (idempotent). Never touches the network."""
        if item_id in self.items:
            return False
        now = self.clock()
        self.items[item_id] = {"id": item_id, "kind": kind, "args": args, "status": "queued",
                               "attempts": 0, "next_at": 0.0, "created_at": now}
        self._append({"op": "enqueue", "id": item_id, "kind": kind, "args": args, "at": now})
        return True

    def pending(self) -> list[dict[str, Any]]:
        return [i for i in self.items.values() if i["status"] == "queued"]

    def stats(self) -> dict[str, Any]:
        st = {"queued": 0, "sent": 0, "dead": 0}
        for i in self.items.values():
            st[i["status"]] = st.get(i["status"], 0) + 1
        st["last_error"] = self.last_error
        return st

    async def _send(self, item: dict[str, Any]) -> dict[str, Any]:
        a = item["args"]
        if item["kind"] == "fact":
            return await self.client.remember_fact(
                a["entity"], a["key"], a["value"], source=a["source"], village=a["village"],
                agent=a.get("agent"), observed_at=a.get("observed_at"), event_id=a.get("event_id"),
                rule_id=a.get("rule_id"), extra_labels=a.get("extra_labels"))
        if item["kind"] == "transcript":
            return await self.client.remember_transcript(
                a["conversation_id"], a["text"], village=a["village"], entity=a.get("entity", "village"),
                source=a.get("source"), agent=a.get("agent", "voice:post_call"), observed_at=a.get("observed_at"))
        return {"degraded": True, "status": 400, "degraded_reason": "unknown kind"}

    async def drain_once(self) -> dict[str, int]:
        """Send every due item in order; stop at the first retryable failure (keeps order)."""
        sent = dead = failed = 0
        if self.client is None:
            return {"sent": 0, "dead": 0, "failed": 0}
        async with self._lock:
            now = self.clock()
            for item in self.pending():
                if item["next_at"] > now:
                    break
                res = await self._send(item)
                status = res.get("status", 0) or 0
                if not res.get("degraded"):
                    item.update(status="sent", result={k: res.get(k) for k in ("am_id", "fact_id", "corrections", "turn_id")})
                    self._append({"op": "sent", "id": item["id"], "result": item["result"], "at": self.clock()})
                    sent += 1
                elif 400 <= status < 500 and status not in (408, 409, 429):
                    err = f"HTTP {status}"
                    item.update(status="dead", last_error=err)
                    self._append({"op": "dead", "id": item["id"], "error": err, "at": self.clock()})
                    dead += 1
                else:
                    item["attempts"] += 1
                    delay = min(BACKOFF_MAX_S, BACKOFF_MIN_S * 2 ** (item["attempts"] - 1))
                    item["next_at"] = self.clock() + delay
                    self.last_error = str(res.get("degraded_reason") or f"HTTP {status}")
                    self._append({"op": "retry", "id": item["id"], "attempts": item["attempts"],
                                  "next_at": item["next_at"], "error": self.last_error})
                    failed += 1
                    break
        return {"sent": sent, "dead": dead, "failed": failed}

    async def _loop(self, interval: float) -> None:
        while True:
            try:
                await self.drain_once()
            except Exception as exc:  # noqa: BLE001 - the flusher must never die
                self.last_error = f"{type(exc).__name__}"
            await asyncio.sleep(interval)

    def start(self, interval: float = INTERVAL_S) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(interval), name="memory-outbox")
        return self._task

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
