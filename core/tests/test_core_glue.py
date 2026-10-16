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
