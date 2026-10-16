from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.settings import ROOT, get_settings

try:
    from surrealdb import AsyncSurreal
except Exception:  # pragma: no cover - import guard for local fallback
    AsyncSurreal = None  # type: ignore[assignment]


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

    async def reset(self) -> None:
        subscribers = self.subscribers
        surreal = self._surreal
        self.__init__()
        self.subscribers = subscribers
        self._surreal = surreal

    async def create_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append(event)
        await self._cloud_create("event", event)
        await self.publish("event", event)
        return event

    async def create_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        self.decisions.append(decision)
        await self._cloud_create("decision", decision)
        await self.publish("decision", decision)
        return decision

    async def create_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self.messages.append(message)
        await self._cloud_create("message", message)
        await self.publish("message", message)
        return message

    async def upsert_verification(self, verification: dict[str, Any], *, publish: bool = True) -> dict[str, Any]:
        self.verifications[verification["id"]] = verification
        await self._cloud_upsert("verification", verification["id"], verification)
        if publish:
            await self.publish("verification", verification)
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
            village = row.get("village", "v_reyes")
            role = row.get("role", key)
            self.views[(village, role)] = row.get("spec", row)
        elif table == "spec_rev":
            self.specs[row.get("village", key)] = row.get("spec", row)
        await self._cloud_upsert(table, key, row)
        return row

    async def publish(self, table: str, row: dict[str, Any]) -> None:
        for queue in list(self.subscribers):
            await queue.put((table, row))

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
        await self._cloud_upsert(table, key, updated)
        await self.publish(table, updated)
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
        self._surreal = conn
        return conn

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

    async def _cloud_create(self, table: str, row: dict[str, Any]) -> None:
        conn = await self.connect_cloud()
        if conn is None:
            return
        try:
            await conn.query(f"CREATE {table}:`{row['id']}` CONTENT $row", {"row": row})
        except Exception:
            # Cloud must not break the demo path; acceptance still runs from the local mirror.
            return

    async def _cloud_upsert(self, table: str, key: str, row: dict[str, Any]) -> None:
        conn = await self.connect_cloud()
        if conn is None:
            return
        try:
            await conn.query(f"UPSERT {table}:`{key}` CONTENT $row", {"row": row})
        except Exception:
            return


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
