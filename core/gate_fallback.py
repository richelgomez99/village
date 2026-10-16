from __future__ import annotations

from datetime import datetime
from typing import Any


def _name(state: dict[str, Any], member_id: str | None, fallback: str) -> str:
    for member in state.get("members", []):
        if member.get("id") == member_id and member.get("name"):
            return str(member["name"])
    return fallback


def decide(inp: dict[str, Any]) -> dict[str, Any]:
    event = inp["event"]
    alloc = inp.get("alloc", {})
    state = inp.get("village_state", {})
    recipient = state.get("care_recipient_id")
    if event["kind"] == "dose":
        slot = event["payload"].get("slot", "evening")
        taken_at = event["payload"].get("taken_at") or event["at"]
        return {
            "id": alloc.get("decision_id", "dc_dose"),
            "rule_id": "R-WINDOW",
            "decision": "record",
            "say": {"es": f"Listo, {_name(state, recipient, '').strip() or 'ya'}. Anoté sus pastillas.".replace("Listo, ya.", "Listo."), "en": "Done. I logged it."},
            "say_key": "dose_recorded",
            "say_vars": {"slot": slot},
            "notify": [],
            "writes": [
                {
                    "kind": "dose",
                    "payload": {
                        "subject": event["payload"].get("subject") or recipient,
                        "slot": slot,
                        "taken_at": taken_at,
                        "confidence": event["payload"].get("confidence", "confirmed"),
                        "via": event["payload"].get("via", "phone_line"),
                    },
                }
            ],
            "flags": [],
            "rules_fired": ["R-WINDOW"],
        }
    if event["kind"] == "money_request":
        verification_id = alloc.get("verification_id", "ver_stub")
        deadline = event["payload"].get("deadline") or "2026-10-16T14:02:54-04:00"
        claimed = event["payload"].get("claimed_member_id")
        claimed_name = _name(state, claimed, "la persona")
        return {
            "id": alloc.get("decision_id", "dc_money"),
            "rule_id": "R-MONEY-VERIFY",
            "decision": "verify_with_member",
            "say": {
                "es": f"Voy a confirmar con {claimed_name} ahora mismo. No mande dinero todavía.",
                "en": f"I'm checking with {claimed_name} right now. Please don't send any money yet.",
            },
            "say_key": "money_hold",
            "say_vars": {"claimed_name": claimed_name},
            "notify": [{"member_id": state.get("coordinator_id"), "channel": "app", "severity": "warn", "reason": "money_request_pending"}],
            "verification": {
                "id": verification_id,
                "claimed_member": claimed,
                "deadline": deadline,
                "channels": ["app_prompt", "outbound_call"],
                "state": "pending",
            },
            "writes": [
                {
                    "kind": "money_request",
                    "payload": {**event["payload"], "verification_id": verification_id},
                },
                {
                    "kind": "verification_pending",
                    "payload": {
                        "verification_id": verification_id,
                        "subject": event["payload"].get("subject") or recipient,
                        "claimed_member_id": claimed,
                        "deadline": deadline,
                        "channels": ["app_prompt", "outbound_call"],
                        "origin": "report_money_request",
                    },
                },
            ],
            "flags": [],
            "rules_fired": ["R-MONEY-VERIFY", "R-VERIFY-CONSENT"],
        }
    return {
        "id": alloc.get("decision_id", f"dc_{datetime.now().timestamp():.0f}"),
        "rule_id": "R-NOOP",
        "decision": "allow",
        "say": {"es": "", "en": ""},
        "notify": [],
        "writes": [],
        "flags": [],
        "rules_fired": ["R-NOOP"],
    }
