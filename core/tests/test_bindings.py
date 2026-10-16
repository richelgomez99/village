from core.bindings import changed, snapshot_data
from core.fixtures import reset_demo


async def test_elder_dose_binding_hides_med_names() -> None:
    await reset_demo("v_reyes")
    data = snapshot_data("elder", "m_carmen")
    dose = data["facts:dose_event?subject=m_carmen&valid_at=today"]
    assert "meds" not in dose


async def test_coordinator_dose_binding_includes_med_history() -> None:
    await reset_demo("v_reyes")
    data = snapshot_data("coordinator", "m_ana")
    dose = data["facts:dose_event?subject=m_carmen&valid_at=today"]
    assert dose["meds"][1]["dose"] == "10 mg"


async def test_helper_gets_no_dose_change_payload() -> None:
    await reset_demo("v_reyes")
    event = {"kind": "dose", "payload": {"subject": "m_carmen", "slot": "evening"}}
    assert changed(event, "helper", "m_marco") == {}
