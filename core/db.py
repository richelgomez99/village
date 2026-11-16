from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.settings import ROOT, get_settings

try:
    from surrealdb import AsyncSurreal
except Exception:  # pragma: no cover - import guard for local fallback
    AsyncSurreal = None  # type: ignore[assignment]

log = logging.getLogger("village.db")

# Tables whose changes reach the phones. With SurrealDB Cloud connected, a LIVE SELECT on
# each one is the feed: a write goes to the cloud and the notification that comes back is
# what fans out. Without the cloud (tests, local runs) the in-process feed does the same job.
LIVE_TABLES = ("event", "decision", "message", "verification", "dose_window")


class MemoryDB:
    def __init__(self) -> None:
        self.villages: dict[str, dict[str, Any]] = {}
        self.members: dict[str, dict[str, Any]] = {}
        self.views: dict[tuple[str, str], dict[str, Any]] = {}
        self.specs: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.verifications: dict[str, dict[str, Any]] = {}
        self.dose_windows: dict[str, dict[str, Any]] = {}
        self.idem: dict[str, dict[str, Any]] = {}
        self.prescriptions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.subscribers: list[asyncio.Queue[tuple[str, dict[str, Any]]]] = []
        self._surreal: Any | None = None
        self._live_on = False
        self._live_task: asyncio.Task[Any] | None = None
        self._live_ready: asyncio.Event | None = None
        self._cloud_sent: dict[tuple[str, str], str] = {}

    async def reset(self) -> None:
        keep = (self.subscribers, self._surreal, self._live_on, self._live_task, self._live_ready)
        self.__init__()
        self.subscribers, self._surreal, self._live_on, self._live_task, self._live_ready = keep

    async def create_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append(event)
        await self._fanout("event", event, await self._cloud_create("event", event))
        return event

    async def create_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        self.decisions.append(decision)
        await self._fanout("decision", decision, await self._cloud_create("decision", decision))
        return decision

    async def create_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self.messages.append(message)
        await self._fanout("message", message, await self._cloud_create("message", message))
        return message

    async def upsert_verification(self, verification: dict[str, Any], *, publish: bool = True) -> dict[str, Any]:
        self.verifications[verification["id"]] = verification
        if not publish and self.live_on("verification"):
            # The caller publishes this row itself once its events are written. On the live
            # feed that publish is the cloud write, so the notification lands after the events.
            return verification
        wrote = await self._cloud_upsert("verification", verification["id"], verification)
        if publish:
            await self._fanout("verification", verification, wrote)
        return verification

    async def get_idem(self, key: str) -> dict[str, Any] | None:
        return self.idem.get(key)

    async def put_idem(self, key: str, row: dict[str, Any]) -> None:
        self.idem[key] = row

    async def upsert_record(self, table: str, key: str, row: dict[str, Any]) -> dict[str, Any]:
        if table == "village":
            self.villages[key] = row
        elif table == "member":
            self.members[key] = row
        elif table == "view":
            from core.village import default_village_id

            village = row.get("village") or default_village_id()
            role = row.get("role", key)
            self.views[(village, role)] = row.get("spec", row)
        elif table == "spec_rev":
            self.specs[row.get("village", key)] = row.get("spec", row)
        await self._cloud_upsert(table, key, row)
        return row

    async def publish(self, table: str, row: dict[str, Any]) -> None:
        """Send a row to every subscriber. On the live feed, a row of a live table is
        written to the cloud and the LIVE SELECT notification delivers it."""
        if self.live_on(table) and isinstance(row.get("id"), str):
            # A write that changes nothing produces no notification, so a row the cloud
            # already holds as-is goes out on the in-process feed instead.
            changed = self._cloud_sent.get((table, row["id"])) != _fingerprint(row)
            if changed and await self._cloud_upsert(table, row["id"], row):
                return
        await self._publish_local(table, row)

    async def _publish_local(self, table: str, row: dict[str, Any]) -> None:
        for queue in list(self.subscribers):
            await queue.put((table, row))

    async def _fanout(self, table: str, row: dict[str, Any], wrote: bool) -> None:
        """After a write: if the cloud took it and the live feed is up, the notification
        fans it out. Otherwise fan out here, so nothing is lost when the cloud is down."""
        if wrote and self.live_on(table):
            return
        await self._publish_local(table, row)

    def live_on(self, table: str) -> bool:
        return self._live_on and table in LIVE_TABLES

    @property
    def live_source(self) -> str:
        return "surreal" if self._live_on else "in-process"

    def subscribe(self) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    async def cas_update(self, table: str, key: str, version: int, values: dict[str, Any]) -> list[dict[str, Any]]:
        store = self._store_for(table)
        row = store.get(key)
        if row is None or row.get("version", 0) != version:
            return []
        updated = {**row, **values, "version": version + 1}
        store[key] = updated
        await self._fanout(table, updated, await self._cloud_upsert(table, key, updated))
        return [updated]

    def _store_for(self, table: str) -> dict[str, dict[str, Any]]:
        if table == "verification":
            return self.verifications
        if table == "dose_window":
            return self.dose_windows
        raise ValueError(f"CAS not supported for {table}")

    async def connect_cloud(self) -> Any | None:
        settings = get_settings()
        if not settings.surreal_db_url or AsyncSurreal is None:
            return None
        if self._surreal is not None:
            return self._surreal
        self._surreal = await self._open_conn()
        return self._surreal

    async def _open_conn(self) -> Any:
        settings = get_settings()
        url = settings.surreal_db_url
        if url.startswith(("ws://", "wss://")) and not url.endswith("/rpc"):
            url = f"{url.rstrip('/')}/rpc"
        conn = AsyncSurreal(url)
        if hasattr(conn, "__aenter__"):
            conn = await conn.__aenter__()
        if settings.surreal_db_user or settings.surreal_db_pass:
            try:
                await conn.signin({"username": settings.surreal_db_user, "password": settings.surreal_db_pass})
            except TypeError:
                await conn.signin({"user": settings.surreal_db_user, "pass": settings.surreal_db_pass})
        await conn.use(settings.surreal_db_ns, settings.surreal_db_db)
        return conn

    # --- LIVE SELECT feed -------------------------------------------------------------

    async def start_cloud_live(self, *, wait_s: float = 10.0) -> bool:
        """Subscribe to LIVE SELECT on every live table, on a connection of its own.
        Returns True once the feed is up. False means the in-process feed stays in charge."""
        settings = get_settings()
        if not settings.surreal_db_url or not settings.surreal_live or AsyncSurreal is None:
            return False
        if self._live_task is None or self._live_task.done():
            self._live_ready = asyncio.Event()
            self._live_task = asyncio.create_task(self._live_supervisor(), name="surreal-live")
        try:
            await asyncio.wait_for(self._live_ready.wait(), timeout=wait_s)
        except asyncio.TimeoutError:
            log.warning("LIVE SELECT not up after %.0f s; in-process feed stays on while it retries", wait_s)
        return self._live_on

    async def stop_cloud_live(self) -> None:
        task, self._live_task = self._live_task, None
        self._live_on = False
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _live_supervisor(self) -> None:
        """Keep the feed up. Any break turns the in-process feed back on, then retries."""
        backoff = 1.0
        broke = False
        while True:
            conn = None
            try:
                conn = await self._open_conn()
                streams = []
                for table in LIVE_TABLES:
                    await conn.query(f"DEFINE TABLE IF NOT EXISTS {table} SCHEMALESS;")  # live() fails on a missing table
                    streams.append((table, await conn.subscribe_live(await conn.live(table))))
                if broke:
                    self._surreal = None  # the cloud is back: the next write opens a fresh connection
                    broke = False
                self._live_on = True
                backoff = 1.0
                if self._live_ready:
                    self._live_ready.set()
                log.info("LIVE SELECT feed up on %s", ", ".join(LIVE_TABLES))
                async with asyncio.TaskGroup() as group:
                    for table, stream in streams:
                        group.create_task(self._live_consume(table, stream))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a broken stream arrives as an ExceptionGroup from the TaskGroup
                log.warning("LIVE SELECT feed down (%s); in-process feed on, retry in %.0f s", type(exc).__name__, backoff)
            finally:
                broke = True
                self._live_on = False
                if conn is not None:
                    try:
                        await conn.close()
                    except Exception:
                        pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def _live_consume(self, table: str, stream: Any) -> None:
        async for note in stream:
            try:
                await self._on_live(table, note)
            except Exception:  # one bad notification must never stop the feed
                log.exception("live notification failed for %s", table)
        raise ConnectionError(f"live query on {table} ended")

    async def _on_live(self, table: str, note: Any) -> None:
        if not isinstance(note, dict):
            return
        if "action" in note and "result" in note:  # SDK v3 shape; v2 yields the record itself
            if str(note["action"]).upper() == "DELETE":
                return
            note = note["result"]
        if not isinstance(note, dict):
            return
        row = _plain(note)
        await self._publish_local(table, self._mirror(table, row))

    def _mirror(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """Return the row to fan out. A row this Core wrote is already in the local mirror,
        and that same object goes out, as it does on the in-process feed. A row from another
        writer is added to the mirror first."""
        key = row.get("id")
        if table in ("verification", "dose_window"):
            store = self._store_for(table)
            mine = store.get(key)
            if mine is not None and mine.get("version", 0) >= row.get("version", 0):
                return mine
            store[key] = row
            self._note_sent(table, key, row)
            return row
        rows = {"event": self.events, "decision": self.decisions, "message": self.messages}[table]
        for mine in reversed(rows):
            if mine.get("id") == key:
                return mine
        rows.append(row)
        self._note_sent(table, key, row)
        return row

    async def clear_cloud(self) -> None:
        conn = await self.connect_cloud()
        if conn is None:
            return
        for table in (
            "event",
            "decision",
            "message",
            "verification",
            "dose_window",
            "idem",
            "slot_token",
            "view",
            "spec_rev",
            "member",
            "village",
        ):
            try:
                await conn.query(f"DELETE {table};")
            except Exception:
                continue

    async def _cloud_create(self, table: str, row: dict[str, Any]) -> bool:
        """True when the cloud took the write."""
        try:
            conn = await self.connect_cloud()
            if conn is None:
                return False
            await conn.query(f"CREATE {table}:`{row['id']}` CONTENT $row", {"row": row})
        except Exception:
            # Cloud must not break the demo path; acceptance still runs from the local mirror.
            return False
        self._note_sent(table, row["id"], row)
        return True

    async def _cloud_upsert(self, table: str, key: str, row: dict[str, Any]) -> bool:
        try:
            conn = await self.connect_cloud()
            if conn is None:
                return False
            await conn.query(f"UPSERT {table}:`{key}` CONTENT $row", {"row": row})
        except Exception:
            return False
        self._note_sent(table, key, row)
        return True

    def _note_sent(self, table: str, key: str, row: dict[str, Any]) -> None:
        if table in LIVE_TABLES:
            self._cloud_sent[(table, key)] = _fingerprint(row)


def _fingerprint(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, default=str)


def _plain(value: Any) -> Any:
    """Cloud values back to contract shape: a RecordID becomes its bare id (`v_reyes`,
    not `village:v_reyes`), SDK datetimes become ISO strings."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    kind = type(value).__name__
    if kind == "RecordID":
        return str(value.id)
    if kind == "Datetime":
        inner = getattr(value, "dt", None)
        return inner.isoformat() if hasattr(inner, "isoformat") else str(inner if inner is not None else value)
    return value


db = MemoryDB()


async def apply_schema() -> str:
    conn = await db.connect_cloud()
    if conn is None:
        return "schema OK (memory)"
    schema = (ROOT / "core" / "schema.surql").read_text()
    statements = [
        statement.strip()
        for statement in schema.split(";")
        if statement.strip() and not statement.strip().startswith("--")
    ]
    for statement in statements:
        await conn.query(f"{statement};")
    return "schema OK (surreal)"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    if args.apply:
        print(await apply_schema())
    elif args.local:
        print("memory fallback is in-process; external surreal start skipped")


if __name__ == "__main__":
    asyncio.run(main())
