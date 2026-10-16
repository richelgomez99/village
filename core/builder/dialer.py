"""Dialer port for the Founder's availability + consent call (D23 #4). Real calls go through
`core.voice.outbound.ElevenLabsDialer` (same `outbound_call(payload)` shape); the call's answer
arrives later via the post-call webhook, so the draft shows 'call placed' until then.
`ScriptedConsentDialer` returns a finished answer (tests / `--llm off` demo; clearly mocked)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


class Dialer(Protocol):
    async def outbound_call(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class ScriptedConsentDialer:
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def outbound_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        member = payload["conversation_initiation_client_data"]["dynamic_variables"]["member_id"]
        out = {"success": True, "conversation_id": f"conv_founder_{len(self.calls)}", "mocked": True}
        if member in self.answers:
            out["answer"] = self.answers[member]
        return out


REYES_SCRIPT = {"m_marco": {"availability_days": ["Tue", "Thu", "Fri", "Sat"], "ai_calls": True, "secs": 41}}


def consent_call_payload(person: dict[str, Any], *, village_id: str, coordinator_name: str, family_label: str) -> dict[str, Any]:
    return {
        "agent_id": os.getenv("ELEVENLABS_AGENT_CALLER_ID", os.getenv("ELEVENLABS_AGENT_ID", "")),
        "agent_phone_number_id": os.getenv("ELEVENLABS_PHONE_NUMBER_ID", ""),
        "to_number": person.get("phone", ""),
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "purpose": "availability_consent",
                "recipient_name": person["name"].split()[0],
                "family_label": family_label,
                "coordinator_name": coordinator_name,
                "village_id": village_id,
                "member_id": person["id"],
            }
        },
        "telephony_call_config": {"ringing_timeout_secs": 30},
    }


def default_dialer() -> Dialer | None:
    try:
        from core.voice.outbound import ElevenLabsDialer  # type: ignore

        if os.getenv("ELEVENLABS_API_KEY") and os.getenv("FOUNDER_LIVE_CALLS") == "1":
            return ElevenLabsDialer()
    except Exception:
        pass
    return None
