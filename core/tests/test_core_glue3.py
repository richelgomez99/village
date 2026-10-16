"""core-glue 3 (contract 1.3.2): plan:<id>, calls:screened, facts:history binds in snapshots and changed(),
picked up generically from element props; pushes on plan item change and screened-call resolution."""
from __future__ import annotations

from core import village as villages
from core.bindings import changed, snapshot_data, view_binds
from core.clock import clock
from core.db import db
from core.fixtures import reset_demo
from core.ws_hub import Client, hub


class FakeWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send_json(self, frame: dict) -> None:
        self.frames.append(frame)


def _add_element(vid: str, role: str, el_id: str, el_type: str, bind: str) -> None:
    view = db.views[(vid, role)]
    view["elements"][el_id] = {"type": el_type, "props": {"bind": bind, "title": {"en": el_type}}}
    view["elements"][view.get("root", "s")].setdefault("children", []).append(el_id)


def _coord(vid: str) -> str:
    return villages.coordinator_id(vid)


async def test_new_binds_picked_up_generically() -> None:
    await reset_demo()
    vid = villages.default_village_id()
    subject = villages.care_recipient_id(vid)
    _add_element(vid, "coordinator", "plan1", "PlanBoard", "plan:holiday")
    _add_element(vid, "coordinator", "calls", "ScreenedCalls", "calls:screened")
    _add_element(vid, "coordinator", "fact", "FactCard", f"facts:history?subject={subject}&key=lisinopril")
    binds = view_binds("coordinator", vid)
    assert {"plan:holiday", "calls:screened", f"facts:history?subject={subject}&key=lisinopril"} <= binds
    data = snapshot_data("coordinator", _coord(vid), vid)
    assert data["plan:holiday"] == {"items": []}
    assert data["calls:screened"] == []
    hist = data[f"facts:history?subject={subject}&key=lisinopril"]
    assert hist["entity"] == subject and hist["key"] == "lisinopril" and len(hist["versions"]) >= 2  # ledger fallback: rx history
    ctrl = snapshot_data("control", None, vid)
    assert "plan:holiday" in ctrl and "calls:screened" in ctrl


async def test_plan_from_proposal_record_and_claim_pushes(monkeypatch) -> None:
    from core import services
    from core.evolve import proposals as P

    await reset_demo()
    vid = villages.default_village_id()
    _add_element(vid, "coordinator", "plan1", "PlanBoard", "plan:holiday")
    monkeypatch.setattr(P, "_prune", lambda v: None)
    P.STORE.setdefault(vid, {})["prop_x_holiday_1"] = {"key": "chat:holiday", "proposal": {"id": "prop_x_holiday_1", "title": {"en": "Holiday"}, "status": "proposed"},
                                                      "plan": {"date": "Nov 26", "items": [{"text": "Pie", "owner": "someone"}, "Pick up at the train"]}}
    try:
        p = snapshot_data("coordinator", _coord(vid), vid)["plan:holiday"]
        assert p["date"] == "Nov 26" and [i["text"] for i in p["items"]] == ["Pie", "Pick up at the train"]
        assert all(i["status"] == "open" for i in p["items"])
        coord_ws, helper_ws = FakeWebSocket(), FakeWebSocket()
        helper = next(x["id"] for x in villages.people(vid) if x.get("view") == "helper")
        hub.clients = [Client(ws=coord_ws, village=vid, member_id=_coord(vid), role="coordinator"),
                       Client(ws=helper_ws, village=vid, member_id=helper, role="helper")]
        res = await services.handle_action(vid, "claim_plan_item", {"payload": {"plan_id": "holiday", "index": 1}, "member_id": _coord(vid), "req_id": "c1"})
        assert res["ok"]
        snap = coord_ws.frames[-1]
        assert snap["type"] == "snapshot" and snap["data"]["plan:holiday"]["items"][1]["status"] == "claimed"
        assert helper_ws.frames == []  # helper view doesn't bind the plan
        bad = await services.handle_action(vid, "claim_plan_item", {"payload": {"plan_id": "holiday", "index": 9}, "member_id": _coord(vid), "req_id": "c2"})
        assert bad["ok"] is False
    finally:
        P.STORE[vid].pop("prop_x_holiday_1", None)
        from core.bindings_v3 import PLANS

        PLANS.clear()
        hub.clients = []


