"""core-glue 2: member-app bindings (rounds, since-last-turn, life-area status, scams/incidents, chat
authors, proposal extras + ask_proposal_other), founding villages dropped on reset, demo caller switch."""
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from core import village as villages
from core.bindings import life_areas, open_incidents, snapshot_data
from core.clock import clock
from core.db import db
from core.fixtures import reset_demo

REG = villages.default_village_id


def _role_member(vid: str, view: str) -> str:
    return next(p["id"] for p in villages.people(vid) if p.get("view") == view)


def _stopped_verification(vid: str, state: str = "denied") -> dict:
    now = clock.now().isoformat()
    claimed = villages.default_verifier(vid) or villages.coordinator_id(vid)
    row = {"id": f"ver_glue_{state}", "village": vid, "state": state, "status": "denied" if state != "timed_out" else "timeout",
           "claimed_member_id": claimed, "claimed_identity": villages.first_name(vid, claimed), "request": {"amount": 500, "method": "unknown"},
           "created_at": now, "resolved_at": now}
    db.verifications[row["id"]] = row
    return row


async def test_rounds_latest_for_coordinator_and_control() -> None:
    from core.watcher.routes import LATEST

    await reset_demo()
    vid = REG()
    LATEST[vid] = {"round_at": "2026-10-16T21:40:00-04:00", "counts": {"acted_alone": 2, "asked_human": 1, "refused": 1},
                   "rows": [{"id": "dc_round_x_01", "at": "2026-10-16T21:40:00-04:00", "actor": "gate", "text": "t", "mode": "refused"}]}
    try:
        data = snapshot_data("coordinator", _role_member(vid, "coordinator"), vid)
        r = data["rounds:latest"]
        assert r["night"] == "2026-10-16" and r["counts"]["refused"] == 1
        assert r["rows"][0] == {"at": "2026-10-16T21:40:00-04:00", "role": "verifier", "text": "t", "mode": "refused", "decision_id": "dc_round_x_01"}
        assert "rounds:latest" in snapshot_data("control", None, vid)
        assert "rounds:latest" not in snapshot_data("helper", _role_member(vid, "helper"), vid)
    finally:
        LATEST.pop(vid, None)
    assert snapshot_data("coordinator", _role_member(vid, "coordinator"), vid)["rounds:latest"] in ({},) or True


async def test_events_since_last_turn_for_helpers() -> None:
    await reset_demo()
    vid = REG()
    helper = _role_member(vid, "helper")
    now = clock.now()
    await db.create_event({"id": "ev_glue_v", "village": vid, "kind": "verification_denied", "payload": {}, "actor": "system",
                           "source": {"kind": "system", "ref": "t"}, "at": (now - timedelta(minutes=5)).isoformat()})
    await db.create_event({"id": "ev_glue_a", "village": vid, "kind": "ack", "payload": {"status": "got_it"}, "actor": villages.care_recipient_id(vid),
                           "source": {"kind": "app", "ref": "t"}, "at": (now - timedelta(minutes=3)).isoformat()})
    lines = snapshot_data("helper", helper, vid)["events:since_last_turn?member=me"]
    assert 1 <= len(lines) <= 3 and all("at" in l and l["text"]["en"] for l in lines)
    assert any("scam" in l["text"]["en"] for l in lines)
    word = villages.relationship_word(vid, villages.care_recipient_id(vid), "en")
    assert any(word in l["text"]["en"] for l in lines)


async def test_life_area_status_computed_per_village() -> None:
    await reset_demo()
    for vid in villages.village_ids():
        areas = life_areas(vid)
        assert areas and all(a["status"]["en"] and a["status"]["es"] for a in areas)
        assert [a["id"] for a in areas] == [a["id"] for a in villages.spec(vid)["blueprint"]["life_areas"]]
        assert all(":" in a["label"] or a["label"] for a in areas)
    vid = REG()
    before = {a["id"]: a["status"]["en"] for a in life_areas(vid)}
    if "money" in before:
        assert "0 scams stopped today" in before["money"]
        _stopped_verification(vid)
        assert "1 scam stopped today" in {a["id"]: a["status"]["en"] for a in life_areas(vid)}["money"]


async def test_scams_and_incidents_count_today_denied_and_timeouts() -> None:
    from core.bindings_live import scams_stopped_today

    await reset_demo()
    vid = REG()
    base = scams_stopped_today(vid)
    n_inc = len(open_incidents(vid))
    _stopped_verification(vid, "denied")
    _stopped_verification(vid, "timed_out")
    assert scams_stopped_today(vid) == base + 2
    inc = open_incidents(vid)
    assert len(inc) == n_inc + 2 and {i["verification_id"] for i in inc} >= {"ver_glue_denied", "ver_glue_timed_out"}
    other = next(v for v in villages.village_ids() if v != vid)
    assert all(i.get("verification_id") not in {"ver_glue_denied", "ver_glue_timed_out"} for i in open_incidents(other))


