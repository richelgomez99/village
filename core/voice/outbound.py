from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from core.clock import clock
from core.db import db

ROOT = Path(__file__).resolve().parents[2]
REYES_SPEC = ROOT / "contracts" / "fixtures" / "reyes_spec.json"


def _people() -> list[dict[str, Any]]:
    return json.loads(REYES_SPEC.read_text())["blueprint"]["people"]


def member(member_id: str) -> dict[str, Any] | None:
    for person in _people():
        if person["id"] == member_id:
            return person
    return None


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


def build_payload(person: dict[str, Any], verification_id: str) -> dict[str, Any]:
    return {
        "agent_id": os.getenv("ELEVENLABS_AGENT_CALLER_ID", ""),
        "agent_phone_number_id": os.getenv("ELEVENLABS_PHONE_NUMBER_ID", ""),
        "to_number": person["phone"],
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "recipient_name": person["name"].split()[0],
                "family_label": "the Reyes family",
                "family_word": "[PALABRA]",
                "care_recipient_rel": "your mom",
                "amount_spoken": "$2,000",
                "method_spoken": "",
                "coordinator_name": "Ana",
                "verification_id": verification_id,
                "village_id": "v_reyes",
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

