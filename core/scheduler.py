from __future__ import annotations

from datetime import datetime

from core.clock import clock
from core.db import db


async def tick() -> dict[str, int]:
    closed = 0
    now = clock.now()
    for verification in list(db.verifications.values()):
        if verification.get("state") != "pending":
            continue
        deadline = datetime.fromisoformat(verification["deadline"])
        if deadline > now:
            continue
        updated = await db.cas_update(
            "verification",
            verification["id"],
            verification.get("version", 0),
            {
                "state": "timed_out",
                "status": "timeout",
                "resolved_at": now.isoformat(),
                "transitions": [
                    *verification.get("transitions", []),
                    {"at": now.isoformat(), "event": "tick", "to": "timed_out"},
                ],
            },
        )
        if not updated:
            continue
        await db.create_event({
            "id": f"ev_timeout_{verification['id']}",
            "village": verification["village"],
            "kind": "verification_timeout",
            "payload": {
                "verification_id": verification["id"],
                "claimed_member_id": verification["claimed_member_id"],
                "reason": "deadline",
                "state": "timed_out",
            },
            "actor": "scheduler",
            "source": {"kind": "system", "ref": "scheduler"},
            "decision_id": None,
            "at": now.isoformat(),
        })
        closed += 1
    return {"verification_timeouts": closed}
