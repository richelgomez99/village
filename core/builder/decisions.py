from __future__ import annotations

from typing import Any

MODES = {"acted_alone", "asked_human", "refused"}


def builder_decision(
    village_id: str,
    text: str,
    *,
    kind: str = "decision",
    refs: list[dict[str, Any]] | None = None,
    mode: str = "acted_alone",
    rule_id: str | None = None,
    source: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Decision row (decision.schema.json 1.2.1, top-level autonomy `mode`, D23 #3)."""
    if mode not in MODES:
        raise ValueError(f"bad mode {mode}")
    row: dict[str, Any] = {
        "village_id": village_id,
        "actor": "builder",
        "kind": kind,
        "mode": mode,
        "text": text[: 280 if kind == "plan" else 400],
        "refs": list(refs or [])[:12],
        "source": source or {"kind": "system", "ref": "builder"},
    }
    if rule_id:
        row["rule_id"] = rule_id
    if trace_id:
        row["trace_id"] = trace_id
    return row


def mode_of(row: dict[str, Any]) -> str | None:
    return row.get("mode") or next((r["id"] for r in row.get("refs", []) if r.get("kind") == "mode"), None)
