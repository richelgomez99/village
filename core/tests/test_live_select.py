"""LIVE SELECT feed, against a fake cloud connection (no network).

Written by Claude with the wiring on Nov 16 2026. Richel owns the names and assertions.
"""
from __future__ import annotations

import asyncio

import pytest

import core.db as dbmod
from core.db import LIVE_TABLES, MemoryDB


class FakeCloud:
    """Stands in for one SurrealDB server: writes on any connection notify every live query."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}
        self.queues: dict[str, list[asyncio.Queue]] = {}
        self.fail_writes = False

    def conn(self) -> "FakeConn":
        return FakeConn(self)

    def write(self, table: str, key: str, row: dict) -> None:
        if self.fail_writes:
            raise ConnectionError("cloud down")
        if self.rows.get((table, key)) == row:
            return  # a write that changes nothing notifies nobody
        action = "UPDATE" if (table, key) in self.rows else "CREATE"
        self.rows[(table, key)] = dict(row)
        for queue in self.queues.get(table, []):
            queue.put_nowait({"id": "q", "action": action, "result": dict(row)})

    def break_streams(self) -> None:
        for queues in self.queues.values():
            for queue in queues:
                queue.put_nowait(None)


class FakeConn:
    def __init__(self, cloud: FakeCloud) -> None:
        self.cloud = cloud

    async def query(self, sql: str, params: dict | None = None):
        if sql.startswith(("CREATE", "UPSERT")):
            table, key = sql.split()[1].split(":")
            self.cloud.write(table, key.strip("`"), params["row"])

    async def live(self, table: str) -> str:
        return table

    async def subscribe_live(self, table: str):
        queue: asyncio.Queue = asyncio.Queue()
        self.cloud.queues.setdefault(table, []).append(queue)

        async def stream():
            while True:
                note = await queue.get()
                if note is None:
                    raise ConnectionError("socket closed")
                yield note

        return stream()

    async def close(self) -> None:
        pass


@pytest.fixture
async def live(monkeypatch):
    cloud = FakeCloud()
    monkeypatch.setenv("SURREAL_DB_URL", "ws://fake")
    monkeypatch.setenv("SURREAL_LIVE", "1")
    dbmod.get_settings.cache_clear()
    monkeypatch.setattr(dbmod, "AsyncSurreal", object())

    async def open_conn(self):
        return cloud.conn()

    monkeypatch.setattr(MemoryDB, "_open_conn", open_conn)
    db = MemoryDB()
    queue = db.subscribe()
    assert await db.start_cloud_live() is True
    yield db, cloud, queue
    await db.stop_cloud_live()
    dbmod.get_settings.cache_clear()


async def drain(queue: asyncio.Queue) -> list[tuple[str, dict]]:
    out = []
    while True:
        try:
            out.append(await asyncio.wait_for(queue.get(), 0.05))
        except asyncio.TimeoutError:
            return out


async def test_feed_source_is_surreal_when_the_cloud_is_connected(live):
    db, _, _ = live
    assert db.live_source == "surreal"
    assert all(db.live_on(table) for table in LIVE_TABLES)
    assert not db.live_on("control")


async def test_own_write_reaches_subscribers_once_as_the_same_row(live):
    db, _, queue = live
    event = {"id": "e_1", "village": "v_reyes"}
    await db.create_event(event)
    got = await drain(queue)
    assert [(table, row["id"]) for table, row in got] == [("event", "e_1")]
    assert got[0][1] is event


async def test_verification_held_back_lands_after_its_events(live):
    db, _, queue = live
    await db.upsert_verification({"id": "vf_1", "version": 0, "state": "pending"}, publish=False)
    await db.create_event({"id": "e_1"})
    await db.create_event({"id": "e_2"})
    await db.publish("verification", db.verifications["vf_1"])
    assert [(table, row["id"]) for table, row in await drain(queue)] == [
        ("event", "e_1"), ("event", "e_2"), ("verification", "vf_1")]


async def test_row_from_another_writer_is_mirrored_and_fanned_out(live):
    db, cloud, queue = live
    cloud.write("event", "e_other", {"id": "e_other", "village": "v_reyes"})
    cloud.write("verification", "vf_9", {"id": "vf_9", "version": 3, "state": "approved"})
    got = await drain(queue)
    assert [(table, row["id"]) for table, row in got] == [("event", "e_other"), ("verification", "vf_9")]
    assert db.events[-1]["id"] == "e_other"
    assert db.verifications["vf_9"]["state"] == "approved"


async def test_republishing_an_unchanged_row_still_delivers(live):
    db, _, queue = live
    await db.upsert_verification({"id": "vf_1", "version": 0})
    await drain(queue)
    await db.publish("verification", db.verifications["vf_1"])
    assert len(await drain(queue)) == 1


async def test_failed_cloud_write_falls_back_to_the_in_process_feed(live):
    db, cloud, queue = live
    cloud.fail_writes = True
    await db.create_event({"id": "e_1"})
    assert [(table, row["id"]) for table, row in await drain(queue)] == [("event", "e_1")]


async def test_broken_stream_turns_the_in_process_feed_back_on(live):
    db, cloud, queue = live
    cloud.break_streams()
    await asyncio.sleep(0.05)
    assert db.live_source == "in-process"
    await db.create_event({"id": "e_1"})
    assert len(await drain(queue)) == 1


async def test_without_a_cloud_url_nothing_changes(monkeypatch):
    monkeypatch.delenv("SURREAL_DB_URL", raising=False)
    dbmod.get_settings.cache_clear()
    db = MemoryDB()
    queue = db.subscribe()
    assert await db.start_cloud_live() is False
    await db.create_event({"id": "e_1"})
    assert db.live_source == "in-process"
    assert len(await drain(queue)) == 1


def test_record_ids_come_back_as_contract_ids():
    from surrealdb import RecordID

    row = dbmod._plain({"id": RecordID("event", "e_1"), "refs": [RecordID("village", "v_reyes")]})
    assert row == {"id": "e_1", "refs": ["v_reyes"]}
