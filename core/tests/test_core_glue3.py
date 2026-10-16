"""core-glue 3 (contract 1.3.4): plan:<id>, calls:screened, facts:history binds in snapshots and changed(),
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


async def test_block_village_binds_and_reyes_fixes() -> None:
    from core.bindings import life_areas, with_source_labels

    await reset_demo()
    block = next(v for v in villages.village_ids() if villages.village_data(v).get("resources"))
    coord = villages.coordinator_id(block)
    d = snapshot_data("coordinator", coord, block)
    for key in ("checkins:village", "needs:open", "resources:available", "claims:topic=all"):
        assert d[key] and all(r["text"]["en"] for r in d[key]), key
    assert any(r["status"] == "ok" for r in d["checkins:village"]) and any(r["status"] == "urgent" for r in d["checkins:village"])
    assert d["needs:open"][0]["text"]["en"].startswith("Urgent")
    assert any("checked" in a["status"]["en"] for a in life_areas(block))
    vid = villages.default_village_id()
    a = snapshot_data("coordinator", villages.coordinator_id(vid), vid)
    assert all(i.get("status") != "acked" for i in a["incidents:open"])
    assert all(r["at"] for r in a["rounds:latest"].get("rows", []))
    ev = {"id": "ev_glue_call", "village": vid, "kind": "symptom", "payload": {}, "actor": villages.care_recipient_id(vid),
          "source": {"kind": "call", "ref": "conv_x"}, "at": clock.now().isoformat()}
    db.events.append(ev)
    msg = with_source_labels({"village": vid, "author": "village", "refs": [{"kind": "event", "id": "ev_glue_call", "label": "from her phone"}]})
    assert msg["refs"][0]["label"].endswith("check-in call") and "phone" not in msg["refs"][0]["label"]


async def test_shift_swap_flips_rota_and_pushes_everywhere() -> None:
    from datetime import date as _date, timedelta as _td

    from core import services
    from core.bindings import rota_me, rota_week

    await reset_demo()
    vid = villages.default_village_id()
    week = rota_week(vid)
    today = clock.now().date().isoformat()
    later = [d for d in week if d["date"] > today and d.get("on_duty")]
    assert later, "base rota has a later day"
    target = later[0]
    was = target["on_duty"]
    cover = next(p["id"] for p in villages.people(vid) if p.get("view") == "helper" and p["id"] != was)
    tonight_before = rota_me(cover, vid)["on_duty"]["member_id"]
    sockets = {}
    clients = []
    for p in villages.people(vid):
        ws = FakeWebSocket()
        sockets[p["id"]] = ws
        clients.append(Client(ws=ws, village=vid, member_id=p["id"], role=p.get("view") or "elder"))
    room = FakeWebSocket()
    clients.append(Client(ws=room, village=vid, member_id=None, role="control"))
    hub.clients = clients
    try:
        ev = await services.record_event(vid, {"kind": "shift", "payload": {"date": target["date"], "on_duty": cover, "backup": was, "change": "swapped"}},
                                         actor=cover, source={"kind": "app", "ref": cover})
        await hub.broadcast_event(ev)
        day = next(d for d in rota_week(vid) if d["date"] == target["date"])
        assert day["on_duty"] == cover and day["backup"] == was
        mine = rota_me(cover, vid, date=target["date"])
        assert mine["is_my_turn"] and mine["on_duty"]["member_id"] == cover
        assert rota_me(cover, vid)["on_duty"]["member_id"] == tonight_before  # tonight unchanged by a later swap
        for mid, ws in sockets.items():
            frame = next(f for f in ws.frames if f["type"] == "event" and f["event"]["kind"] == "shift")
            assert any(d["date"] == target["date"] and d["on_duty"] == cover for d in frame["data"]["rota:week"]), mid
        reasoning = [f for f in room.frames if f.get("kind") == "reasoning"]
        dayname = _date.fromisoformat(target["date"]).strftime("%A")
        assert reasoning and reasoning[-1]["payload"]["text"] == f"{dayname}: {villages.first_name(vid, cover)} covers for {villages.first_name(vid, was)}"
        if villages.person(vid, was).get("view") == "helper":
            lines = [l["text"]["en"] for l in next(f for f in sockets[was].frames if f["type"] == "event")["data"]["events:since_last_turn?member=me"]]
            assert f"{villages.first_name(vid, cover)} covers your {dayname}" in lines
    finally:
        hub.clients = []
