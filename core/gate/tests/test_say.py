from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.gate.say import TEMPLATES, say


def test_money_confirmed_uses_gendered_spanish_pronoun():
    line = say("money_confirmed", claimed_name="Lucía", pronoun="she")
    assert "sí fue ella" in line["es"]
    assert "really her" in line["en"]


def test_policy_templates_include_required_gate_owned_lines():
    required = {
        "money_hold",
        "money_denied",
        "money_timeout",
        "money_confirmed",
        "money_unknown",
        "money_never",
        "money_share_disclosure",
        "dd_report",
        "advise_911_first",
        "no_dose_advice",
        "schedule_readback",
        "family_notified",
        "core_down",
        "money_core_down",
    }
    assert required.issubset(TEMPLATES)


def test_double_dose_report_is_verbatim_template():
    line = say("dd_report", logged_time="8:02", on_duty_name="Marco")
    assert line["es"] == "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco."
    assert "don't take" not in line["en"].lower()
