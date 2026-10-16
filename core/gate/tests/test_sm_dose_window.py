from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.gate.sm_dose_window import FakeClock, step_dose_window


def window(**overrides):
    row = {
        "village": "v_reyes",
        "subject": "m_carmen",
        "slot": "evening",
        "date": "2026-10-15",
        "slot_time": "19:30",
        "state": "scheduled",
        "version": 0,
        "on_duty": "m_marco",
        "backup": "m_ana",
        "quiet_hours": "22:30-07:00",
    }
    row.update(overrides)
    return row


def test_dose_window_opens_30_minutes_before_due():
    row, actions = step_dose_window(window(), {"type": "tick"}, "2026-10-15T19:00:00-04:00")

    assert row["state"] == "window_open"
    assert actions == []


def test_T06_reminder_at_45_minutes_late():
    row, actions = step_dose_window(window(state="window_open"), {"type": "tick"}, "2026-10-15T20:15:00-04:00")

    assert row["state"] == "reminded"
    assert actions[0]["type"] == "CALL"
    assert actions[0]["member_id"] == "m_carmen"
    assert actions[0]["event"]["kind"] == "reminder"


def test_T07_reminder_not_repeated_after_warp_back_and_forth():
    start = window(state="reminded", reminder_placed_at="2026-10-15T20:15:00-04:00")
    clock = FakeClock("2026-10-15T20:30:00-04:00")
    row, actions = step_dose_window(start, {"type": "tick"}, clock.now())
    assert row["state"] == "reminded"
    assert actions == []

    clock.warp(minutes=-20)
    row, actions = step_dose_window(row, {"type": "tick"}, clock.now())
    assert actions == []

    clock.warp(minutes=25)
    row, actions = step_dose_window(row, {"type": "tick"}, clock.now())
    assert actions == []


def test_T08_escalates_to_on_duty_at_90_minutes_late():
    row, actions = step_dose_window(window(state="reminded", reminder_placed_at="2026-10-15T20:15:00-04:00"), {"type": "tick"}, "2026-10-15T21:00:00-04:00")

    assert row["state"] == "escalated_1"
    assert actions[0]["member_id"] == "m_marco"
    assert actions[0]["event"]["payload"]["level"] == 1


def test_T09_escalates_to_backup_after_no_answer():
    row, actions = step_dose_window(window(state="escalated_1", escalation_placed_at="2026-10-15T21:00:00-04:00", escalated_to="m_marco"), {"type": "tick"}, "2026-10-15T21:15:00-04:00")

    assert row["state"] == "escalated_2"
    assert actions[0]["member_id"] == "m_ana"
    assert actions[0]["event"]["payload"]["level"] == 2


def test_T10_friday_rota_uses_marco_when_on_duty():
    row, actions = step_dose_window(
        window(state="reminded", date="2026-10-16", reminder_placed_at="2026-10-16T20:15:00-04:00", on_duty="m_marco", backup="m_ana"),
        {"type": "tick"},
        "2026-10-16T21:00:00-04:00",
    )

    assert row["state"] == "escalated_1"
    assert actions[0]["member_id"] == "m_marco"


def test_T27_quiet_hours_suppress_care_recipient_call_but_not_family_escalation():
    row, actions = step_dose_window(window(state="window_open", slot_time="21:55"), {"type": "tick"}, "2026-10-15T22:40:00-04:00")

    assert row["state"] == "window_open"
    assert actions == []

    row, actions = step_dose_window(window(state="window_open", slot_time="21:10"), {"type": "tick"}, "2026-10-15T22:40:00-04:00")
    assert row["state"] == "escalated_1"
    assert actions[0]["member_id"] == "m_marco"


def test_dose_event_marks_window_taken():
    row, actions = step_dose_window(
        window(state="window_open"),
        {"type": "dose", "event_id": "ev_dose_1", "taken_at": "2026-10-15T19:40:00-04:00", "confidence": "confirmed"},
        "2026-10-15T19:40:00-04:00",
    )

    assert row["state"] == "taken"
    assert row["dose_event_id"] == "ev_dose_1"
    assert actions == []


def test_cutoff_closes_open_window_after_four_hours():
    row, actions = step_dose_window(window(state="escalated_2"), {"type": "tick"}, "2026-10-15T23:30:00-04:00")

    assert row["state"] == "closed"
    assert actions == []
