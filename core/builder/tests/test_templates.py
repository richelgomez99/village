from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.builder import templates  # noqa: E402
from core.builder.validate import validate_spec  # noqa: E402


def test_fixture_fallbacks_validate_with_d22_mapping() -> None:
    for kind in ("care", "block"):
        spec = templates.spec(kind, village_id=f"v_test_{kind}")
        report = validate_spec(spec)

        assert report.ok, report.errors
        assert spec["village"]["id"] == f"v_test_{kind}"
        assert all(printable["kind"] == "fridge_card" for printable in spec["printables"])


def test_member_id_remap_rewrites_structured_references() -> None:
    spec = templates.spec(
        "care",
        village_id="v_family",
        member_id_map={"m_carmen": "m_elena", "m_ana": "m_sofia", "m_marco": "m_raul", "m_lucia": "m_ines"},
    )
    report = validate_spec(spec)

    assert report.ok, report.errors
    people = {person["id"] for person in spec["blueprint"]["people"]}
    assert people == {"m_elena", "m_sofia", "m_raul", "m_ines"}
    assert set(spec["channels"]) == people
    assert spec["village"]["coordinator_id"] == "m_sofia"
    assert spec["village"]["care_recipient_id"] == "m_elena"
    assert spec["views"]["coordinator"]["elements"]["dose"]["props"]["subject"] == "m_elena"
    assert spec["policies"][0]["applies_to_member_ids"] == ["m_elena"]


def test_template_view_per_role_with_remap_and_decision_row() -> None:
    from core.builder.mapping import elder_view_problems

    v = templates.view("care", "coordinator", member_id_map={"m_carmen": "m_elena"})
    assert v["elements"]["dose"]["props"]["subject"] == "m_elena"
    assert templates.view("block", "volunteer")["theme"] in ("family", "dashboard")
    assert elder_view_problems(templates.view("care", "elder")) == []
    row = templates.template_decision("v_x", "helper", "timeout after 45 s")
    assert row["text"] == "template helper: timeout after 45 s" and row["kind"] == "note"
    fx = templates.fixture_mode("care", "v_fx")
    assert fx["village"]["status"] == "draft" and validate_spec(fx).ok
    renamed = templates.name_map({"m_carmen": {"name": "Elena Ruiz"}}, fx)
    assert renamed["blueprint"]["people"][0]["name"] == "Elena Ruiz"


def test_elder_view_check_catches_d22_violations() -> None:
    from core.builder.mapping import elder_view_problems

    v = templates.view("care", "elder")
    v["elements"].pop("tonight")
    v["elements"]["s"]["children"].remove("tonight")
    assert "missing TonightCard" in elder_view_problems(v)
