"""D24 #11: every incident becomes a test.

When a verification resolves `denied` or `timeout` (verification_denied /
verification_timeout ledger rows), append the call's utterance with its expected
decision to evals/sets/<village_id>.jsonl. `scam_experiment --village <id>` scores the
base set plus this file and reports n_base + n_village. Idempotent per verification id.

    uv run python -m evals.incident_to_test v_reyes      # scan the seed ledger
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.reyes import ROOT

SETS = ROOT / "evals" / "sets"
RESOLVED_KINDS = {"verification_denied": "denied", "verification_timeout": "timeout"}


def set_path(village_id: str, sets_dir: Path = SETS) -> Path:
    return sets_dir / f"{village_id}.jsonl"


def _existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line).get("verification_id") for line in path.read_text().splitlines() if line.strip()}


def row_for(resolution: dict[str, Any], money_event: dict[str, Any]) -> dict[str, Any]:
    p = money_event["payload"]
    claimed = p.get("claimed_member_id")
    ver_id = resolution["payload"]["verification_id"]
    src = money_event.get("source") or {}
    return {
        "id": f"inc_{ver_id}",
        "verification_id": ver_id,
        "utterance": src.get("quote") or p.get("utterance", ""),
        # What the gate must do with this utterance next time: verify with the claimed member,
        # or (nobody to verify with) advise not to send.
        "expected_decision": "verify_with_member" if claimed else "advise_do_not_send",
        "is_scam": True,
        "outcome": RESOLVED_KINDS[resolution["kind"]],
        "claimed_identity": p.get("claimed_identity", "unknown"),
        "language": "es" if any(ch in (p.get("utterance") or "") for ch in "áéíóúñ¿¡") else "en",
        "channel": "call",
        "source": {"money_event_id": money_event["id"], "resolution_event_id": resolution.get("id"),
                   "call": f"{src.get('ref')}@{src.get('secs')}", "at": resolution.get("at")},
    }


def on_verification_resolved(village_id: str, resolution: dict[str, Any], events: list[dict[str, Any]],
                             sets_dir: Path = SETS) -> dict[str, Any] | None:
    """Append one row for a denied/timeout verification. Returns the row, or None (not resolved / already there)."""
    if resolution.get("kind") not in RESOLVED_KINDS:
        return None
    ver_id = resolution["payload"].get("verification_id")
    money = next((e for e in events if e.get("kind") == "money_request"
                  and (e.get("payload") or {}).get("verification_id") == ver_id), None)
    if money is None or not ver_id:
        return None
    path = set_path(village_id, sets_dir)
    if ver_id in _existing_ids(path):
        return None
    row = row_for(resolution, money)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def sync_from_events(village_id: str, events: list[dict[str, Any]], sets_dir: Path = SETS) -> list[dict[str, Any]]:
    added = []
    for ev in events:
        row = on_verification_resolved(village_id, ev, events, sets_dir)
        if row:
            added.append(row)
    return added


def main() -> None:
    import sys

    from evals.reyes import seed_events

    village = sys.argv[1] if len(sys.argv) > 1 else "v_reyes"
    added = sync_from_events(village, seed_events(village))
    print(json.dumps({"village": village, "added": len(added), "path": str(set_path(village))}, indent=2))


if __name__ == "__main__":
    main()
