import asyncio

from core import bindings_v3, block_data
from core import village as villages

DATA = {"plans": {"shift_today": {"title": "This shift", "items": [{"text": "x", "owner": "b_x", "status": "done"}, "y"]}}}


def _fake(monkeypatch, data=DATA):
    monkeypatch.setattr(villages, "village_data", lambda vid: data)
    bindings_v3.PLANS.pop(("v_any", "shift_today"), None)


def test_plan_falls_back_to_village_data(monkeypatch):
    _fake(monkeypatch)
    got = bindings_v3.plan("v_any", "shift_today")
    assert got["title"] == "This shift"
    assert [(i["text"], i["status"]) for i in got["items"]] == [("x", "done"), ("y", "open")]
    assert got["items"][0]["owner"] == "b_x"
    assert bindings_v3.plan("v_any", "nope") == {"items": []}


def test_set_plan_item_on_data_plan(monkeypatch):
    _fake(monkeypatch)

    async def noop(*a, **k):
        return None

    from core.ws_hub import hub
    monkeypatch.setattr(hub, "push_binds", noop)
    try:
        got = asyncio.run(bindings_v3.set_plan_item("v_any", "shift_today", 1, status="done", owner="b_y"))
        assert got["items"][1] == {"text": "y", "status": "done", "owner": "b_y"}
        assert bindings_v3.plan("v_any", "shift_today")["items"][1]["status"] == "done"
    finally:
        bindings_v3.PLANS.pop(("v_any", "shift_today"), None)


def test_claims_checked_vs_checking(monkeypatch):
    src = {"name": "City OEM", "url": "https://example.org"}
    data = {"rumors": [
        {"id": "r1", "claim": "Power back at 6", "official_source": src, "finding": "Utility says 9pm", "checked_at": "14:05"},
        {"id": "r2", "claim": "Water unsafe", "official_source": src},
    ]}
    monkeypatch.setattr(villages, "village_data", lambda vid: data)
    rows = block_data.claims("v_any")
    assert rows[0]["status"] == "checked"
    assert rows[0]["text"]["en"] == "Heard: Power back at 6 · Utility says 9pm (City OEM, 14:05)"
    assert rows[1]["status"] == "checking"
    assert rows[1]["text"]["en"] == "Heard: Water unsafe · Check: City OEM"
