from datetime import timedelta

from core import dialer
from core.clock import clock
from core.db import db
from core.dialer import FakeDialer
from core.fixtures import reset_demo
from core.scheduler import recover
from core import services


def _row(vid: str, *, deadline_delta_s: int, call_placed: bool) -> dict:
    now = clock.now()
    return {
        "id": vid,
        "village": "v_reyes",
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "claimed_identity": "Marco",
        "state": "pending",
        "status": "pending",
        "channels": [{"via": "app_prompt", "member_id": "m_marco", "status": "sent"}, {"via": "outbound_call", "member_id": "m_marco", "status": "ringing"}],
        "answers": [],
        "request": {"amount": 2000},
        "created_at": (now - timedelta(seconds=60)).isoformat(),
        "deadline": (now + timedelta(seconds=deadline_delta_s)).isoformat(),
        "call_placed_at": (now - timedelta(seconds=55)).isoformat() if call_placed else None,
        "version": 3,
        "transitions": [],
    }


async def test_restart_closes_past_deadline_without_redial() -> None:
    await reset_demo("v_reyes")
    fake = FakeDialer()
    dialer.set_dialer(fake)
    try:
        await db.upsert_verification(_row("ver_restart_past", deadline_delta_s=-10, call_placed=True))
        result = await recover()
        timeouts = [ev for ev in db.events if ev["kind"] == "verification_timeout" and ev["payload"]["verification_id"] == "ver_restart_past"]
        assert len(timeouts) == 1
        assert db.verifications["ver_restart_past"]["state"] == "timed_out"
        assert fake.calls == []
        assert result["verification_timeouts"] == 1
        await recover()  # a second boot tick writes nothing new
        assert len([ev for ev in db.events if ev["kind"] == "verification_timeout" and ev["payload"]["verification_id"] == "ver_restart_past"]) == 1
    finally:
        dialer.set_dialer(None)


async def test_restart_never_redials_when_call_placed() -> None:
    await reset_demo("v_reyes")
    fake = FakeDialer()
    dialer.set_dialer(fake)
    try:
        await db.upsert_verification(_row("ver_restart_open", deadline_delta_s=30, call_placed=True))
        result = await recover()
        assert fake.calls == []
        assert result["not_redialed"] == 1
        assert db.verifications["ver_restart_open"]["state"] == "pending"
    finally:
        dialer.set_dialer(None)


async def test_money_request_dials_marco_once_even_on_duplicate_webhook() -> None:
    await reset_demo("v_reyes")
    fake = FakeDialer()
    dialer.set_dialer(fake)
    body = {
        "conversation_id": "conv_dial_once",
        "caller_id": "+15555550101",
        "call_secs": 9,
        "utterance": "Marco needs money",
        "tool_call_id": "toolu_dial",
        "claimed_member": "marco",
        "amount": 2000,
        "urgency": "now",
    }
    try:
        first = await services.handle_tool("report_money_request", body)
        await dialer.drain()
        second = await services.handle_tool("report_money_request", body)
        await dialer.drain()
        assert first == second
        assert len(fake.calls) == 1
        vid = first["data"]["verification_id"]
        assert db.verifications[vid]["call_placed_at"]
        assert fake.calls[0]["conversation_initiation_client_data"]["dynamic_variables"]["verification_id"] == vid
    finally:
        dialer.set_dialer(None)


async def test_no_consent_no_dial() -> None:
    await reset_demo("v_reyes")
    fake = FakeDialer()
    dialer.set_dialer(fake)
    try:
        row = _row("ver_lucia", deadline_delta_s=30, call_placed=False)
        row["claimed_member_id"] = "m_lucia"
        await db.upsert_verification(row)
        outcome = await dialer.dial_verification("ver_lucia")
        assert outcome["status"] == "skipped_no_consent"
        assert fake.calls == []
    finally:
        dialer.set_dialer(None)


def test_default_dialer_is_fake_in_tests() -> None:
    assert dialer.mode() == "fake"
