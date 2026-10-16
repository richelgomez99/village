from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.voice.init_hook import INIT_VAR_KEYS, VOICE_CALLS, app


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VILLAGE_SECRET", "test-secret")
    monkeypatch.setenv("DEMO_CARMEN_CALLER_ID", "+19999999999")
    VOICE_CALLS.clear()


def post(caller_id: str) -> dict:
    response = TestClient(app).post(
        "/hooks/elevenlabs/init",
        headers={"X-Village-Secret": "test-secret"},
        json={
            "caller_id": caller_id,
            "agent_id": "agent_mom",
            "called_number": "+18482579221",
            "call_sid": "CA_init",
            "conversation_id": "conv_init",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_known_caller_returns_exact_seven_vars() -> None:
    body = post("+15555550103")
    variables = body["dynamic_variables"]

    assert tuple(variables.keys()) == INIT_VAR_KEYS
    assert variables["member_id"] == "m_marco"
    assert variables["member_short_name"] == "Marco"
    assert VOICE_CALLS[-1]["member_id"] == "m_marco"


def test_demo_carmen_override_wins() -> None:
    variables = post("+19999999999")["dynamic_variables"]

    assert variables["member_id"] == "m_carmen"
    assert variables["member_short_name"] == "Carmen"


def test_unknown_caller_gets_guest_vars() -> None:
    variables = post("+10000000000")["dynamic_variables"]

    assert tuple(variables.keys()) == INIT_VAR_KEYS
    assert variables["member_id"] == "m_unknown"
    assert "Guest caller" in variables["today_summary"]


def test_web_empty_caller_resolves_care_recipient() -> None:
    variables = post("")["dynamic_variables"]

    assert variables["member_id"] == "m_carmen"
    assert VOICE_CALLS[-1]["direction"] == "web"


def test_secret_required() -> None:
    response = TestClient(app).post("/hooks/elevenlabs/init", json={"caller_id": "+15555550101"})
    assert response.status_code == 401

