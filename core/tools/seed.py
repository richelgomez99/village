"""Seed any registered village: `python -m core.tools.seed --village <id> [--keep]`.

Villages are listed in data/villages/index.json (spec fixture + data file + optional seeds).
`--keep` seeds this village next to the ones already loaded (when reset_demo supports it).
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json

from core import village
from core.fixtures import reset_demo


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--village", default=None, choices=village.village_ids() or None,
                        help="village id (default: DEMO_VILLAGE_ID / registry default)")
    parser.add_argument("--keep", action="store_true", help="keep other villages already seeded")
    parser.add_argument("--no-memory", action="store_true", help="skip writing founding facts to Agent Memory")
    args = parser.parse_args()
    village_id = args.village or village.default_village_id()
    kwargs = {}
    if args.keep and "keep_others" in inspect.signature(reset_demo).parameters:
        kwargs["keep_others"] = True
    out = await reset_demo(village_id, **kwargs)
    if not args.no_memory:
        out["founding_facts"] = await seed_founding_memory()
    print(json.dumps(out, indent=2))


async def seed_founding_memory() -> dict:
    """Write each village's founding facts (data file `memory_seed`) to Agent Memory, idempotently:
    ids already in the shared outbox ledger (var/memory/outbox.jsonl) are skipped, so a reseed never
    duplicates. Without SURREAL_MEMORY_* configured the writes fail soft and stay queued for Core."""
    from core.memory.client import get_client
    from core.memory.founding import enqueue_founding
    from core.memory.outbox import Outbox

    ob = Outbox(client=get_client())
    before = set(ob.items)
    new = enqueue_founding(ob)
    fresh = [i for i in ob.items.values() if i["id"] not in before]
    sent = 0
    for item in fresh:
        try:
            res = await ob._send(item)
        except Exception:  # noqa: BLE001
            res = {"degraded": True}
        if not res.get("degraded"):
            item["status"] = "sent"
            ob._append({"op": "sent", "id": item["id"], "result": {k: res.get(k) for k in ("am_id", "fact_id")}})
            sent += 1
    total = sum(1 for i in ob.items if i.startswith("founding:"))
    return {"total": total, "new": new, "sent_now": sent}


if __name__ == "__main__":
    asyncio.run(main())
