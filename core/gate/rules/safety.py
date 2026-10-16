from __future__ import annotations

from datetime import timedelta
from typing import Any

from core.gate.models import GateInput, append_rule, copy_payload, member_name
from core.gate.rules.common import coordinator_notify, finish, local_hm, on_duty_name, parse_dt
from core.gate.rules.money import decide_money

EMERGENCY_WORDS = (
    "chest hurts",
    "arm is numb",
    "can't breathe",
    "cant breathe",
    "unresponsive",
    "stroke",
    "suicidal",
    "overdose",
    "no puedo respirar",
    "me duele el pecho",
)

MED_ADVICE_WORDS = (
    "take two",
    "one more",
    "missed one",
    "skip",
    "stop",
    "change it back",
    "change dose",
    "fine",
    "safe",
    "okay",
    "otra",
    "dos",
)

COERCIVE_PRIVACY_WORDS = ("without telling", "sin decir", "track", "location", "messages")


def decide_safety(inp: GateInput) -> dict[str, Any]:
    state = inp.village_state
    event = inp.event
    kind = event["kind"]
    payload = copy_payload(event)
    text = " ".join(str(payload.get(k, "")) for k in ("utterance", "text", "description")).lower()

    if state.get("kill_switch") and kind not in {"tick"}:
        out = finish(inp, "R-KILL", "deny", rules=["P-CO-01"])
        out["flags"] = ["kill_switch"]
        return out

    money_decision = decide_money(inp)
    if money_decision is not None:
        return money_decision

    if _has_emergency(kind, payload, text):
        out = finish(inp, "R-911", "advise_911", "advise_911_first", rules=["P-911-01", "P-911-02"])
        out["notify"] = [coordinator_notify(inp, "high", "emergency")]
        return out

    if _is_blocked_model_output(kind, payload, text):
        if _mentions_money_or_secret(text):
            # Money-specific model-output blocking is implemented in G004.
            pass
        else:
            return finish(inp, "R-AUTONOMY", "deny", "no_dose_advice", rules=["P-MA-01"])

    if _is_covert_surveillance(kind, payload, text):
        return finish(inp, "R-CONSENT", "deny", rules=["P-CO-02"])

    if kind == "spec_patch":
        return finish(inp, "R-SPEC", "require_approval", rules=["P-CO-01"])

    if kind in {"dose", "dose_question"}:
        double = _double_dose_window(inp)
        if double and (kind == "dose" or payload.get("intent") in {"take_another", "double_already_taken"}):
            if payload.get("intent") == "double_already_taken":
                out = finish(
                    inp,
                    "R-DOSE-ADVICE",
                    "escalate_family",
                    "no_dose_advice",
                    rules=["P-DD-02", "P-MA-01"],
                )
                dose_payload = _dose_payload_from_attempt(inp, payload, double, possible_double=True)
                out["writes"] = [{"kind": "dose", "payload": dose_payload}]
            else:
                logged_time = local_hm(double["taken_at"], state.get("timezone", "America/New_York"))
                out = finish(
                    inp,
                    "R-DOUBLE",
                    "report_already_logged",
                    "dd_report",
                    {"logged_time": logged_time, "on_duty_name": on_duty_name(inp)},
                    ["P-DD-01"],
                )
                out["escalate"] = {
                    "member_id": state["rota_today"]["on_duty"],
                    "channel": "both",
                    "level": 1,
                }
                out["writes"] = [{"kind": _repeat_kind(kind, payload), "payload": _repeat_payload(inp, payload, double)}]
                out["flags"] = ["possible_double_dose", "attempted_duplicate"]
            return out

        if kind == "dose_question" and payload.get("intent") in {"change_dose", "skip"}:
            return finish(inp, "R-DOSE-ADVICE", "refuse_medical_advice", "no_dose_advice", rules=["P-MA-01", "P-MA-03"])

    if kind == "schedule_query":
        schedule = _active_schedule(payload, state)
        return finish(
            inp,
            "R-DOSE-ADVICE",
            "remind",
            "schedule_readback",
            {"schedule": schedule},
            ["P-MA-02"],
        )

    if kind == "dose":
        out = finish(inp, "R-WINDOW", "record", "dose_recorded")
        dose_payload = copy_payload(event)
        flags = list(dose_payload.get("flags", []))
        if _off_schedule(inp, dose_payload) and "off_schedule" not in flags:
            flags.append("off_schedule")
        if flags:
            dose_payload["flags"] = flags
            out["flags"] = flags
        out["writes"] = [{"kind": "dose", "payload": dose_payload}]
        return out

    return finish(inp, "R-NOOP", "allow")


