from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from core.clock import clock
from core.db import db
from core import village
from core.voice.tools import redact_digits

POST_CALLS: list[dict[str, Any]] = []


def _signature_parts(header: str) -> tuple[str, str]:
    parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    return parts.get("t", ""), parts.get("v0", "")


def verify_signature(raw: bytes, header: str | None, secret: str | None = None) -> None:
    secret = secret if secret is not None else os.getenv("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret:
        return
    if not header:
        raise HTTPException(status_code=401, detail="missing signature")
    timestamp, received = _signature_parts(header)
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail="bad signature")


def redact_text(value: str) -> str:
    return redact_digits(value.replace(os.getenv("VILLAGE_FAMILY_WORD", ""), "[PALABRA]") if os.getenv("VILLAGE_FAMILY_WORD") else value)


def clean_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [clean_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_payload(item) for key, item in value.items()}
    return value


def outbox_dir() -> Path:
    return Path(os.getenv("VOICE_MEMORY_OUTBOX", "core/voice/memory_outbox"))


def write_memory_outbox(conversation_id: str, payload: dict[str, Any]) -> None:
    directory = outbox_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{conversation_id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True))


async def record_call_failed(payload: dict[str, Any]) -> None:
    verification_id = payload.get("verification_id")
    if verification_id and verification_id in db.verifications:
        row = db.verifications[verification_id]
        channels = []
        for channel in row.get("channels", []):
            if channel.get("via") == "outbound_call":
                channel = {**channel, "status": "failed"}
            channels.append(channel)
        await db.upsert_verification({**row, "channels": channels})
    await db.create_event({
        "id": f"ev_call_failed_{len(db.events) + 1}",
        "village": payload.get("village_id") or village.default_village_id(),
        "kind": "call_failed",
        "payload": {
            "conversation_id": payload.get("conversation_id"),
            "verification_id": verification_id,
            "reason": payload.get("reason", payload.get("error", "unknown")),
        },
        "actor": "voice:post_call",
        "source": {"kind": "system", "ref": "elevenlabs_post_call"},
        "at": clock.now().isoformat(),
    })


async def apply_verification_answer(payload: dict[str, Any]) -> None:
    verification_id = payload.get("verification_id") or payload.get("dynamic_variables", {}).get("verification_id")
    data = payload.get("data_collection_results", payload.get("data_collection", {}))
    answer = data.get("verification_answer")
    if isinstance(answer, dict):
        answer = answer.get("value")
    if not verification_id or answer not in {"yes", "no", "unsure"}:
        return
    try:
        from core import services

        await services.answer_verification(
            verification_id,
            answer,
            via="outbound_call",
            member_id=payload.get("member_id")
            or payload.get("dynamic_variables", {}).get("member_id")
            or (db.verifications.get(verification_id) or {}).get("claimed_member_id")
            or village.default_verifier(payload.get("village_id")),
            quote=payload.get("listener_quote"),
            call_sid=payload.get("call_sid"),
        )
    except Exception:
        return


async def handle_payload(payload: dict[str, Any]) -> None:
    event_type = payload.get("type", payload.get("event", "post_call"))
    clean = clean_payload(payload)
    POST_CALLS.append(clean)

    if event_type == "call_initiation_failure":
        await record_call_failed(clean)
        return

    if event_type in {"post_call", "conversation_ended", "data_collection"}:
        await apply_verification_answer(clean)
        conversation_id = clean.get("conversation_id", "unknown_conversation")
        write_memory_outbox(conversation_id, clean)


app = FastAPI(title="Village ElevenLabs post-call hook")


@app.post("/hooks/elevenlabs/post-call")
async def post_call(request: Request) -> dict[str, bool]:
    raw = await request.body()
    verify_signature(raw, request.headers.get("ElevenLabs-Signature"))
    payload = json.loads(raw.decode() or "{}")
    await handle_payload(payload)
    return {"ok": True}

