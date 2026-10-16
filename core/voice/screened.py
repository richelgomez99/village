"""Screened-call log (D19): every receptionist call, with or without a money claim, lands in `calls:screened`.

Outcomes: message_taken | passed_through | held | refused | hung_up. Written by `relay_message` (message_taken) and
by the post-call webhook for receptionist calls (receptionist=on, caller unknown). In memory, like the rest of the
demo state; core/bindings_v3.screened_calls merges `rows(village_id)`.
"""
from __future__ import annotations

from typing import Any

OUTCOMES = ("message_taken", "passed_through", "held", "refused", "hung_up")
_ROWS: dict[str, dict[str, Any]] = {}  # conversation_id -> row


def record(village_id: str, conversation_id: str, outcome: str, *, at: str, claimed: str | None = None,
           message: str | None = None, callback: str | None = None, keep_existing: bool = False) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    existing = _ROWS.get(conversation_id)
    if existing and keep_existing:
        return existing
    row = {**(existing or {}), "village_id": village_id, "conversation_id": conversation_id, "outcome": outcome, "at": existing.get("at", at) if existing else at}
    for key, value in (("claimed", claimed), ("say", message), ("callback", callback)):
        if value:
            row[key] = value
    _ROWS[conversation_id] = row
    return row


def get(conversation_id: str) -> dict[str, Any] | None:
    return _ROWS.get(conversation_id)


def rows(village_id: str) -> list[dict[str, Any]]:
    return [{k: v for k, v in r.items() if k not in {"village_id", "conversation_id"}} for r in _ROWS.values() if r["village_id"] == village_id]


def reset() -> None:
    _ROWS.clear()
