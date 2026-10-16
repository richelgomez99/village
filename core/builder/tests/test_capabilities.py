from __future__ import annotations

import json

from core.builder.capabilities import decision_rows, list_capabilities, plan_capabilities
from core.builder.decisions import mode_of
from core.builder.paths import FIXTURES


def _fx(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_catalog_has_eight_capabilities_with_required_fields() -> None:
    caps = {c["id"]: c for c in list_capabilities()}
    assert set(caps) == {"phone_line", "receptionist_line", "is_it_my_turn", "dashboard", "village_chat", "fridge_card", "refill_day", "check_in_call"}
    for c in caps.values():
        for key in ("applies_when", "fits", "cost_to_person", "risk_class", "implements"):
            assert key in c, (c["id"], key)


def test_reyes_choices_per_person() -> None:
    plan = plan_capabilities(_fx("reyes_spec.json"))
    assert set(plan.for_member("m_carmen")) == {"phone_line", "check_in_call", "fridge_card"}
    assert set(plan.for_member("m_marco")) == {"is_it_my_turn", "refill_day"}
    assert set(plan.for_member("m_ana")) == {"dashboard", "village_chat"}
    # receptionist waits for the second attempt (Evolve proposes it)
    assert any(r.capability == "receptionist_line" and "second" in r.reason for r in plan.rejected)
    # a second attempt flips it on
    plan2 = plan_capabilities(_fx("reyes_spec.json"), signals={"money_attempts": 2})
    assert "receptionist_line" in plan2.for_member("m_carmen")


def test_block_chooses_differently() -> None:
    reyes = plan_capabilities(_fx("reyes_spec.json")).as_dict()
    block = plan_capabilities(_fx("block_spec.json"))
    assert set(block.for_member("b_tanya")) == {"dashboard", "village_chat"}
    assert {"phone_line", "check_in_call"} <= set(block.for_member("b_alvarez"))
    used = {c for caps in block.as_dict().values() for c in caps}
    assert not used & {"fridge_card", "refill_day"}
    assert block.as_dict() != reyes


def test_decision_rows_carry_reason_and_mode() -> None:
    spec = _fx("reyes_spec.json")
    rows = decision_rows("v_reyes", plan_capabilities(spec), spec["blueprint"]["people"])
    carmen = next(r for r in rows if r["refs"][0]["id"] == "m_carmen")
    assert carmen["text"].startswith("Mamá: ")
    assert "phone line" in carmen["text"] and "fits tech_comfort phone" in carmen["text"]
    assert mode_of(carmen) == "acted_alone"
    assert all(len(r["text"]) <= 400 for r in rows)
