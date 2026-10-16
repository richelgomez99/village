from __future__ import annotations

import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.builder.tools import TOOL_NAMES, all_tools


def test_all_tools_are_registered_and_closed() -> None:
    tools = all_tools()

    assert set(tools) == TOOL_NAMES
    for name, tool in tools.items():
        assert tool["name"] == name
        assert tool["input_schema"]["additionalProperties"] is False
        Draft202012Validator.check_schema(tool["input_schema"])


def test_extract_blueprint_accepts_contract_shaped_payload() -> None:
    tool = all_tools()["extract_blueprint"]
    payload = {
        "kind": "care",
        "people": [
            {
                "id": "m_carmen",
                "name": "Carmen Reyes",
                "relation": "mother",
                "role": "care_recipient",
                "view": "elder",
                "profile": {
                    "lang": "es",
                    "memory": "mild_lapses",
                    "tech_comfort": "phone",
                    "preferred_channels": ["phone_line", "fridge_card"],
                    "quiet_hours": "21:30-07:00",
                    "evidence": [{"field": "quiet_hours", "source_span": {"start": 0, "end": 12}, "quote": "After 9:30"}],
                },
                "consent": {"ai_calls": None, "app_prompts": None, "money_verifier": False},
                "reason": "Vulnerable center of the village.",
            },
            {
                "id": "m_ana",
                "name": "Ana Reyes",
                "relation": "daughter",
                "role": "coordinator",
                "view": "coordinator",
                "profile": {"lang": "en", "memory": "typical", "tech_comfort": "app", "preferred_channels": ["app"]},
                "consent": {"ai_calls": True, "app_prompts": True, "money_verifier": True},
                "reason": "Speaker and coordinator.",
            },
        ],
        "edges": [{"from": "m_ana", "to": "m_carmen", "kind": "coordinates", "label": "coordinates care"}],
        "needs": [
            {
                "id": "n_scam_calls",
                "text": "Someone pretended to be Marco and asked for money.",
                "priority": 1,
                "domain": "money",
                "life_area": "money",
                "subject_member_ids": ["m_carmen", "m_ana"],
                "source_span": {"start": 13, "end": 55},
            }
        ],
        "rules": ["money_verify_with_member", "money_never_moves", "quiet_hours"],
        "life_areas": [
            {
                "id": "money",
                "label": "Money",
                "need_ids": ["n_scam_calls"],
                "rules": ["R-MONEY-VERIFY"],
                "trusted_contacts": ["m_ana"],
            }
        ],
        "questions": ["Anyone else verifies money requests?"],
    }

    Draft202012Validator(tool["input_schema"]).validate(payload)


def test_extract_blueprint_rejects_unknown_fields() -> None:
    tool = all_tools()["extract_blueprint"]
    validator = Draft202012Validator(tool["input_schema"])

    errors = list(validator.iter_errors({"kind": "care", "extra": True}))

    assert any("Additional properties" in error.message for error in errors)
