"""core-glue lane: member records + Village line in snapshots, per-village control frames, founding
frames, village list, builder redeem handoff, builder tracer, fridge card."""
from __future__ import annotations

import pytest

from core import village as villages
from core.db import db
from core.fixtures import reset_demo
from core.ws_hub import Client, hub, snapshot


class FakeWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send_json(self, frame: dict) -> None:
        self.frames.append(frame)


@pytest.fixture(autouse=True)
def _village_line(monkeypatch):
    monkeypatch.setenv("VILLAGE_PHONE_NUMBER", "+15550001111")


def _people(vid: str) -> dict[str, dict]:
    return {p["id"]: p for p in villages.people(vid)}


async def test_member_records_for_call_targets_and_village_line() -> None:
    await reset_demo()
    for vid in villages.village_ids():
        recipient, coord = villages.care_recipient_id(vid), villages.coordinator_id(vid)
        people = _people(vid)
        for role in ("helper", "coordinator"):
            if (vid, role) not in db.views or not recipient:
                continue
            snap = snapshot(vid, role, next(i for i, p in people.items() if p.get("view") == role))
            rec = snap["data"][f"member:{recipient}"]
            assert rec["member_id"] == recipient and rec["role"] == people[recipient]["role"]
            if villages.e164(people[recipient].get("phone")):
                assert rec["phone"] == people[recipient]["phone"]
        if (vid, "elder") in db.views and coord:
            snap = snapshot(vid, "elder", recipient)
            assert f"member:{coord}" in snap["data"]
            assert snap["identity"]["village_number"] == "+15550001111"


async def test_redeemed_phone_overrides_member_record() -> None:
    await reset_demo()
    vid = villages.default_village_id()
    recipient = villages.care_recipient_id(vid)
    helper_role = next(p["view"] for p in villages.people(vid) if p.get("view") not in (None, "elder"))
    db.members[recipient] = {**db.members[recipient], "phone": "+15557654321"}
    snap = snapshot(vid, helper_role, None)
    assert snap["data"][f"member:{recipient}"]["phone"] == "+15557654321"


async def test_village_number_falls_back_to_spec(monkeypatch) -> None:
    monkeypatch.delenv("VILLAGE_PHONE_NUMBER", raising=False)
    await reset_demo()
    vid = villages.default_village_id()
    # fixture printables carry a placeholder, not E.164 -> no number rather than a fake one
    assert villages.village_number(vid) in (None,) or villages.e164(villages.village_number(vid))


# ---- T2: per-village control frames ------------------------------------------------------------

def _two_rooms() -> tuple[FakeWebSocket, FakeWebSocket, str, str]:
    a_id, b_id = villages.village_ids()[:2]
    a, b = FakeWebSocket(), FakeWebSocket()
    hub.clients = [Client(ws=a, village=a_id, member_id=None, role="control"),
                   Client(ws=b, village=b_id, member_id=None, role="control")]
    return a, b, a_id, b_id


async def test_control_frames_stay_in_their_village() -> None:
    from core import services

    await reset_demo()
    a, b, a_id, b_id = _two_rooms()
    await services.reasoning(a_id, "only for A")
    await services.ledger(a_id, "row1", "done", "work")
    await services.caption(a_id, "hola", "hello")
    await services.control(a_id, "gate", {"decision": {"decision": "allow"}, "input_kind": "tick"})
    await services.control(a_id, "counter", {"name": "scams_stopped", "value": 1, "label": "x"})
    await services.control(a_id, "blueprint", {"stage": "kind", "items": [{"kind": "care"}]})
    kinds = [f["kind"] for f in a.frames]
    assert {"reasoning", "ledger", "caption", "gate", "counter", "blueprint"} <= set(kinds)
    assert b.frames == []
    for f in a.frames:
        if f["kind"] in {"reasoning", "ledger", "caption", "blueprint"}:
            assert f["payload"]["village"] == a_id
    await services.reasoning(b_id, "only for B")
    assert [f["payload"]["text"] for f in b.frames] == ["only for B"]
    hub.clients = []


async def test_member_sockets_never_get_control_frames() -> None:
    from core import services

    await reset_demo()
    vid = villages.default_village_id()
    phone = FakeWebSocket()
    hub.clients = [Client(ws=phone, village=vid, member_id=villages.coordinator_id(vid), role="coordinator")]
    await services.reasoning(vid, "room only")
    assert phone.frames == []
    hub.clients = []


# ---- T3: founding frames derived from the builder's state --------------------------------------

