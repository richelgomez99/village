from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from core.db import db
from core.settings import ROOT


FIXTURES = ROOT / "contracts" / "fixtures"
DATA = ROOT / "data" / "villages"


def load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


async def reset_demo(village_id: str = "v_reyes") -> dict[str, Any]:
    await db.reset()
    await db.clear_cloud()
    spec = load_json(FIXTURES / "reyes_spec.json")
    events = load_json(FIXTURES / "events_reyes_seed.json")["events"]
    family = load_json(DATA / "reyes_family.json")

    await db.upsert_record("village", village_id, {"id": village_id, **spec["village"]})
    await db.upsert_record(
        "spec_rev",
        f"reyes_{spec['rev']}",
        {"id": f"sr_reyes_{spec['rev']}", "village": village_id, "rev": spec["rev"], "spec": spec, "published": True},
    )
    for person in spec["blueprint"]["people"]:
        await db.upsert_record("member", person["id"], {"village": village_id, **person})
    for role, view in spec["views"].items():
        await db.upsert_record("view", f"reyes_{role}", {"id": f"view_reyes_{role}", "village": village_id, "role": role, "rev": spec["rev"], "spec": view})
    for event in events:
        await db.create_event(event)

    meds = family.get("medications", [])
    lisinopril = [med for med in meds if med.get("name") == "lisinopril"]
    db.prescriptions[village_id] = [
        {
            "med_id": "med_lisinopril_5",
            "name": "lisinopril",
            "dose": "5 mg",
            "valid_from": "2026-09-01",
            "valid_until": "2026-10-03",
            "source": {"kind": "system", "ref": "seed", "quote": "Prior bottle in cabinet"},
            "prescriber": "Dr. Park",
        },
        {
            "med_id": "med_lisinopril_10",
            "name": "lisinopril",
            "dose": "10 mg",
            "valid_from": "2026-10-03",
            "valid_until": None,
            "source": {"kind": "call", "ref": "conv_setup_0003", "secs": 88},
            "prescriber": "Dr. Park",
        },
    ]
    if not lisinopril:
        pass
    from core import services

    services.reset_chat_state()
    seed = load_json(FIXTURES / "messages_reyes_seed.json")["messages"]
    # contracts: core seeds the rows before the live scam beat (14:02); the live flow writes the rest.
    for message in [row for row in seed if row["at"] < "2026-10-16T14:02:00-04:00"]:
        await db.create_message({**message, "village": village_id})
    return {
        "village": village_id,
        "members": len(db.members),
        "views": len(spec["views"]),
        "events": len(db.events),
        "tokens": {"carmen": "m_carmen", "ana": "m_ana", "marco": "m_marco", "control": "control"},
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", default="v_reyes")
    args = parser.parse_args()
    print(json.dumps(await reset_demo(args.reset), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