def _has_emergency(kind: str, payload: dict[str, Any], text: str) -> bool:
    if kind in {"symptom", "help_request"} and payload.get("emergency_signals") is True:
        return True
    return any(word in text for word in EMERGENCY_WORDS)


def _is_blocked_model_output(kind: str, payload: dict[str, Any], text: str) -> bool:
    return kind == "model_output" and any(word in text for word in MED_ADVICE_WORDS)


def _is_covert_surveillance(kind: str, payload: dict[str, Any], text: str) -> bool:
    return any(word in text for word in COERCIVE_PRIVACY_WORDS) and ("without telling" in text or "sin decir" in text)


def _mentions_money_or_secret(text: str) -> bool:
    return any(word in text for word in ("gift card", "account", "bank", "money", "tarjeta", "cuenta"))


def _double_dose_window(inp: GateInput) -> dict[str, Any] | None:
    payload = copy_payload(inp.event)
    subject = payload.get("subject")
    slot = payload.get("slot")
    if not subject or not slot:
        return None
    now = parse_dt(inp.event["at"])
    max_age = timedelta(hours=float(inp.village_state.get("double_dose_window_hours", 6)))
    for window in inp.village_state.get("dose_windows", []):
        if window.get("subject") != subject or window.get("slot") != slot:
            continue
        if window.get("state") != "taken" or not window.get("taken_at"):
            continue
        taken_at = parse_dt(window["taken_at"])
        if timedelta(0) <= now - taken_at <= max_age:
            return window
    return None


def _repeat_kind(kind: str, payload: dict[str, Any]) -> str:
    return "dose_repeat_scan" if payload.get("via") == "lid_qr" or kind == "dose" else "dose_repeat"


def _repeat_payload(inp: GateInput, payload: dict[str, Any], window: dict[str, Any]) -> dict[str, Any]:
    repeat = {
        "subject": payload["subject"],
        "slot": payload["slot"],
        "first_event_id": window["dose_event_id"],
        "first_taken_at": window["taken_at"],
        "attempted_at": inp.event["at"],
        "notified": inp.village_state["rota_today"]["on_duty"],
    }
    if payload.get("utterance"):
        repeat["utterance"] = payload["utterance"]
    return repeat


def _dose_payload_from_attempt(
    inp: GateInput, payload: dict[str, Any], window: dict[str, Any], possible_double: bool
) -> dict[str, Any]:
    dose_payload = {
        "subject": payload.get("subject", window["subject"]),
        "slot": payload.get("slot", window["slot"]),
        "taken_at": inp.event["at"],
        "confidence": "uncertain",
        "via": "phone_line",
    }
    if possible_double:
        dose_payload["flags"] = ["possible_double_dose"]
    return dose_payload


def _off_schedule(inp: GateInput, payload: dict[str, Any]) -> bool:
    for window in inp.village_state.get("dose_windows", []):
        if window.get("subject") == payload.get("subject") and window.get("slot") == payload.get("slot"):
            date = window.get("date")
            slot_time = window.get("slot_time")
            if not date or not slot_time:
                return False
            at = parse_dt(payload.get("taken_at") or inp.event["at"])
            scheduled = parse_dt(f"{date}T{slot_time}:00{at.strftime('%z')[:3]}:{at.strftime('%z')[3:]}")
            return not (scheduled - timedelta(minutes=30) <= at <= scheduled + timedelta(hours=4))
    return False


def _active_schedule(payload: dict[str, Any], state: dict[str, Any]) -> str:
    slot = payload.get("slot")
    meds = []
    for med in state.get("active_meds", []):
        if slot and slot not in med.get("slots", []):
            continue
        meds.append(f"{med['name']} {med['dose']}")
    return ", ".join(meds) if meds else "no hay medicamentos activos en este registro"
