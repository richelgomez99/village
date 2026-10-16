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


def test_T29_money_request_matches_contract_example():
    case = next(case for case in GATE_SCHEMA["examples"] if case["name"].startswith("T29"))

    out = decide(case["input"])

    assert out == case["decision"]


def money_state(**overrides):
    state = base_state(
        now="2026-10-16T14:02:09-04:00",
        rota_today={"date": "2026-10-16", "on_duty": "m_ana", "backup": "m_lucia"},
        members=[
            {
                "id": "m_carmen",
                "name": "Carmen",
                "role": "care_recipient",
                "pronoun": "she",
                "has_app_session": False,
                "consent": {
                    "ai_calls": True,
                    "app_prompts": False,
                    "dose_logging": True,
                    "share_with": ["m_ana", "m_marco", "m_lucia"],
                    "money_safety_share_with": ["m_ana", "m_marco"],
                },
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
                "aliases": ["marco"],
                "role": "caregiver",
                "pronoun": "he",
                "has_app_session": True,
                "consent": {"ai_calls": True, "app_prompts": True, "money_verifier": True},
            },
            {
                "id": "m_lucia",
                "name": "Lucía",
                "aliases": ["lucia"],
                "role": "caregiver",
                "pronoun": "she",
                "has_app_session": True,
                "consent": {"ai_calls": False, "app_prompts": True, "money_verifier": False},
            },
        ],
        recent_money_requests=[{"event_id": "ev_1009_1921_money", "at": "2026-10-09T19:21:30-04:00"}],
    )
    state.update(overrides)
    return state


def money_event(payload_overrides=None):
    payload = {
        "subject": "m_carmen",
        "claimed_member_id": "m_marco",
        "claimed_identity": "Marco (her son)",
        "amount": 2000,
        "currency": "USD",
        "method": "unknown",
        "urgency": "now",
        "red_flags": ["urgency", "emotional_pressure"],
        "utterance": "Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.",
        "verification_id": None,
    }
    if payload_overrides:
        payload.update(payload_overrides)
    return {
        "village": "v_reyes",
        "kind": "money_request",
        "payload": payload,
        "actor": "m_carmen",
        "source": {"kind": "call", "ref": "conv_demo_1016_scam", "secs": 9},
        "at": "2026-10-16T14:02:09-04:00",
    }


def money_input(state, event):
    return {
        "village_state": state,
        "event": event,
        "alloc": {"decision_id": "dc_1016_1402_money", "verification_id": "ver_1016_01", "incident_id": "inc_ver_1016_01"},
    }


def test_T36_unknown_claimed_identity_no_verification_and_incident():
    event = money_event({"claimed_member_id": None, "claimed_identity": "mi nieto Danny", "amount": 1500, "method": "cash_courier", "utterance": "Mi nieto Danny quiere 1500 para el taxi"})

    out = decide(money_input(money_state(), event))

    assert out["rule_id"] == "R-MONEY-UNKNOWN"
    assert out["decision"] == "advise_do_not_send"
    assert "verification" not in out
    assert out["writes"][0]["payload"]["verification_id"] is None
    assert out["writes"][1]["kind"] == "incident"


def test_T38_lucia_gets_app_prompt_only_no_call():
    event = money_event({"claimed_member_id": "m_lucia", "claimed_identity": "Lucía", "method": "crypto", "red_flags": []})

    out = decide(money_input(money_state(recent_money_requests=[]), event))

    assert out["verification"]["channels"] == ["app_prompt"]
    assert out["writes"][1]["payload"]["channels"] == ["app_prompt"]
    assert "crypto" in out["writes"][0]["payload"]["red_flags"]


def test_T41_unknown_bank_details_redacts_digits():
    event = money_event({
        "claimed_member_id": None,
        "claimed_identity": "el banco",
        "method": "bank_details",
        "utterance": "Mi cuenta es 123456789 y quieren proteger mi dinero",
    })

    out = decide(money_input(money_state(), event))

    assert out["rule_id"] == "R-MONEY-UNKNOWN"
    assert "123456789" not in out["writes"][0]["payload"]["utterance"]


