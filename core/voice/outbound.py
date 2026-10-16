from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from core.clock import clock
from core.db import db
from core import village

_REL_SPOKEN = {"mother": "mom", "father": "dad"}


def member(member_id: str) -> dict[str, Any] | None:
    """The member's spec entry, from whichever registered village they belong to."""
    return village.person(village.member_village(member_id), member_id)


def consent_allows_ai_calls(member_id: str) -> bool:
    person = member(member_id)
    return bool(person and person.get("consent", {}).get("ai_calls") is True)


class OutboundRequest(BaseModel):
    member_id: str
    reason: str = "verification"
    template: str = "T3"
    verification_id: str


@dataclass
class FakeDialer:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def outbound_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "success": True,
            "conversation_id": f"conv_out_{len(self.calls)}",
            "callSid": f"CA_fake_{len(self.calls)}",
        }

    async def cancel(self, call_sid: str) -> bool:
        self.calls.append({"cancel": call_sid})
        return True


class ElevenLabsDialer:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "")

    async def outbound_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY missing")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
                headers={"xi-api-key": self.api_key, "content-type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def cancel(self, call_sid: str) -> bool:
        del call_sid
        return False


def build_payload(person: dict[str, Any], verification_id: str, village_id: str | None = None) -> dict[str, Any]:
    vid = village_id or village.member_village(person["id"])
    recipient = village.person(vid, village.care_recipient_id(vid)) or {}
    relation = str(recipient.get("relation") or "family member")
    return {
        "agent_id": os.getenv("ELEVENLABS_AGENT_CALLER_ID", ""),
        "agent_phone_number_id": os.getenv("ELEVENLABS_PHONE_NUMBER_ID", ""),
        "to_number": person["phone"],
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "recipient_name": person["name"].split()[0],
                "family_label": village.village_name(vid),
                "family_word": village.family_word(vid) or "",
                "care_recipient_rel": f"your {_REL_SPOKEN.get(relation, relation)}",
                "amount_spoken": "$2,000",
                "method_spoken": "",
                "coordinator_name": village.first_name(vid, village.coordinator_id(vid)),
                "verification_id": verification_id,
                "village_id": vid,
                "member_id": person["id"],
            }
        },
        "telephony_call_config": {"ringing_timeout_secs": 30},
    }


class OutboundService:
    def __init__(self, dialer: Any | None = None) -> None:
        self.dialer = dialer or ElevenLabsDialer()

    async def place(self, request: OutboundRequest) -> dict[str, Any]:
        person = member(request.member_id)
        if person is None:
            raise HTTPException(status_code=404, detail="unknown member")

        row = db.verifications.get(request.verification_id)
        if row is None:
            raise HTTPException(status_code=404, detail="unknown verification")

        if row.get("state") not in {None, "pending"} or row.get("status") not in {None, "pending"}:
            return {"placed": False, "status": "terminal"}

        if row.get("call_placed_at"):
            return {"placed": False, "status": "already_placed"}

        if not consent_allows_ai_calls(request.member_id):
            return {"placed": False, "status": "skipped_no_consent"}

        now = clock.now().isoformat()
        updated = await db.cas_update(
            "verification",
            request.verification_id,
            row.get("version", 0),
            {"call_placed_at": now},
        )
        if not updated:
            return {"placed": False, "status": "already_placed"}

        payload = build_payload(person, request.verification_id)
        result = await self.dialer.outbound_call(payload)
        try:  # D18: caption the verification call live on the Control Room (no-op without an API key)
            from core.voice.captions import start_poller

            start_poller(str(result.get("conversation_id") or ""), payload["conversation_initiation_client_data"]["dynamic_variables"].get("village_id", ""), {"user": person["name"].split()[0], "agent": "Village"})
        except Exception:
            pass
        latest = db.verifications[request.verification_id]
        channel = {
            "via": "outbound_call",
            "member_id": request.member_id,
            "status": "ringing",
            "ref": result.get("conversation_id", ""),
            "call_sid": result.get("callSid", ""),
            "at": now,
        }
        await db.upsert_verification({
            **latest,
            "channels": [*latest.get("channels", []), channel],
        })
        return {
            "placed": True,
            "status": "ringing",
            "conversation_id": result.get("conversation_id"),
            "call_sid": result.get("callSid"),
            "payload": payload,
        }


app = FastAPI(title="Village outbound voice")
service = OutboundService()


@app.post("/calls/outbound")
async def outbound(
    body: OutboundRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    expected = os.getenv("CONTROL_TOKEN")
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="bad control token")
    return await service.place(body)

