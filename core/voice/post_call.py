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


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """ElevenLabs wraps events as {type, event_timestamp, data:{...}}; flatten to the shape the handlers read."""
    data = payload.get("data")
    kind = str(payload.get("type", ""))
    if not isinstance(data, dict) or kind not in {"post_call_transcription", "call_initiation_failure", "post_call_audio"}:
        return payload
    init = data.get("conversation_initiation_client_data") or {}
    analysis = data.get("analysis") or {}
    flat = {
        **data,
        "type": "post_call" if kind == "post_call_transcription" else kind,
        "event_timestamp": payload.get("event_timestamp"),
        "dynamic_variables": {**(data.get("dynamic_variables") or {}), **(init.get("dynamic_variables") or {})},
        "data_collection_results": analysis.get("data_collection_results") or data.get("data_collection_results") or {},
    }
    dv = flat["dynamic_variables"]
    for key in ("village_id", "member_id", "verification_id"):
        if dv.get(key) and not flat.get(key):
            flat[key] = dv[key]
    if kind == "call_initiation_failure":
        flat.setdefault("reason", data.get("failure_reason") or "unknown")
    return flat


def _dc_value(results: dict[str, Any], key: str) -> str:
    value = results.get(key)
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value).strip()


WELCOME_RESULTS: list[dict[str, Any]] = []


def _call_iso(payload: dict[str, Any]) -> str:
    from datetime import datetime, timezone

    stamp = (payload.get("metadata") or {}).get("start_time_unix_secs") or payload.get("event_timestamp")
    try:
        return datetime.fromtimestamp(float(stamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return clock.now().isoformat()


def _words_secs(payload: dict[str, Any], words: str) -> float:
    """Second in the call where she said it: the user turn that best matches her words, else the call length."""
    probe = words.lower()[:24]
    for turn in payload.get("transcript") or []:
        message = str(turn.get("message") or "").lower()
        if turn.get("role") == "user" and probe and (probe in message or message in probe):
            return float(turn.get("time_in_call_secs") or 0)
    return float((payload.get("metadata") or {}).get("call_duration_secs") or 0)


async def apply_welcome(payload: dict[str, Any], services: Any | None = None) -> dict[str, Any] | None:
    """Welcome call (D24 #5): her quiet hours, in her words, become P-QH-01 with call provenance."""
    dv = payload.get("dynamic_variables") or {}
    if dv.get("call_purpose") != "welcome":
        return None
    results = payload.get("data_collection_results") or {}
    quiet = _dc_value(results, "quiet_hours")
    words = _dc_value(results, "quiet_hours_words") or quiet
    vid = payload.get("village_id") or dv.get("village_id") or village.default_village_id()
    member_id = dv.get("member_id") or village.care_recipient_id(vid)
    row: dict[str, Any] = {
        "conversation_id": payload.get("conversation_id"),
        "village_id": vid,
        "member_id": member_id,
        "consent": _dc_value(results, "welcome_consent"),
        "preferred_name": _dc_value(results, "preferred_name"),
        "evening_checkin": _dc_value(results, "evening_checkin"),
        "quiet_hours": quiet,
        "words": words,
        "call_at": _call_iso(payload),
        "policy": None,
    }
    WELCOME_RESULTS.append(row)
    if not quiet:
        return row
    try:
        from core.builder.founding import confirm_quiet_hours

        if services is None:
            from core.builder.routes import services as builder_services

            services = builder_services()
        spec = await services.get_spec(vid)
        if spec and any(p.get("rule_id") == "P-QH-01" for p in spec.get("policies") or []):
            ref = f"welcome_call:{payload.get('conversation_id', '')}@{row['call_at']}"
            row["policy"] = confirm_quiet_hours(spec, member_id, quiet, words, _words_secs(payload, words), ref=ref)
            await services.store_spec(vid, spec, spec.get("status") or "draft")
    except Exception as exc:  # never fail the webhook over provenance
        row["error"] = type(exc).__name__
    return row


_SCREEN_STATUS = {"pass_through": "passed_through", "passed_through": "passed_through", "confirmed": "passed_through",
                  "refused": "refused", "held": "held", "ask_purpose": "hung_up", "message_taken": "message_taken"}


def log_screened_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Receptionist call (receptionist=on, unknown caller): one calls:screened row per call, even with no money claim."""
    dv = payload.get("dynamic_variables") or {}
    if dv.get("receptionist") != "on" or dv.get("caller_known") != "false":
        return None
    from core.voice import screened

    conv = str(payload.get("conversation_id") or "")
    vid = payload.get("village_id") or dv.get("village_id") or village.default_village_id()
    existing = screened.get(conv)
    if existing and existing.get("outcome") == "message_taken":
        return existing
    outcome = "hung_up"
    for key in (f"{conv}:screen:await", f"{conv}:screen"):  # Core's cached screen_caller answers (core.evolve.receptionist)
        resp = ((db.idem.get(key) or {}).get("response") or {})
        status = (resp.get("data") or {}).get("status")
        if status in _SCREEN_STATUS:
            outcome = _SCREEN_STATUS[status]
            break
    results = payload.get("data_collection_results") or {}
    claimed = _dc_value(results, "claimed_identity") or None
    return screened.record(vid, conv, outcome, at=_call_iso(payload), claimed=claimed)


async def _flush_captions(payload: dict[str, Any]) -> None:
    try:
        from core.voice import captions

        if not captions.enabled():
            return
        dv = payload.get("dynamic_variables") or {}
        names = {"user": dv.get("member_short_name") or dv.get("recipient_name") or "Caller", "agent": "Village"}
        await captions.emit_transcript(
            payload.get("village_id") or dv.get("village_id") or village.default_village_id(),
            str(payload.get("conversation_id") or ""),
            payload.get("transcript") or [],
            names=names,
            final=True,
        )
    except Exception:
        return


async def handle_payload(payload: dict[str, Any]) -> None:
    payload = normalize(payload)
    event_type = payload.get("type", payload.get("event", "post_call"))
    clean = clean_payload(payload)
    POST_CALLS.append(clean)

    if event_type == "call_initiation_failure":
        await record_call_failed(clean)
        return

    if event_type in {"post_call", "conversation_ended", "data_collection"}:
        await apply_verification_answer(clean)
        log_screened_call(payload)
        await apply_welcome(payload)  # her words, unredacted digits: "9" in "9 de la noche" is an hour, not an account
        if os.getenv("VILLAGE_CAPTIONS", "on").lower() != "off" and clean.get("transcript"):
            import asyncio

            asyncio.get_running_loop().create_task(_flush_captions(clean))
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

