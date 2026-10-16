from datetime import timedelta

from fastapi.testclient import TestClient

from core.app import app
from core.clock import clock
from core.db import db
from core.fixtures import reset_demo
from core import services
from core.scheduler import tick


async def test_start_verification_persists_versioned_row() -> None:
    await reset_demo("v_reyes")
    now = clock.now().isoformat()
    result = await services.start_verification(
        "v_reyes",
        {
            "village": "v_reyes",
            "kind": "money_request",
            "payload": {
                "subject": "m_carmen",
                "claimed_member_id": "m_marco",
                "claimed_identity": "Marco",
                "amount": 2000,
                "currency": "USD",
                "method": "unknown",
                "urgency": "now",
                "utterance": "needs money",
                "deadline": "2026-10-16T14:02:54-04:00",
            },
            "actor": "m_carmen",
            "source": {"kind": "call", "ref": "conv_verification", "secs": 9},
            "at": now,
        },
        idempotency_key="conv_verification:tool_1",
    )
    assert result["status"] == "pending"
    row = db.verifications[result["verification_id"]]
    assert row["version"] == 0
    assert row["state"] == "pending"


async def test_answer_verification_uses_cas() -> None:
    await db.upsert_verification({
        "id": "ver_cas",
        "village": "v_reyes",
        "claimed_member_id": "m_marco",
        "state": "pending",
        "status": "pending",
        "answers": [],
        "created_at": clock.now().isoformat(),
        "deadline": "2099-01-01T00:00:00-05:00",
        "version": 0,
        "transitions": [],
    })
    first = await services.answer_verification("ver_cas", "no", via="app_prompt", member_id="m_marco")
    second = await services.answer_verification("ver_cas", "yes", via="app_prompt", member_id="m_marco")
    assert first["outcome"] == "applied"
    assert second["outcome"] == "conflict"
    assert db.verifications["ver_cas"]["version"] == 2
    assert any(ev["kind"] == "verification_denied" for ev in db.events)


async def test_duplicate_money_tool_returns_cached_body() -> None:
    await reset_demo("v_reyes")
    body = {
        "conversation_id": "conv_dup_money",
        "tool_call_id": "tool_money_1",
        "caller_id": "+15555550101",
        "call_secs": 9,
        "utterance": "Marco needs money",
        "claimed_member": "marco",
        "claimed_identity": "Marco",
        "amount": 2000,
        "currency": "USD",
        "method": "unknown",
        "urgency": "now",
    }
    first = await services.handle_tool("report_money_request", body)
    second = await services.handle_tool("report_money_request", body)
    assert second == first
    assert len(db.verifications) == 1


async def test_scheduler_times_out_past_deadline_verification() -> None:
    await reset_demo("v_reyes")
    await db.upsert_verification({
        "id": "ver_due",
        "village": "v_reyes",
        "claimed_member_id": "m_marco",
        "state": "pending",
        "status": "pending",
        "answers": [],
        "deadline": "2000-01-01T00:00:00-05:00",
        "version": 0,
    })
    result = await tick()
    assert result["verification_timeouts"] == 1
    assert db.verifications["ver_due"]["state"] == "timed_out"
    assert any(ev["kind"] == "verification_timeout" and ev["payload"]["verification_id"] == "ver_due" for ev in db.events)


async def test_await_verification_defaults_after_30_seconds_and_opens_incident() -> None:
    await reset_demo("v_reyes")
    created_at = clock.now() - timedelta(seconds=31)
    await db.upsert_verification({
        "id": "ver_await",
        "village": "v_reyes",
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "claimed_identity": "Marco",
        "state": "pending",
        "status": "pending",
        "channels": [{"via": "app_prompt", "member_id": "m_marco", "status": "sent", "at": created_at.isoformat()}],
        "answers": [],
        "created_at": created_at.isoformat(),
        "deadline": (created_at + timedelta(seconds=45)).isoformat(),
        "version": 0,
        "transitions": [],
    })

    result = await services.await_verification("ver_await", max_wait_s=0)

    assert result["say_key"] == "money_timeout"
    assert result["status"] == "timeout"
    assert result["state"] == "default_spoken"
    assert result["incident_id"] == "inc_ver_await"
    assert db.verifications["ver_await"]["state"] == "default_spoken"
    assert db.verifications["ver_await"]["spoken_say_key"] == "money_timeout"
    assert any(ev["kind"] == "incident" and ev["payload"]["incident_id"] == "inc_ver_await" for ev in db.events)


async def test_late_no_after_default_spoken_denies_without_new_spoken_say() -> None:
    await reset_demo("v_reyes")
    created_at = clock.now() - timedelta(seconds=38)
    await db.upsert_verification({
        "id": "ver_late",
        "village": "v_reyes",
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "claimed_identity": "Marco",
        "state": "default_spoken",
        "status": "pending",
        "channels": [],
        "answers": [],
        "created_at": created_at.isoformat(),
        "deadline": (created_at + timedelta(seconds=45)).isoformat(),
        "await_returned_at": (created_at + timedelta(seconds=30)).isoformat(),
        "spoken_say_key": "money_timeout",
        "incident_id": "inc_ver_late",
        "version": 0,
        "transitions": [],
    })

    result = await services.answer_verification("ver_late", "no", via="app_prompt", member_id="m_marco")

    assert result["state"] == "late_denied"
    assert result["status"] == "denied"
    assert db.verifications["ver_late"]["spoken_say_key"] == "money_timeout"
    assert db.verifications["ver_late"]["incident_id"] == "inc_ver_late"
    assert any(ev["kind"] == "verification_denied" and ev["payload"]["state"] == "late_denied" for ev in db.events)


async def test_actions_answer_start_and_ack_incident() -> None:
    await reset_demo("v_reyes")
    started = await services.handle_action(
        "v_reyes",
        "start_verification",
        {"req_id": "req_start_ver", "member_id": "m_ana", "payload": {"claimed_member_id": "m_marco", "amount": 2000}},
    )
    verification_id = started["decision"]["verification"]["id"]
    assert started["ok"] is True
    assert verification_id in db.verifications

    answered = await services.handle_action(
        "v_reyes",
        "answer_verification",
        {"req_id": "req_answer_ver", "member_id": "m_marco", "payload": {"verification_id": verification_id, "answer": "no"}},
    )
    assert answered["type"] == "result"
    assert answered["ok"] is True
    assert db.verifications[verification_id]["state"] == "denied"

    acked = await services.handle_action(
        "v_reyes",
        "ack_incident",
        {"req_id": "req_ack_inc", "member_id": "m_ana", "arg": f"inc_{verification_id}"},
    )
    assert acked["ok"] is True
    assert db.events[-1]["kind"] == "ack"


def test_post_verification_answer_route_uses_services() -> None:
    with TestClient(app) as client:
        client.post("/clock/warp", json={"reset": True})
        response = client.post(
            "/tools/report_money_request",
            json={
                "conversation_id": "conv_http_answer",
                "tool_call_id": "tool_http_answer",
                "caller_id": "+15555550101",
                "call_secs": 9,
                "utterance": "Marco needs money",
                "claimed_member": "marco",
                "claimed_identity": "Marco",
                "amount": 2000,
                "currency": "USD",
                "method": "unknown",
                "urgency": "now",
            },
        )
        verification_id = response.json()["data"]["verification_id"]
        answer = client.post(f"/verifications/{verification_id}/answer", json={"verification_answer": "no", "member_id": "m_marco"})

    assert answer.status_code == 200
    assert answer.json()["state"] == "denied"
