"""Watcher trigger (D13/D19): the 2nd money_request claiming the same member within 7 days -> detector ->
consider_options -> propose. Fires from the verification resolution path (services port) or from
POST /villages/{id}/evolve/trigger (control token, demo)."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db

log = logging.getLogger("village.evolve")

AUTO_DELAY_S = float(os.environ.get("VILLAGE_EVOLVE_DELAY_S", "2.0"))
_PENDING: dict[str, asyncio.Task[Any]] = {}
LAST: dict[str, dict[str, Any]] = {}


def _labels() -> dict[str, dict[str, Any]]:
    try:
        from evals.session_eval import sessions_with_label

        return sessions_with_label()
    except Exception:  # noqa: BLE001
        return {}


def patterns(village_id: str) -> list[dict[str, Any]]:
    from evals.detector import detect_patterns

    events = [e for e in db.events if e.get("village", village_id) == village_id]
    return detect_patterns(village_id, events, now=clock.now().isoformat(), session_labels=_labels())


def _forced_pattern(village_id: str) -> dict[str, Any] | None:
    """Demo trigger with < 2 recent requests: use every money_request on record for the most-claimed member."""
    from evals.detector import evidence_for

    money = [e for e in db.events if e.get("kind") == "money_request" and e.get("village", village_id) == village_id
             and (e.get("payload") or {}).get("claimed_member_id")]
    if not money:
        return None
    by: dict[str, list[dict[str, Any]]] = {}
    for e in money:
        by.setdefault(e["payload"]["claimed_member_id"], []).append(e)
    claimed, evs = max(by.items(), key=lambda kv: len(kv[1]))
    today = clock.now().date().isoformat()
    evidence: list[dict[str, Any]] = []
    for e in sorted(evs, key=lambda x: x["at"]):
        evidence.extend(evidence_for(e, today=today, session_labels=_labels()))
    name = villages.first_name(village_id, claimed)
    return {"pattern": "repeat_money_request", "village": village_id, "subject": evs[0]["payload"].get("subject"),
            "claimed_member_id": claimed, "count": len(evs), "window_days": 7, "event_ids": [e["id"] for e in evs],
            "detected_by": "arize_eval" if any("eval" in r for r in evidence) else "memory_pattern",
            "text": f"{len(evs)} money request{'s' if len(evs) != 1 else ''} in {name}'s name on record (demo trigger).",
            "evidence": evidence[:12]}


async def run(village_id: str, *, force: bool = False, source: str = "watcher") -> dict[str, Any]:
    """detector -> consider_options -> propose. Returns {proposal, options, pattern, timings} (or {skipped})."""
    from core import services
    from core.evolve.options import consider_options
    from core.evolve.proposals import find_active, propose

    t0 = time.perf_counter()
    pats = patterns(village_id)
    pattern = pats[0] if pats else (_forced_pattern(village_id) if force else None)
    if pattern is None:
        return {"skipped": "no pattern (needs 2 money requests in one member's name within 7 days)"}
    key = f"{pattern.get('pattern', 'manual')}:{pattern.get('subject')}:{pattern.get('claimed_member_id')}"
    existing = find_active(village_id, key)
    if existing is not None:
        return {"skipped": f"already proposed ({existing['proposal']['id']}: {existing['proposal']['status']})",
                "proposal": existing["proposal"]}
    await services.ledger(village_id, f"watch:{village_id}:{len(db.events)}", "done", "Watcher · pattern check",
                          result=pattern.get("text", "")[:400], role="Watcher")
    t1 = time.perf_counter()
    options = await consider_options(village_id, pattern)
    t2 = time.perf_counter()
    proposal = await propose(village_id, pattern, options)
    t3 = time.perf_counter()
    timings = {"detect_ms": int((t1 - t0) * 1000), "options_ms": int((t2 - t1) * 1000), "propose_ms": int((t3 - t2) * 1000),
               "options_mode": options.get("mode"), "source": source}
    LAST[village_id] = timings
    return {"proposal": proposal, "options": options, "pattern": {k: v for k, v in pattern.items() if k != "evidence"}, "timings": timings}


def auto_enabled() -> bool:
    flag = os.environ.get("VILLAGE_EVOLVE_AUTO", "").lower()
    if flag in {"on", "1", "true"}:
        return True
    if flag in {"off", "0", "false"}:
        return False
    return "PYTEST_CURRENT_TEST" not in os.environ  # default on, except inside unrelated tests


def on_verification_resolved(village_id: str, row: dict[str, Any]) -> None:
    """services port: a money verification just resolved. Never raises; runs in the background."""
    try:
        if not auto_enabled() or (row.get("request") or {}).get("origin") == "screen_caller_probe":
            return
        claimed = row.get("claimed_member_id")
        if not claimed or not any(p.get("claimed_member_id") == claimed for p in patterns(village_id)):
            return
        prev = _PENDING.get(village_id)
        if prev is not None and not prev.done():
            return

        async def go() -> None:
            await asyncio.sleep(AUTO_DELAY_S)  # let the incident post land first
            try:
                await run(village_id, source="verification_resolved")
            except Exception:  # noqa: BLE001
                log.exception("evolve auto trigger failed")

        _PENDING[village_id] = asyncio.get_running_loop().create_task(go())
    except Exception:  # noqa: BLE001
        log.exception("evolve trigger hook failed")