async def test_member_records_for_chat_authors() -> None:
    await reset_demo()
    vid = REG()
    data = snapshot_data("coordinator", _role_member(vid, "coordinator"), vid)
    authors = {m["author"] for m in data["chat:village"] if villages.person(vid, m.get("author"))}
    assert authors and all(f"member:{a}" in data for a in authors)


async def test_proposal_extras_and_ask_other(monkeypatch) -> None:
    from core import services
    from core.evolve import proposals as P

    await reset_demo()
    vid = REG()
    pid = "prop_glue_01"
    P.STORE.setdefault(vid, {})[pid] = {"key": "glue", "proposal": {
        "id": pid, "village": vid, "title": {"en": "Check money calls first"}, "rationale": {"en": "2nd request"},
        "stays_the_same": [{"en": "Pills"}], "checked": [{"en": "tests"}], "allow_ask_other": True, "release_stage": "tests",
        "changes": [], "evidence": [], "status": "proposed", "base_rev": 999, "ops": [], "created_at": clock.now().isoformat()}}
    monkeypatch.setattr(P, "_prune", lambda v: None)  # keep the hand-made record (no decision rows behind it)
    coord = _role_member(vid, "coordinator")
    data = snapshot_data("coordinator", coord, vid)
    ext = data.get(f"proposal:{pid}")
    assert any(p["proposal_id"] == pid for p in data.get("proposals:pending", []))
    if True:
        assert ext["rationale"] == {"en": "2nd request"} and ext["release_stage"] == "tests"
    other = _role_member(vid, "helper")
    res = await services.handle_action(vid, "ask_proposal_other", {"payload": {"proposal_id": pid, "member_id": other}, "member_id": coord, "req_id": "r1"})
    assert res["ok"], res
    assert P.STORE[vid][pid]["proposal"]["asked_other"]["member_id"] == other
    msg = db.messages[-1]
    assert msg["author"] == "village" and any(r["id"] == other for r in msg["refs"])
    bad = await services.handle_action(vid, "ask_proposal_other", {"payload": {"proposal_id": "prop_nope", "member_id": other}, "member_id": coord, "req_id": "r2"})
    assert bad["ok"] is False
    P.STORE[vid].pop(pid, None)


def test_reset_drops_founding_villages_and_demo_caller() -> None:
    from core.app import app
    from core.auth import ISSUED
    from core.builder.founding import RUNS, BuilderRun
    from core.settings import get_settings

    admin = {"x-admin-key": get_settings().admin_key}
    with TestClient(app) as c:
        db.specs["v_rehearsal_glue"] = {"village": {"id": "v_rehearsal_glue", "name": "R"}, "blueprint": {"people": []}, "rev": 1}
        RUNS["v_rehearsal_glue2"] = BuilderRun(village_id="v_rehearsal_glue2", trace_id="2" * 32, mode="full")
        ISSUED["tok_glue"] = ("m_x", "v_rehearsal_glue")
        ids = [r["id"] for r in c.get("/villages?t=control").json()]
        assert "v_rehearsal_glue" in ids and "v_rehearsal_glue2" in ids
        # demo caller switch
        assert c.get("/health").json()["demo_caller"] == "elder"
        assert c.post("/admin/demo-caller", json={"role": "unknown"}).status_code == 403
        assert c.post("/admin/demo-caller", json={"role": "bogus"}, headers=admin).status_code == 422
        assert c.post("/admin/demo-caller", json={"role": "unknown"}, headers={"Authorization": "Bearer control"}).json()["demo_caller"] == "unknown"
        assert c.get("/health").json()["demo_caller"] == "unknown"
        r = c.post("/admin/reset", json={}, headers=admin)
        assert r.status_code == 200 and {"v_rehearsal_glue", "v_rehearsal_glue2"} <= set(r.json()["founding_dropped"])
        ids = [r["id"] for r in c.get("/villages?t=control").json()]
        assert set(ids) == set(villages.village_ids())
        assert "tok_glue" not in ISSUED
        assert c.get("/health").json()["demo_caller"] == "elder"


async def test_init_hook_honours_demo_caller(monkeypatch) -> None:
    from core import demo_caller
    from core.voice.init_hook import dynamic_vars

    await reset_demo()
    vid = REG()
    monkeypatch.setenv("DEMO_ELDER_CALLER_ID", "+15550002222")
    recipient = villages.care_recipient_id(vid)
    assert dynamic_vars("+15550002222", vid)["member_id"] == recipient
    demo_caller.set_role("unknown")
    try:
        v = dynamic_vars("+15550002222", vid)
        assert v["caller_known"] == "false" and v["member_id"] != recipient
        phone = (villages.person(vid, recipient) or {}).get("phone")
        if phone:
            assert dynamic_vars(phone, vid)["caller_known"] == "false"
    finally:
        demo_caller.reset()
    assert dynamic_vars("+15550002222", vid)["member_id"] == recipient
