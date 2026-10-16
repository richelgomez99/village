from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.db import db
from core.voice.outbound import FakeDialer, OutboundService, app, service


@pytest.fixture(autouse=True)
async def reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_TOKEN", "control")
    await db.reset()
    await db.upsert_verification({
        "id": "ver_1016_01",
        "village": "v_reyes",
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "state": "pending",
        "status": "pending",
        "channels": [],
        "answers": [],
        "version": 0,
    })
    service.dialer = FakeDialer()


def post(member_id: str = "m_marco", verification_id: str = "ver_1016_01"):
    return TestClient(app).post(
        "/calls/outbound",
        headers={"Authorization": "Bearer control"},
        json={"member_id": member_id, "reason": "verification", "template": "T3", "verification_id": verification_id},
    )


def test_places_outbound_with_ringing_timeout() -> None:
    response = post()

    assert response.status_code == 200
    body = response.json()
    assert body["placed"] is True
    assert body["status"] == "ringing"
    assert body["payload"]["telephony_call_config"]["ringing_timeout_secs"] == 30
    assert db.verifications["ver_1016_01"]["call_placed_at"]


def test_consent_false_skips_call() -> None:
    response = post(member_id="m_lucia")

    assert response.status_code == 200
    assert response.json() == {"placed": False, "status": "skipped_no_consent"}
    assert "call_placed_at" not in db.verifications["ver_1016_01"]


def test_second_call_does_not_redial() -> None:
    first = post()
    second = post()

    assert first.json()["placed"] is True
    assert second.json() == {"placed": False, "status": "already_placed"}


def test_terminal_row_does_not_dial() -> None:
    db.verifications["ver_1016_01"]["state"] = "denied"
    db.verifications["ver_1016_01"]["status"] = "denied"

    response = post()

    assert response.status_code == 200
    assert response.json() == {"placed": False, "status": "terminal"}


def test_control_token_required() -> None:
    response = TestClient(app).post(
        "/calls/outbound",
        json={"member_id": "m_marco", "reason": "verification", "template": "T3", "verification_id": "ver_1016_01"},
    )
    assert response.status_code == 401

