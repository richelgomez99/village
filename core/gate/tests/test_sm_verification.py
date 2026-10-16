from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.gate.sm_verification import step_verification


def verification(state="pending", **overrides):
    row = {
        "id": "ver_1016_01",
        "village": "v_reyes",
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "claimed_identity": "Marco (her son)",
        "origin": "report_money_request",
        "conversation_id": "conv_demo_1016_scam",
        "money_request_event_id": "ev_1016_1402_money",
        "request": {"amount": 2000, "currency": "USD", "method": "unknown", "urgency": "now", "red_flags": []},
        "state": state,
        "status": "pending",
        "channels": [],
        "answers": [],
        "created_at": "2026-10-16T14:02:09-04:00",
        "deadline": "2026-10-16T14:02:54-04:00",
        "call_placed_at": None,
        "await_returned_at": None,
        "resolved_at": None,
        "spoken_say_key": None,
        "incident_id": None,
        "version": 0,
        "transitions": [{"from": "created", "to": "pending", "at": "2026-10-16T14:02:09-04:00", "cause": "created"}],
    }
    if state == "default_spoken":
        row["await_returned_at"] = "2026-10-16T14:02:44-04:00"
        row["spoken_say_key"] = "money_timeout"
    row.update(overrides)
    return row


def test_pending_answer_yes_confirms_and_emits_event():
    row, emits = step_verification(
        verification(),
        {"type": "answer", "answer": "yes", "via": "app_prompt", "member_id": "m_marco"},
        "2026-10-16T14:02:21-04:00",
    )

    assert row["state"] == "confirmed"
    assert row["status"] == "confirmed"
    assert emits[0]["kind"] == "verification_confirmed"


def test_pending_answer_no_denies_and_opens_incident():
    row, emits = step_verification(
        verification(),
        {"type": "answer", "answer": "no", "via": "app_prompt", "member_id": "m_marco"},
        "2026-10-16T14:02:21-04:00",
    )

    assert row["state"] == "denied"
    assert row["status"] == "denied"
    assert [emit["kind"] for emit in emits] == ["verification_denied", "incident"]


def test_pending_answer_unsure_times_out():
    row, emits = step_verification(
        verification(),
        {"type": "answer", "answer": "unsure", "via": "app_prompt", "member_id": "m_marco"},
        "2026-10-16T14:02:21-04:00",
    )

    assert row["state"] == "unsure"
    assert row["status"] == "timeout"
    assert emits[0]["payload"]["reason"] == "unsure"


def test_await_after_30_seconds_sets_default_spoken():
    row, emits = step_verification(verification(), {"type": "await_returned"}, "2026-10-16T14:02:44-04:00")

    assert row["state"] == "default_spoken"
    assert row["status"] == "pending"
    assert row["spoken_say_key"] == "money_timeout"
    assert emits[0]["kind"] == "incident"


def test_tick_at_deadline_times_out_pending():
    row, emits = step_verification(verification(), {"type": "tick"}, "2026-10-16T14:02:54-04:00")

    assert row["state"] == "timed_out"
    assert row["status"] == "timeout"
    assert emits[0]["kind"] == "verification_timeout"


def test_late_no_after_default_spoken_updates_incident_without_say_change():
    row, emits = step_verification(
        verification("default_spoken"),
        {"type": "answer", "answer": "no", "via": "app_prompt", "member_id": "m_marco"},
        "2026-10-16T14:02:47-04:00",
    )

    assert row["state"] == "late_denied"
    assert row["spoken_say_key"] == "money_timeout"
    assert emits[0]["payload"]["late"] is True


def test_late_yes_after_default_spoken_confirms_but_keeps_safe_spoken_line():
    row, emits = step_verification(
        verification("default_spoken"),
        {"type": "answer", "answer": "yes", "via": "outbound_call", "member_id": "m_marco"},
        "2026-10-16T14:02:47-04:00",
    )

    assert row["state"] == "late_confirmed"
    assert row["spoken_say_key"] == "money_timeout"
    assert emits[0]["kind"] == "verification_confirmed"


def test_default_spoken_tick_deadline_finishes_timed_out():
    row, emits = step_verification(verification("default_spoken"), {"type": "tick"}, "2026-10-16T14:02:54-04:00")

    assert row["state"] == "timed_out"
    assert [emit["kind"] for emit in emits] == ["verification_timeout"]


def test_duplicate_same_answer_is_stored_dup_no_state_change():
    start = verification("denied", answers=[{"answer": "no", "via": "app_prompt", "member_id": "m_marco", "at": "2026-10-16T14:02:21-04:00", "secs_since_created": 12, "outcome": "applied"}], status="denied", resolved_at="2026-10-16T14:02:21-04:00")

    row, emits = step_verification(
        start,
        {"type": "answer", "answer": "no", "via": "outbound_call", "member_id": "m_marco"},
        "2026-10-16T14:02:22-04:00",
    )

    assert row["state"] == "denied"
    assert row["answers"][-1]["outcome"] == "dup"
    assert emits == []


def test_T50_conflict_after_yes_downgrades_to_unconfirmed():
    start = verification("confirmed", answers=[{"answer": "yes", "via": "app_prompt", "member_id": "m_marco", "at": "2026-10-16T14:02:21-04:00", "secs_since_created": 12, "outcome": "applied"}], status="confirmed", resolved_at="2026-10-16T14:02:21-04:00")

    row, emits = step_verification(
        start,
        {"type": "answer", "answer": "no", "via": "outbound_call", "member_id": "m_marco"},
        "2026-10-16T14:02:21-04:00",
    )

    assert row["state"] == "unsure"
    assert row["status"] == "timeout"
    assert row["answers"][-1]["outcome"] == "conflict"
    assert emits[0]["kind"] == "verification_answer_conflict"


def test_answer_after_terminal_without_conflict_is_ignored():
    start = verification("timed_out", status="timeout", resolved_at="2026-10-16T14:02:54-04:00")

    row, emits = step_verification(
        start,
        {"type": "answer", "answer": "yes", "via": "app_prompt", "member_id": "m_marco"},
        "2026-10-16T14:03:00-04:00",
    )

    assert row["state"] == "timed_out"
    assert row["answers"][-1]["outcome"] == "ignored"
    assert emits == []


def test_restart_pending_with_call_placed_does_not_redial():
    start = verification(call_placed_at="2026-10-16T14:02:10-04:00")

    row, emits = step_verification(start, {"type": "noop"}, "2026-10-16T14:02:20-04:00")

    assert row["call_placed_at"] == "2026-10-16T14:02:10-04:00"
    assert emits == []


def test_deadline_during_inflight_await_returns_timeout_state():
    row, emits = step_verification(verification(), {"type": "tick"}, "2026-10-16T14:03:00-04:00")

    assert row["state"] == "timed_out"
    assert any(emit["kind"] == "verification_timeout" for emit in emits)
