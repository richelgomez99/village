"""Receipt helpers (= contracts/schemas/release.schema.json) + schema validation + local store."""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "schemas"
STAGES = ("spec", "daytona_build", "tests", "anchor_qa", "arize_evals", "live")
TZ = ZoneInfo("America/New_York")

Receipt = dict[str, Any]


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def new_receipt(*, release_id: str, village: str, rev: int, previous_live_rev: int | None, attempt: int,
                trigger: str, repair_of: str | None = None, trace_id: str | None = None,
                proposal_id: str | None = None) -> Receipt:
    r: Receipt = {
        "id": release_id,
        "village": village,
        "rev": rev,
        "previous_live_rev": previous_live_rev,
        "live_rev": previous_live_rev,
        "attempt": attempt,
        "trigger": trigger,
        "stages": [{"name": n, "status": "pending", "started": None, "ended": None, "details": {}} for n in STAGES],
        "result": "in_progress",
        "created_at": now_iso(),
    }
    if repair_of:
        r["repair_of"] = repair_of
    if trace_id:
        r["trace_id"] = trace_id
    if proposal_id:
        r["proposal_id"] = proposal_id
    return r


def stage(r: Receipt, name: str) -> dict[str, Any]:
    return r["stages"][STAGES.index(name)]


@lru_cache
def _registry():  # type: ignore[no-untyped-def]
    from referencing import Registry, Resource

    res = []
    for p in SCHEMAS.glob("*.schema.json"):
        doc = json.loads(p.read_text())
        r = Resource.from_contents(doc)
        res.append((doc["$id"], r))
        res.append((p.name, r))
    return Registry().with_resources(res)


@lru_cache
def _validator(name: str, pointer: str = ""):  # type: ignore[no-untyped-def]
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((SCHEMAS / name).read_text())
    if pointer:
        schema = {"$ref": f"{schema['$id']}#{pointer}"}
    return Draft202012Validator(schema, registry=_registry(), format_checker=FormatChecker())


def validate_receipt(r: Receipt) -> list[str]:
    return [f"{'/'.join(map(str, e.path))}: {e.message}"[:300] for e in _validator("release.schema.json").iter_errors(r)]


def validate_control(frame: dict[str, Any]) -> list[str]:
    v = _validator("ws_messages.schema.json", "/$defs/control")
    return [f"{'/'.join(map(str, e.path))}: {e.message}"[:300] for e in v.iter_errors(frame)]


class ReceiptStore:
    """Local JSON store under var/releases/receipts/<village>.json (core can swap for SurrealDB)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT / "var" / "releases" / "receipts"

    def _path(self, village: str) -> Path:
        return self.root / f"{village}.json"

    def all(self, village: str) -> list[Receipt]:
        p = self._path(village)
        return json.loads(p.read_text()) if p.exists() else []

    def put(self, r: Receipt) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        rows = [x for x in self.all(r["village"]) if x["id"] != r["id"]]
        rows.append(r)
        self._path(r["village"]).write_text(json.dumps(rows, indent=1, ensure_ascii=False))

    def get(self, release_id: str) -> Receipt | None:
        if not self.root.exists():
            return None
        for p in self.root.glob("*.json"):
            for r in json.loads(p.read_text()):
                if r["id"] == release_id:
                    return r
        return None
