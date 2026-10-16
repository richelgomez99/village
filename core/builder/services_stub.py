from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class MemoryServices:
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    frames: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)

    async def store_spec(self, village_id: str, spec: dict[str, Any], status: str = "draft") -> dict[str, Any]:
        stored = deepcopy(spec)
        stored.setdefault("village", {})["id"] = village_id
        stored["village"]["status"] = status
        self.specs[village_id] = stored
        return stored

    async def get_spec(self, village_id: str) -> dict[str, Any] | None:
        spec = self.specs.get(village_id)
        return deepcopy(spec) if spec else None

    async def broadcast_control(self, village_id: str, frame: dict[str, Any]) -> None:
        self.frames.append(deepcopy(frame))

    async def broadcast_patch(self, village_id: str, frame: dict[str, Any]) -> None:
        """Draft-view patch for one role (D33 progressive draft); core sends it to that role's sockets."""
        self.frames.append(deepcopy(frame))

    async def record_decision(self, row: dict[str, Any]) -> dict[str, Any]:
        row = deepcopy(row)
        row.setdefault("id", f"dc_{len(self.decisions) + 1:04d}")
        row.setdefault("at", now_iso())
        row.setdefault("source", {"kind": "system", "ref": "builder"})
        self.decisions.append(row)
        return row

    async def decisions_for(self, village_id: str, limit: int = 60) -> list[dict[str, Any]]:
        rows = [d for d in self.decisions if d.get("village_id") == village_id or d.get("village") == village_id]
        return deepcopy(rows[-limit:])

    async def facts_for(self, village_id: str) -> list[dict[str, Any]]:
        return deepcopy([f for f in self.facts if f.get("village") == village_id or f.get("village_id") == village_id])

    async def events_for(self, village_id: str, kinds: list[str] | None = None, limit: int = 60) -> list[dict[str, Any]]:
        rows = [e for e in self.events if e.get("village") == village_id or e.get("village_id") == village_id]
        if kinds:
            rows = [e for e in rows if e.get("kind") in kinds]
        return deepcopy(rows[-limit:])
