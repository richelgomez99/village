from core.settings import CONTRACT_VERSION
from fastapi.testclient import TestClient

from core.app import app


def test_health_reports_llm_off() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["contract_version"] == CONTRACT_VERSION
    assert body["deps"]["llm"] == "off"


def test_log_dose_writes_decision_and_event_frame() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?village=v_reyes&m=m_carmen") as ws:
            ws.send_json({"type": "hello", "contract_version": CONTRACT_VERSION, "village": "v_reyes", "member_id": "m_carmen"})
            assert ws.receive_json()["type"] == "snapshot"
            response = client.post(
                "/tools/log_dose",
                json={
                    "conversation_id": "conv_test_dose",
                    "caller_id": "+15555550101",
                    "call_secs": 31,
                    "utterance": "Ya me la tome.",
                    "slot": "evening",
                    "confidence": "confirmed_by_caller",
                },
            )
            assert response.status_code == 200
            assert response.json()["decision"] == "record"
            frame = ws.receive_json()
            assert frame["type"] == "event"
            assert frame["event"]["kind"] == "dose"

        decisions = client.get("/villages/v_reyes/decisions").json()["decisions"]
        assert decisions[-1]["gate"]["decision"] == "record"
        assert decisions[-1]["event_ids"]


def test_ws_contract_mismatch_closes_with_error() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?village=v_reyes&m=m_carmen") as ws:
            ws.send_json({"type": "hello", "contract_version": "0.9.0", "village": "v_reyes", "member_id": "m_carmen"})
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["code"] == "contract_mismatch"


def test_prescriptions_show_lisinopril_history() -> None:
    with TestClient(app) as client:
        prescriptions = client.get("/villages/v_reyes/prescriptions").json()["prescriptions"]
    assert [row["dose"] for row in prescriptions if row["name"] == "lisinopril"] == ["5 mg", "10 mg"]
    assert prescriptions[0]["valid_until"] == "2026-10-03"


def test_http_action_log_dose_uses_shared_handler() -> None:
    with TestClient(app) as client:
        response = client.post("/v/v_reyes/actions/log_dose", json={"req_id": "req_http_action", "slot": "evening"})
    assert response.status_code == 200
    assert response.json()["decision"]["decision"] == "record"


def test_ws_action_log_dose_returns_result() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?village=v_reyes&m=m_carmen") as ws:
            ws.send_json({"type": "hello", "contract_version": CONTRACT_VERSION, "village": "v_reyes", "member_id": "m_carmen"})
            assert ws.receive_json()["type"] == "snapshot"
            ws.send_json({"type": "action", "name": "log_dose", "req_id": "req_ws_action", "body": {"slot": "evening"}})
            frames = [ws.receive_json(), ws.receive_json()]
            assert {frame["type"] for frame in frames} == {"result", "event"}
            result = next(frame for frame in frames if frame["type"] == "result")
            assert result["req_id"] == "req_ws_action"
            assert result["decision"]["decision"] == "record"