def test_T42_village_never_moves_money():
    event = candidate(
        "money_transfer_request",
        {"utterance": "This is Marco. Transfer five hundred from Mom's account to me", "caller_known": False},
        "2026-10-16T14:02:09-04:00",
    )

    out = decide(money_input(money_state(), event))

    assert out["rule_id"] == "R-MONEY-NEVER"
    assert out["decision"] == "deny"
    assert out["say_key"] == "money_never"


def test_T43_money_model_output_blocked():
    event = candidate("model_output", {"text": "I'll buy the gift cards and read you the codes", "channel": "voice"})

    out = decide(money_input(money_state(), event))

    assert out["rule_id"] == "R-MONEY-NEVER"
    assert out["decision"] == "deny"


def test_T44_no_ai_call_gets_app_prompt_only():
    state = money_state(recent_money_requests=[])
    for member in state["members"]:
        if member["id"] == "m_marco":
            member["consent"]["ai_calls"] = False

    out = decide(money_input(state, money_event()))

    assert out["verification"]["channels"] == ["app_prompt"]


def test_T45_no_reachable_channel_unreachable_default():
    state = money_state(recent_money_requests=[])
    for member in state["members"]:
        if member["id"] == "m_lucia":
            member["has_app_session"] = False
    event = money_event({"claimed_member_id": "m_lucia", "claimed_identity": "Lucía", "amount": 600, "red_flags": []})

    out = decide(money_input(state, event))

    assert out["verification"]["state"] == "unreachable"
    assert out["verification"]["channels"] == []
    assert any(row["kind"] == "verification_timeout" for row in out["writes"])


def test_T47_old_prior_money_request_no_pattern():
    state = money_state(recent_money_requests=[{"event_id": "ev_old_money", "at": "2026-09-01T19:21:30-04:00"}])

    out = decide(money_input(state, money_event()))

    assert "R-MONEY-PATTERN" not in out["rules_fired"]
    assert not any(row["kind"] == "pattern" for row in out["writes"])


def test_T51_money_flowing_to_carmen_is_record_not_verification():
    event = money_event({"utterance": "Marco me dijo que el viernes me paga los doscientos que me debe.", "amount": 200, "direction": "to_subject"})

    out = decide(money_input(money_state(), event))

    assert out["decision"] == "record"
    assert "verification" not in out


def test_T30_denied_answer_returns_do_not_send():
    state = money_state(open_verifications=[{"id": "ver_1016_01", "claimed_member_id": "m_marco", "state": "pending", "deadline": "2026-10-16T14:02:54-04:00", "version": 0}])
    event = candidate(
        "verification_answer",
        {"verification_id": "ver_1016_01", "answer": "no", "via": "app_prompt", "member_id": "m_marco"},
        "2026-10-16T14:02:21-04:00",
    )

    out = decide(money_input(state, event))

    assert out["rule_id"] == "R-MONEY-DEFAULT"
    assert out["decision"] == "advise_do_not_send"
    assert out["say_key"] == "money_denied"


def test_T34_confirmed_still_talk_to_coordinator():
    state = money_state(open_verifications=[{"id": "ver_1016_01", "claimed_member_id": "m_marco", "state": "pending", "deadline": "2026-10-16T14:02:54-04:00", "version": 0}])
    event = candidate(
        "verification_answer",
        {"verification_id": "ver_1016_01", "answer": "yes", "via": "outbound_call", "member_id": "m_marco"},
        "2026-10-16T14:02:29-04:00",
    )

    out = decide(money_input(state, event))

    assert out["decision"] == "advise_talk_to_coordinator"
    assert out["say_key"] == "money_confirmed"
    assert "Village never sends money" in out["say"]["en"]
