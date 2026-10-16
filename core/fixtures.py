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
    spec = load_json(FIXTURES / "reyes_spec.json")
    events = load_json(FIXTURES / "events_reyes_seed.json")["events"]
    family = load_json(DATA / "reyes_family.json")

    db.specs[village_id] = spec
    db.villages[village_id] = spec["village"]
    for person in spec["blueprint"]["people"]:
        db.members[person["id"]] = person
    for role, view in spec["views"].items():
        db.views[(village_id, role)] = view
    for event in events:
        db.events.append(event)

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
            "prescriber": "Dr. Lee",
        },
        {
            "med_id": "med_lisinopril_10",
            "name": "lisinopril",
            "dose": "10 mg",
            "valid_from": "2026-10-03",
            "valid_until": None,
            "source": {"kind": "call", "ref": "conv_setup_0003", "secs": 88},
            "prescriber": "Dr. Lee",
        },
    ]
    if not lisinopril:
        pass
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
