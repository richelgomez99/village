from __future__ import annotations

from datetime import datetime
from typing import Any


def decide(inp: dict[str, Any]) -> dict[str, Any]:
    event = inp["event"]
    alloc = inp.get("alloc", {})
    if event["kind"] == "dose":
        slot = event["payload"].get("slot", "evening")
        taken_at = event["payload"].get("taken_at") or event["at"]
        return {
            "id": alloc.get("decision_id", "dc_dose"),
            "rule_id": "R-WINDOW",
            "decision": "record",
            "say": {"es": "Listo, Carmen. Anoté sus pastillas.", "en": "Done. I logged it."},
            "say_key": "dose_recorded",
            "say_vars": {"slot": slot},
            "notify": [],
            "writes": [
                {
                    "kind": "dose",
                    "payload": {
                        "subject": event["payload"].get("subject", "m_carmen"),
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
