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
