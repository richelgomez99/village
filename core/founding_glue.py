"""Core-side founding frames for the Control Room (core-glue T3).

The builder emits `counter{intake_covered}` after each founding answer; Core derives the two frames the
kit's founding view reads from the builder's own state (SESSIONS / RUNS):
  control{counter name:"intake_coverage", value, of}   coverage meter
  control{blueprint stage:"questions", items}           next question first, then the open gaps
Additive and read-only: nothing here writes builder state. Never includes the family word."""
from __future__ import annotations

from typing import Any


def founding_frames(village_id: str) -> list[tuple[str, dict[str, Any]]]:
    try:
        from core.builder.founding import RUNS, SESSIONS
    except Exception:  # builder lane absent
        return []
    session = SESSIONS.get(village_id)
    intake = getattr(session, "intake", None)
    if intake is None:
        return []
    covered, total = len(intake.covered()), len(intake.topics)
    out: list[tuple[str, dict[str, Any]]] = [
        ("counter", {"name": "intake_coverage", "value": covered, "of": total, "label": "intake coverage"})
    ]
    items: list[dict[str, Any]] = []
    run = RUNS.get(village_id)
    turns = getattr(run, "turns", None) or []
    nxt = turns[-1].get("next") if turns else None
    if not nxt:
        q = getattr(session, "question", None)
        nxt = getattr(q, "text", None)
    if nxt and nxt != "review":
        items.append({"question": str(nxt)[:300]})
    items += [{"question": str(gap)[:300], "gap": True} for gap in intake.gaps()]
    payload: dict[str, Any] = {"village": village_id, "stage": "questions", "items": items[:24]}
    trace_id = getattr(run, "trace_id", None)
    if trace_id:
        payload["trace_id"] = trace_id
    out.append(("blueprint", payload))
    return out
