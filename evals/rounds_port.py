"""Evals port for core/watcher/rounds.py (Ports.evals).

rounds.py calls `await rerun_scam_set(village_id)` and reads `caught`/`total`, and
`await detect_patterns(village_id, events)` and reads each pattern's
`claimed_member_id`, `event_ids`, `count`, `text`. Each pattern also carries
`evidence` (proposal.schema.json#/$defs/evidence rows) for the proposal.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from evals import detector


async def rerun_scam_set(village_id: str) -> dict[str, Any]:
    from evals.scam_experiment import run

    mode = "auto" if os.environ.get("VILLAGE_LLM", "off") != "off" else "rules"
    from evals.reyes import ROOT

    report = await asyncio.to_thread(run, mode, village_id, ROOT / "var" / "evals" / "rounds")
    s = report["summary"]
    return {
        "n_caught": s["caught"], "n_total": s["scams"], "n_false_alarms": s["false_alarms"], "n_benign": s["benign"],
        "n_base": s["n_base"], "n_village": s["n_village"],
        # names rounds.py reads
        "caught": s["caught"], "total": s["scams"],
        "headline": report["headline"], "mode": report["mode"], "report": (report.get("paths") or [None])[0],
    }


async def detect_patterns(village_id: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from evals.session_eval import sessions_with_label

        labels = sessions_with_label()
    except Exception:  # noqa: BLE001
        labels = {}
    return detector.detect_patterns(village_id, events, session_labels=labels)