async def test_screened_calls_from_receptionist_verifications_and_changed() -> None:
    await reset_demo()
    vid = villages.default_village_id()
    _add_element(vid, "coordinator", "calls", "ScreenedCalls", "calls:screened")
    claimed = villages.default_verifier(vid) or _coord(vid)
    now = clock.now().isoformat()
    row = {"id": "ver_screen_glue", "village": vid, "origin": "screen_caller", "state": "pending", "claimed_member_id": claimed,
           "claimed_identity": villages.first_name(vid, claimed), "created_at": now, "request": {}}
    db.verifications[row["id"]] = row
    calls = snapshot_data("coordinator", _coord(vid), vid)["calls:screened"]
    assert calls[0]["outcome"] == "held" and "verified_by" not in calls[0]
    row.update(state="denied", resolved_at=now)
    db.idem["conv_g:screen:await"] = {"response": {"say": "They say this isn't them.", "data": {"verification_id": row["id"], "status": "refused"}}, "at": now}
    ev = {"kind": "verification_denied", "village": vid, "payload": {"verification_id": row["id"]}}
    data = changed(ev, "coordinator", _coord(vid), vid)
    c = data["calls:screened"][0]
    assert c["outcome"] == "refused" and c["verified_by"] == villages.first_name(vid, claimed) and c["say"].startswith("They say")
    # a non-screen verification does not touch calls:screened
    db.verifications["ver_other"] = {**row, "id": "ver_other", "origin": "report_money_request"}
    assert "calls:screened" not in changed({**ev, "payload": {"verification_id": "ver_other"}}, "coordinator", _coord(vid), vid)


async def test_memory_history_upgrades_and_pushes(monkeypatch) -> None:
    from core import bindings_v3

    await reset_demo()
    vid = villages.default_village_id()
    subject = villages.care_recipient_id(vid)
    bind = f"facts:history?subject={subject}&key=lisinopril"
    _add_element(vid, "coordinator", "fact", "FactCard", bind)

    async def fake_history(deps, village, entity, key):
        return {"village": village, "entity": entity, "key": key, "versions": [{"value": "10 mg", "observed_at": "2026-10-03"}], "degraded": False}

    monkeypatch.setattr("core.memory.views.history_view", fake_history)
    ws = FakeWebSocket()
    client = Client(ws=ws, village=vid, member_id=_coord(vid), role="coordinator")
    hub.clients = [client]
    try:
        await hub._refresh_histories(client)
        assert ws.frames and ws.frames[-1]["data"][bind]["versions"][0]["value"] == "10 mg"
        assert ws.frames[-1]["data"][bind]["degraded"] is False
    finally:
        bindings_v3.HISTORY_CACHE.clear()
        hub.clients = []


async def test_plan_from_builder_plan_data() -> None:
    from core.builder import chat_intent

    await reset_demo()
    vid = villages.default_village_id()
    chat_intent.PLANS.setdefault(vid, {})["feast"] = {"title": {"en": "Feast plan"}, "date": "Nov 26",
                                                      "items": [{"text": {"en": "Turkey"}, "owner": _coord(vid), "kind": "task"}]}
    try:
        _add_element(vid, "coordinator", "plan2", "PlanBoard", "plan:feast")
        p = snapshot_data("coordinator", _coord(vid), vid)["plan:feast"]
        assert p["title"] == {"en": "Feast plan"} and p["date"] == "Nov 26" and p["items"][0]["owner"] == _coord(vid)
    finally:
        chat_intent.PLANS.get(vid, {}).pop("feast", None)


async def test_life_areas_carry_need_ids_from_spec() -> None:
    from core.bindings import life_areas

    await reset_demo()
    for vid in villages.village_ids():
        spec = villages.spec(vid)
        for row in life_areas(vid):
            expected = {n["id"] for n in spec["blueprint"]["needs"] if n.get("life_area") == row["id"]}
            assert expected <= set(row["need_ids"]) and len(row["need_ids"]) == len(set(row["need_ids"]))


async def test_coordinator_snapshot_has_rounds_and_fact_history() -> None:
    from core.ws_hub import snapshot

    await reset_demo()
    vid = villages.default_village_id()
    snap = snapshot(vid, "coordinator", villages.coordinator_id(vid))
    assert "rounds:latest" in snap["data"]
    hist = [k for k in snap["data"] if k.startswith("facts:history?")]
    binds = [k for k in __import__("core.bindings", fromlist=["view_binds"]).view_binds("coordinator", vid) if k.startswith("facts:history?")]
    assert set(binds) <= set(hist)
    rx = (db.prescriptions.get(vid) or [{}])[0].get("name")
    if rx:
        from core.bindings_v3 import fact_history

        assert fact_history(vid, villages.care_recipient_id(vid), f"{rx}_dose")["versions"]
