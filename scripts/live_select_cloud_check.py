"""Check the LIVE SELECT feed (core/db.py) against SurrealDB Cloud. Needs SURREAL_DB_URL in .env.
Writes ten scratch message rows under village v_livecheck, then deletes them. Prints no secrets.
Run: uv run python -m scripts.live_select_cloud_check"""
import asyncio, statistics, time
from core.db import db
from core.settings import get_settings
settings = get_settings()

async def main():
    assert settings.surreal_db_url, "no SURREAL_DB_URL"
    print("scheme:", settings.surreal_db_url.split("://")[0])
    queue = db.subscribe()
    up = await db.start_cloud_live(wait_s=20)
    print("live up:", up, "| live_source:", db.live_source)
    if not up:
        return
    tag = f"livecheck_{int(time.time())}"
    ids, lat = [], []
    try:
        # rows this Core writes: must arrive through the notification, once each
        for i in range(10):
            rid = f"{tag}_{i}"; ids.append(rid)
            row = {"id": rid, "village": "v_livecheck", "kind": "livecheck", "text": "live select check", "n": i}
            t0 = time.perf_counter()
            await db.create_message(row)
            table, got = await asyncio.wait_for(queue.get(), timeout=10)
            lat.append((time.perf_counter() - t0) * 1000)
            assert table == "message" and got["id"] == rid, (table, got.get("id"))
            assert got is row, "expected the mirror object"
        await asyncio.sleep(1)
        print("own writes: 10 of 10 arrived | duplicates in queue:", queue.qsize())
        print("write to fan-out ms p50 %.0f  min %.0f  max %.0f" % (statistics.median(lat), min(lat), max(lat)))
        # a row from another writer, on a connection of its own
        other = await db._open_conn()
        rid = f"{tag}_other"; ids.append(rid)
        t0 = time.perf_counter()
        await other.query(f"CREATE message:`{rid}` CONTENT $row", {"row": {"id": rid, "village": "v_livecheck", "kind": "livecheck", "text": "other writer"}})
        table, got = await asyncio.wait_for(queue.get(), timeout=10)
        print("other writer arrived: %s in %.0f ms | in mirror: %s" % (got.get("id") == rid, (time.perf_counter() - t0) * 1000, any(m.get("id") == rid for m in db.messages)))
        await other.close()
    finally:
        conn = await db.connect_cloud()
        for rid in ids:
            await conn.query(f"DELETE message:`{rid}`;")
        left = await conn.query("SELECT count() FROM message WHERE village = 'v_livecheck' GROUP ALL;")
        print("cleanup, rows left:", left)
        await db.stop_cloud_live()

asyncio.run(main())
