from __future__ import annotations

from typing import Any


def builder_decision(village_id: str, text: str, *, kind: str = "decision", refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "village_id": village_id,
        "actor": "builder",
        "kind": kind,
        "text": text[:400],
        "refs": refs or [],
        "source": {"kind": "system", "ref": "builder"},
    }
