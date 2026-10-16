from __future__ import annotations

from datetime import datetime
from typing import Any

from core.clock import clock
from core.db import db

_booted = False


async def tick() -> dict[str, int]:
    """Close verifications past deadline through the gate SM (timeout + incident emits)."""
    from core import services

    closed = 0
    now = clock.now()
    for verification in list(db.verifications.values()):
        if verification.get("state") not in {"pending", "default_spoken"}:
            continue
        if datetime.fromisoformat(verification["deadline"]) > now:
            continue
        row, written = await services.apply_verification_step(
            verification,
            {"type": "tick"},
            actor="scheduler",
            source={"kind": "system", "ref": "scheduler"},
        )
        if row is not None and any(ev["kind"] == "verification_timeout" for ev in written):
            closed += 1
    result: dict[str, Any] = {"verification_timeouts": closed}
    nudges = await services.rota_nudge_tick() if hasattr(services, "rota_nudge_tick") else 0
    result["nudges"] = nudges
    return result


async def recover() -> dict[str, int]:
    """Boot recovery (T017): the first tick closes past-deadline rows; rows still open are
    never redialed when `call_placed_at` is set, and are dialed once when it is not."""
    from core.dialer import dial_verification

    result = await tick()
    redials = 0
    skipped = 0
    for row in list(db.verifications.values()):
        if row.get("state") != "pending":
            continue
        if row.get("call_placed_at"):
            skipped += 1
            continue
        outcome = await dial_verification(row["id"])
        redials += 1 if outcome.get("placed") else 0
    return {**result, "dialed": redials, "not_redialed": skipped}
