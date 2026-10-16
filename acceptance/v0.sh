#!/usr/bin/env bash
set -euo pipefail

uv run python - <<'PY'
from fastapi.testclient import TestClient

from core.app import app

with TestClient(app) as client:
    health = client.get("/health")
    assert health.status_code == 200, health.text
    body = health.json()
    assert body["ok"] is True
    assert body["contract_version"] == "1.1.0"
    assert body["deps"]["llm"] == "off"

    with client.websocket_connect("/ws?village=v_reyes&m=m_carmen") as carmen:
        carmen.send_json({"type": "hello", "contract_version": "1.1.0", "village": "v_reyes", "member_id": "m_carmen"})
        snap = carmen.receive_json()
        assert snap["type"] == "snapshot"
        assert snap["role"] == "elder"

        tool = client.post(
            "/tools/log_dose",
            json={
                "conversation_id": "conv_accept_v0_dose",
                "caller_id": "+15555550101",
                "call_secs": 31,
                "utterance": "Ya me la tome.",
                "slot": "evening",
                "confidence": "confirmed_by_caller",
                "tool_call_id": "tool_accept_v0",
            },
        )
        assert tool.status_code == 200, tool.text
        assert tool.json()["decision"] == "record"
        frame = carmen.receive_json()
        assert frame["type"] == "event"
        assert frame["event"]["kind"] == "dose"
        assert frame["event"]["decision_id"].startswith("dc_")

    prescriptions = client.get("/villages/v_reyes/prescriptions")
    assert prescriptions.status_code == 200
    doses = [row["dose"] for row in prescriptions.json()["prescriptions"] if row["name"] == "lisinopril"]
    assert doses == ["5 mg", "10 mg"]

    warp = client.post("/clock/warp", json={"minutes": 38})
    assert warp.status_code == 200
    assert warp.json()["offset_minutes"] == 38

    decisions = client.get("/villages/v_reyes/decisions")
    assert decisions.status_code == 200
    assert decisions.json()["decisions"][-1]["gate"]["rules_fired"][0] == "R-WINDOW"
PY

uv run pytest core -q
