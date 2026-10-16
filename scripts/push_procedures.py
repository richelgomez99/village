from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_DIR = ROOT / "agents" / "procedures"


def load_procedure(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not data.get("steps"):
        raise ValueError(f"{path}: procedure_validation_failed /steps must be non-empty")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("procedures", nargs="*")
    args = parser.parse_args()

    paths = sorted(PROCEDURE_DIR.glob("*.json")) if args.all or not args.procedures else [
        PROCEDURE_DIR / f"{name}.json" if not name.endswith(".json") else Path(name) for name in args.procedures
    ]

    payloads = []
    for path in paths:
        data = load_procedure(path)
        payloads.append({
            "name": data.get("name", path.stem),
            "agent_id": args.agent or "${ELEVENLABS_AGENT_MOM_LINE_ID}",
            "content": json.dumps({"steps": data["steps"]}, separators=(",", ":")),
        })

    if args.dry_run:
        print(json.dumps({"procedures": payloads}, indent=2))
        return 0

    raise SystemExit("Live procedure push is intentionally disabled until ELEVENLABS_API_KEY is available; rerun with --dry-run today.")


if __name__ == "__main__":
    raise SystemExit(main())

