from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from core import village as villages
from core.db import db
from core.settings import ROOT


FIXTURES = ROOT / "contracts" / "fixtures"
DATA = ROOT / "data" / "villages"


def load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def _slug(village_id: str) -> str:
    return village_id.removeprefix("v_")


async def seed_village(village_id: str, *, with_seed_rows: bool = True) -> dict[str, Any]:
    """Load one registered village (data/villages/index.json -> contract spec + seed rows) without
    touching any other village already in memory."""
    spec = villages.fixture_spec(village_id)
    if not spec:
        raise KeyError(f"unknown village {village_id!r}; registered: {villages.village_ids()}")
    slug = _slug(village_id)
    await db.upsert_record("village", village_id, {**spec["village"], "id": village_id})
    await db.upsert_record(
        "spec_rev",
        f"{slug}_{spec['rev']}",
        {"id": f"sr_{slug}_{spec['rev']}", "village": village_id, "rev": spec["rev"], "spec": spec, "published": True},
    )
    for person in spec["blueprint"]["people"]:
        await db.upsert_record("member", person["id"], {"village": village_id, **person})
    for role, view in spec["views"].items():
        await db.upsert_record("view", f"{slug}_{role}", {"id": f"view_{slug}_{role}", "village": village_id, "role": role, "rev": spec["rev"], "spec": view})
    db.prescriptions[village_id] = villages.seed_prescriptions(village_id)
    if with_seed_rows:
        for event in villages.seed_events(village_id):
            await db.create_event({**event, "village": event.get("village", village_id)})
        # contracts: core seeds the rows before the live scam beat (14:02); the live flow writes the rest.
        for message in [row for row in villages.seed_messages(village_id) if row["at"] < "2026-10-16T14:02:00-04:00"]:
            await db.create_message({**message, "village": village_id})
    return spec


async def reset_demo(village_id: str | None = None, *, keep_others: bool = False) -> dict[str, Any]:
    """Reset to the seed of `village_id` (default: DEMO_VILLAGE_ID / registry default). Every other
    registered village is loaded alongside (spec, members, views) so one Core serves them all at once.
    keep_others=True re-seeds only `village_id` and leaves the in-memory state of the others alone."""
    village_id = village_id or villages.default_village_id()
    from core import demo_caller

    demo_caller.reset()
    if not keep_others:
        await db.reset()
        await db.clear_cloud()
        from core import services

        services.reset_chat_state()
    spec = await seed_village(village_id)
    if not keep_others:
        for other in villages.village_ids():
            if other != village_id:
                await seed_village(other)
    from core.block_data import seed_checkins

    for vid in ([village_id] if keep_others else villages.village_ids()):
        await seed_checkins(vid)  # group villages: today's door-knock check-ins (no-op for villages without that data)
    people = spec["blueprint"]["people"]
    def _token_name(name: str) -> str:
        words = [w for w in name.split() if w.rstrip(".").lower() not in {"mr", "mrs", "ms", "dr", "the"}]
        return (words or name.split() or ["member"])[0].lower()

    tokens = {_token_name(str(p["name"])): p["id"] for p in people if (spec.get("channels", {}).get(p["id"]) or [])}
    tokens["control"] = "control"
    return {
        "village": village_id,
        "villages": villages.village_ids(),
        "members": len([m for m in db.members.values() if m.get("village") == village_id]),
        "views": len(spec["views"]),
        "events": len(db.events),
        "tokens": tokens,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", "--village", dest="village", default=None)
    args = parser.parse_args()
    print(json.dumps(await reset_demo(args.village), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
