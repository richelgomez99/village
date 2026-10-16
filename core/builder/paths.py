from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
FIXTURES = CONTRACTS / "fixtures"
SCHEMAS = CONTRACTS / "schemas"
PROMPTS = ROOT / "prompts"
DATA = ROOT / "data"
