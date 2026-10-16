#!/usr/bin/env python
"""Validate a VillageSpec file against the contract (JSON Schema + pydantic mirror + invariants).
  uv run python scripts/validate_spec.py data/builder/out/care/spec.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.builder.validate import validate_spec  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_spec.py <spec.json>")
        return 2
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    report = validate_spec(spec)
    if report.ok:
        print(f"OK {argv[1]} rev={spec.get('rev')} views={list(spec.get('views', {}))}" + (f" warnings={len(report.warnings)}" if report.warnings else ""))
        return 0
    print(f"INVALID {argv[1]}")
    for e in report.errors[:20]:
        print(f"  {e}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
