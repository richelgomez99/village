"""Contract-shaped WS `control` frames (ws_messages.schema.json#/$defs/control)."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def now_iso() -> str:
    try:
        from core.clock import clock  # type: ignore

        return clock.now().isoformat(timespec="seconds")
    except Exception:
        return datetime.now().astimezone().isoformat(timespec="seconds")


def hhmm() -> str:
    return now_iso()[11:16]


def reasoning(village: str, text: str, kind: str = "note", trace_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"source": "builder", "kind": kind, "text": text[:400], "village": village}
    if trace_id:
        payload["trace_id"] = trace_id
    return {"type": "control", "kind": "reasoning", "payload": payload, "at": now_iso()}


def counter(name: str, value: float, label: str, of: float | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "value": value, "label": label[:80]}
    if of is not None:
        payload["of"] = of
    return {"type": "control", "kind": "counter", "payload": payload, "at": now_iso()}


def blueprint(village: str, stage: str, items: list[dict[str, Any]], trace_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"village": village, "stage": stage, "items": items[:24]}
    if trace_id:
        payload["trace_id"] = trace_id
    return {"type": "control", "kind": "blueprint", "payload": payload, "at": now_iso()}


def ledger_line(status: str, what: str, result: str) -> str:
    """D23 #4 ledger row: `time · status · what · result`."""
    return f"{hhmm()} · {status} · {what} · {result}"
