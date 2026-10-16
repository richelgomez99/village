from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.db import db
from core.voice.post_call import POST_CALLS, app


def sign(body: bytes, secret: str = "hook-secret", timestamp: str = "123") -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v0={digest}"


@pytest.fixture(autouse=True)
async def reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", "hook-secret")
    monkeypatch.setenv("VOICE_MEMORY_OUTBOX", str(tmp_path))
    monkeypatch.setenv("VILLAGE_FAMILY_WORD", "azul")
    await db.reset()
    await db.upsert_verification({
        "id": "ver_1016_01",
        "village": "v_reyes",
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "state": "pending",
        "status": "pending",
        "channels": [{"via": "outbound_call", "member_id": "m_marco", "status": "ringing"}],
        "answers": [],
        "version": 0,
    })
    POST_CALLS.clear()


def post(payload: dict) -> Any:
    raw = json.dumps(payload).encode()
    return TestClient(app).post(
        "/hooks/elevenlabs/post-call",
        content=raw,
        headers={"ElevenLabs-Signature": sign(raw), "content-type": "application/json"},
    )


def test_post_call_writes_redacted_memory_outbox(tmp_path: Path) -> None:
    response = post({
        "type": "post_call",
        "conversation_id": "conv_post",
        "transcript": [{"text": "La palabra azul y tarjeta 4111 1111 1111 1111"}],
    })

    assert response.status_code == 200
    saved = json.loads((tmp_path / "conv_post.json").read_text())
    assert "azul" not in json.dumps(saved)
    assert "4111" not in json.dumps(saved)
    assert "[PALABRA]" in json.dumps(saved)


def test_tampered_signature_rejected() -> None:
    response = TestClient(app).post(
        "/hooks/elevenlabs/post-call",
        content=b"{}",
        headers={"ElevenLabs-Signature": "t=1,v0=bad", "content-type": "application/json"},
    )
    assert response.status_code == 401


def test_call_initiation_failure_records_failed_event() -> None:
    response = post({
        "type": "call_initiation_failure",
        "conversation_id": "conv_fail",
        "verification_id": "ver_1016_01",
        "reason": "geo_permissions",
    })

    assert response.status_code == 200
    assert db.events[-1]["kind"] == "call_failed"
    assert db.verifications["ver_1016_01"]["channels"][0]["status"] == "failed"


def test_data_collection_answer_applies_to_verification() -> None:
    response = post({
        "type": "data_collection",
        "conversation_id": "conv_answer",
        "call_sid": "CA_answer",
        "dynamic_variables": {"verification_id": "ver_1016_01", "member_id": "m_marco"},
        "data_collection_results": {"verification_answer": "no"},
        "listener_quote": "That was not me",
    })

    assert response.status_code == 200
    assert db.verifications["ver_1016_01"]["state"] == "denied"
    assert db.verifications["ver_1016_01"]["answers"][0]["call_sid"] == "CA_answer"
