from core.bindings import changed, snapshot_data
from core.fixtures import reset_demo


async def test_elder_snapshot_has_no_med_names() -> None:
    # D22 / contract 1.2.0 rev 5: the elder view has no dose tracker; whatever it binds must never carry med names
    await reset_demo("v_reyes")
    data = snapshot_data("elder", "m_carmen")
    for value in data.values():
        assert "meds" not in (value if isinstance(value, dict) else {})


async def test_coordinator_dose_binding_includes_med_history() -> None:
    await reset_demo("v_reyes")
    data = snapshot_data("coordinator", "m_ana")
    dose = data["facts:dose_event?subject=m_carmen&valid_at=today"]
    morning = next(slot for slot in dose["slots"] if slot["slot"] == "morning")
    assert "lisinopril 10 mg" in morning["meds"]


async def test_helper_gets_no_dose_change_payload() -> None:
    await reset_demo("v_reyes")
    event = {"kind": "dose", "payload": {"subject": "m_carmen", "slot": "evening"}}
    assert changed(event, "helper", "m_marco") == {}
