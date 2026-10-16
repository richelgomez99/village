from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core.gate.models import Decision, GateInput, append_rule, decision_base, member_by_id, member_name
from core.gate.say import say


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def local_hm(value: str, timezone: str) -> str:
    dt = parse_dt(value).astimezone(ZoneInfo(timezone))
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt.minute:02d}"


def finish(
    inp: GateInput,
    rule_id: str,
    gate_decision: str,
    say_key: str = "silent",
    say_vars: dict[str, str] | None = None,
    rules: list[str] | None = None,
) -> Decision:
    out = decision_base(inp, rule_id, gate_decision)
    values = say_vars or {}
    out["say"] = say(say_key, **{**village_names(inp), **values})
    out["say_vars"] = {k: str(v) for k, v in values.items()}
    if say_key != "silent":
        out["say_key"] = say_key
    for rule in rules or []:
        append_rule(out, rule)
    return out


def village_names(inp: GateInput) -> dict[str, str]:
    """Names for gate-owned lines come from village_state (built from the village spec), never code."""
    state = inp.village_state
    names: dict[str, str] = {}
    for var, key in (("coordinator_name", "coordinator_id"), ("recipient_name", "care_recipient_id")):
        member = member_by_id(state, state.get(key))
        if member and member.get("name"):
            names[var] = str(member["name"])
    return names


def coordinator_notify(inp: GateInput, severity: str = "warn", reason: str = "gate_notice") -> dict[str, str]:
    return {
        "member_id": inp.village_state["coordinator_id"],
        "channel": "app",
        "severity": severity,
        "reason": reason,
    }


def on_duty_name(inp: GateInput) -> str:
    return member_name(inp.village_state, inp.village_state.get("rota_today", {}).get("on_duty"))