async def test_intake_covered_counter_derives_coverage_and_gap_questions() -> None:
    from core.builder.conversation import IntakeState
    from core.builder.founding import RUNS, SESSIONS, BuilderRun, FoundingSession

    await reset_demo()
    a, b, a_id, b_id = _two_rooms()
    run = BuilderRun(village_id=a_id, trace_id="0" * 32, mode="full")
    intake = IntakeState(opener="my mom lives alone", kind="care", speaker="me")
    intake.family_word = "secretword"
    run.family_word = "secretword"
    run.turns.append({"next": "Who helps on weekdays?"})
    RUNS[a_id], SESSIONS[a_id] = run, FoundingSession(run=run, intake=intake)
    try:
        await hub.control(a_id, "counter", {"name": "intake_covered", "value": 0, "label": "topics covered", "of": 10})
    finally:
        RUNS.pop(a_id, None), SESSIONS.pop(a_id, None)
    cov = [f for f in a.frames if f["kind"] == "counter" and f["payload"]["name"] == "intake_coverage"]
    assert cov and cov[0]["payload"]["of"] == len(intake.topics) and cov[0]["payload"]["value"] == len(intake.covered())
    bp = [f for f in a.frames if f["kind"] == "blueprint"][0]["payload"]
    assert bp["stage"] == "questions" and bp["items"][0] == {"question": "Who helps on weekdays?"}
    assert len([i for i in bp["items"] if i.get("gap")]) == len(intake.gaps())
    assert "secretword" not in str(a.frames)
    assert b.frames == []
    hub.clients = []


# ---- T4 / T5 / T7: HTTP ------------------------------------------------------------------------

def _new_village(client, vid: str = "v_glue01") -> dict:
    """A builder-shaped village (template spec under a fresh id) as the intake would store it."""
    from core.builder import templates

    spec = templates.spec("care", village_id=vid, status="draft")
    spec["village"]["name"] = "Glue Test Village"
    from core.db import db as _db

    _db.specs[vid] = spec
    return spec


def test_get_villages_lists_registry_and_created() -> None:
    from fastapi.testclient import TestClient

    from core.app import app

    with TestClient(app) as c:
        assert c.get("/villages").status_code == 401
        rows = c.get("/villages", headers={"Authorization": "Bearer control"}).json()
        ids = [r["id"] for r in rows]
        assert set(villages.village_ids()) <= set(ids)
        assert all(set(r) == {"id", "name", "status", "kind", "people_count", "rev"} for r in rows)
        _new_village(c)
        rows = c.get("/villages?t=control").json()
        mine = next(r for r in rows if r["id"] == "v_glue01")
        assert mine["status"] == "draft" and mine["people_count"] >= 2 and mine["name"] == "Glue Test Village"


def test_redeem_falls_back_to_builder_invite_and_phone_becomes_call_target() -> None:
    import hashlib

    from fastapi.testclient import TestClient

    from core.app import app
    from core.builder import routes as broutes

    broutes.set_services(broutes.CoreServices())
    with TestClient(app) as c:
        spec = _new_village(c, "v_glue02")
        helper = next(p for p in spec["blueprint"]["people"] if p.get("view") == "helper")
        recipient = spec["village"]["care_recipient_id"]
        token = "builderinvitetoken123"
        broutes.INVITES[hashlib.sha256(token.encode()).hexdigest()] = {"invite_id": "inv_x", "village": "v_glue02", "member_id": helper["id"], "redeemed_at": None}
        r = c.post("/auth/redeem", json={"invite": token, "phone": "+15551234567", "consent": {"ai_calls": True}})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["village"] == "v_glue02" and out["member_id"] == helper["id"]
        assert villages.member_phone("v_glue02", helper["id"]) == "+15551234567"
        # the member token opens that village's helper view, never the registry village of the same id
        with c.websocket_connect(f"/ws?m={out['member_token']}") as ws:
            ws.send_json({"type": "hello", "contract_version": __import__("core.settings", fromlist=["x"]).CONTRACT_VERSION, "member_token": out["member_token"]})
            snap = ws.receive_json()
        assert snap["village"] == "v_glue02" and snap["role"] == "helper" and snap["spec"].get("elements")
        assert f"member:{recipient}" in snap["data"]
        assert c.post("/auth/redeem", json={"invite": token}).status_code == 409
        assert c.post("/auth/redeem", json={"invite": "nope"}).status_code == 404


def test_fridge_card_html() -> None:
    from fastapi.testclient import TestClient

    from core.app import app
    from core.builder.founding import RUNS, BuilderRun

    with TestClient(app) as c:
        spec = _new_village(c, "v_glue03")
        assert c.get("/villages/v_glue03/print/fridge").status_code == 401
        html = c.get("/villages/v_glue03/print/fridge?t=control").text
        assert "+15550001111"[2:5] in html and "911" in html and "__________" in html
        assert "[PALABRA]" not in html  # never from the spec
        RUNS["v_glue03"] = BuilderRun(village_id="v_glue03", trace_id="1" * 32, mode="full")
        RUNS["v_glue03"].family_word = "girasol"
        try:
            coord = spec["village"]["coordinator_id"]
            html = c.get(f"/villages/v_glue03/print/fridge?t={coord}").text
        finally:
            RUNS.pop("v_glue03", None)
        assert "girasol" in html
        other = next(p for p in spec["blueprint"]["people"] if p["id"] not in (coord, spec["village"]["care_recipient_id"]))
        assert str(other["name"]).split()[0] in html
