from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.gate import decide

GATE_SCHEMA = json.loads((ROOT / "contracts" / "schemas" / "gate.schema.json").read_text())


def base_state(**overrides):
    state = {
        "village_id": "v_reyes",
        "now": "2026-10-15T08:40:00-04:00",
        "timezone": "America/New_York",
        "kill_switch": False,
        "coordinator_id": "m_ana",
        "care_recipient_id": "m_carmen",
        "quiet_hours": "22:30-07:00",
        "double_dose_window_hours": 6,
        "rota_today": {"date": "2026-10-15", "on_duty": "m_marco", "backup": "m_ana"},
        "members": [
            {
                "id": "m_carmen",
                "name": "Carmen",
                "role": "care_recipient",
                "pronoun": "she",
                "has_app_session": False,
                "consent": {"ai_calls": True, "app_prompts": False, "dose_logging": True, "share_with": ["m_ana", "m_marco"]},
            },
            {
                "id": "m_ana",
                "name": "Ana",
                "role": "coordinator",
                "pronoun": "she",
                "has_app_session": True,
                "consent": {"ai_calls": True, "app_prompts": True, "money_verifier": True},
            },
            {
                "id": "m_marco",
                "name": "Marco",
                "role": "caregiver",
                "pronoun": "he",
                "has_app_session": True,
                "consent": {"ai_calls": True, "app_prompts": True, "money_verifier": True},
            },
        ],
        "dose_windows": [],
        "open_verifications": [],
        "recent_money_requests": [],
    }
    state.update(overrides)
    return state


def candidate(kind, payload, at="2026-10-15T08:40:00-04:00"):
    return {
        "village": "v_reyes",
        "kind": kind,
        "payload": payload,
        "actor": "m_carmen",
        "source": {"kind": "app", "ref": "m_carmen"},
        "at": at,
    }


def gate_input(state, event):
    return {"village_state": state, "event": event, "alloc": {"decision_id": "dc_test_001"}}


def taken_window(slot="morning", taken_at="2026-10-15T08:02:10-04:00", confidence="confirmed"):
    return {
        "subject": "m_carmen",
        "slot": slot,
        "date": "2026-10-15",
        "slot_time": "08:00",
        "state": "taken",
        "dose_event_id": "ev_1015_0802_dose_morning",
        "taken_at": taken_at,
        "confidence": confidence,
        "version": 3,
    }


def test_T28_second_lid_scan_reports_only_verbatim():
    state = base_state(dose_windows=[taken_window()])
    event = candidate(
        "dose",
        {"subject": "m_carmen", "slot": "morning", "taken_at": "2026-10-15T08:40:00-04:00", "confidence": "confirmed", "via": "lid_qr"},
    )
    out = decide(gate_input(state, event))

    assert out["rule_id"] == "R-DOUBLE"
    assert out["decision"] == "report_already_logged"
    assert out["say"]["es"] == "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco."
    assert out["escalate"] == {"member_id": "m_marco", "channel": "both", "level": 1}
    assert out["writes"][0]["kind"] == "dose_repeat_scan"
    assert out["rules_fired"][:2] == ["R-DOUBLE", "P-DD-01"]


def test_T03_records_prior_day_dose_outside_window():
    state = base_state(dose_windows=[taken_window(taken_at="2026-10-14T19:40:00-04:00")])
    event = candidate(
        "dose",
        {"subject": "m_carmen", "slot": "evening", "taken_at": "2026-10-15T19:45:00-04:00", "confidence": "confirmed", "via": "app"},
        "2026-10-15T19:45:00-04:00",
    )

    out = decide(gate_input(state, event))

    assert out["rule_id"] == "R-WINDOW"
    assert out["decision"] == "record"
    assert out["writes"][0]["kind"] == "dose"


def test_T05_duplicate_already_happened_escalates_without_dose_advice():
    state = base_state(dose_windows=[taken_window()])
    event = candidate(
        "dose_question",
        {"subject": "m_carmen", "slot": "morning", "intent": "double_already_taken", "utterance": "I took them twice"},
        "2026-10-15T09:00:00-04:00",
    )

    out = decide(gate_input(state, event))

    assert out["rule_id"] == "R-DOSE-ADVICE"
    assert out["decision"] == "escalate_family"
    assert out["writes"][0]["payload"]["flags"] == ["possible_double_dose"]
    assert "fine" not in out["say"]["en"].lower()


def test_T12_refuses_medication_advice():
    out = decide(gate_input(base_state(), candidate("dose_question", {"subject": "m_carmen", "intent": "skip", "utterance": "Can I take two since I missed one?"})))

    assert out["rule_id"] == "R-DOSE-ADVICE"
    assert out["decision"] == "refuse_medical_advice"


def test_T14_schedule_query_reads_active_meds_only():
    state = base_state(
        active_meds=[
            {"med_id": "rx_lis_10", "name": "lisinopril", "dose": "10 mg", "slots": ["morning"], "valid_from": "2026-10-03"}
        ]
    )

    out = decide(gate_input(state, candidate("schedule_query", {"subject": "m_carmen", "slot": "morning"})))

    assert out["decision"] == "remind"
    assert "10 mg" in out["say"]["es"]


def test_T17_911_cannot_be_downgraded():
    out = decide(gate_input(base_state(), candidate("symptom", {"subject": "m_carmen", "type": "symptom", "description": "My chest hurts and my arm is numb", "emergency_signals": True})))

    assert out["rule_id"] == "R-911"
    assert out["decision"] == "advise_911"
    assert out["say"]["en"].startswith("Call 911 now")


def test_T19_covert_surveillance_denied():
    out = decide(gate_input(base_state(), candidate("ask_family", {"utterance": "track my wife's location without telling her"})))

    assert out["rule_id"] == "R-CONSENT"
    assert out["decision"] == "deny"


def test_T13_model_medical_output_blocked():
    out = decide(gate_input(base_state(), candidate("model_output", {"text": "one more is okay", "channel": "voice"})))

    assert out["rule_id"] == "R-AUTONOMY"
    assert out["decision"] == "deny"


def test_spec_patch_requires_approval():
    out = decide(gate_input(base_state(), candidate("spec_patch", {"proposal_id": "prop_001", "approver": "m_ana"})))

    assert out["rule_id"] == "R-SPEC"
    assert out["decision"] == "require_approval"


def test_kill_switch_denies_agent_action():
    out = decide(gate_input(base_state(kill_switch=True), candidate("dose_question", {"subject": "m_carmen", "intent": "status", "utterance": "status"})))

    assert out["rule_id"] == "R-KILL"
    assert out["decision"] == "deny"
    assert out["flags"] == ["kill_switch"]
