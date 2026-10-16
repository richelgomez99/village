"""Founding facts -> memory (village-agnostic, D30).

Each village's data file (data/villages/index.json -> "data") may carry a `memory_seed` list:
what the group told Village when it was founded, transcribed from that same data file.
Each row: {id, entity, key, value, text, area, source{kind, ref, secs?, quote?}}.
`founding_drafts(village)` turns them into fact drafts shaped like ledger drafts, with stable
ids so reseeding never duplicates (outbox item id = "founding:<village>:<id>").
"""
from __future__ import annotations

from typing import Any

from core import village as village_reg
from core.memory import conventions as cv

AGENT = "village"
SEED_AT = "2026-10-10T12:00:00-04:00"  # founding day; rows may override with observed_at


def founding_drafts(village: str) -> list[dict[str, Any]]:
    data = village_reg.village_data(village) or {}
    out: list[dict[str, Any]] = []
    for row in data.get("memory_seed") or []:
        src = dict(row.get("source") or {"kind": "system", "ref": "seed"})
        at = row.get("observed_at") or data.get("founded_at") or SEED_AT
        out.append({
            "village": village, "entity": row["entity"], "key": cv.norm_key(row["key"]),
            "value": str(row["value"])[:400], "text": str(row.get("text") or row["value"])[:300],
            "observed_at": cv.iso(at), "recorded_at": cv.iso(at), "source": src,
            "event_id": f"ev_founding_{row['id']}", "agent": AGENT, "rule_id": None,
            "extra_labels": {"area": row.get("area") or "general", "founding": row["id"]},
            "_item_id": f"founding:{village}:{row['id']}",
        })
    return out


def enqueue_founding(outbox: Any, villages: list[str] | None = None) -> int:
    """Idempotent: same ids -> no duplicates."""
    n = 0
    for vid in villages or village_reg.village_ids():
        for d in founding_drafts(vid):
            args = {k: d[k] for k in ("entity", "key", "value", "source", "village", "agent", "observed_at",
                                      "event_id", "rule_id", "extra_labels")}
            n += outbox.enqueue(d["_item_id"], "fact", args)
    return n
