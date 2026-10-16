"""Outbound-call seam for verifications (T017).

`get_dialer()` returns the dialer Core uses to call the claimed member:
- tests / acceptance: `FakeDialer` (VILLAGE_DIALER=fake, or `set_dialer()`),
- live: `core.voice.outbound.ElevenLabsDialer` when that module imports and the ElevenLabs
  key, caller agent id and phone number id are configured (VILLAGE_DIALER=real or unset).
Placing a call goes through `core.voice.outbound.OutboundService`, which CAS-sets
`call_placed_at` first, so a row with `call_placed_at` is never dialed again (restart-safe).
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

from core.db import db
from core.settings import ROOT

_override: Any | None = None
_tasks: set[asyncio.Task[Any]] = set()
REAL_KEYS = ("ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_CALLER_ID", "ELEVENLABS_PHONE_NUMBER_ID")


@dataclass
class FakeDialer:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def outbound_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        n = len(self.calls)
        return {"success": True, "conversation_id": f"conv_out_fake_{n}", "callSid": f"CA_fake_{n}"}

    async def cancel(self, call_sid: str) -> bool:
        self.calls.append({"cancel": call_sid})
        return True


_fake = FakeDialer()


def set_dialer(dialer: Any | None) -> None:
    global _override
    _override = dialer


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        from dotenv import dotenv_values

        values.update({k: v for k, v in dotenv_values(ROOT / ".env").items() if v})
    except Exception:
        pass
    values.update({k: v for k, v in os.environ.items() if v})
    return values


def mode() -> str:
    if _override is not None:
        return "override"
    env = _env()
    wanted = env.get("VILLAGE_DIALER", "real").lower()
    if wanted in {"fake", "off"}:
        return wanted
    if all(env.get(k) for k in REAL_KEYS):
        try:
            import core.voice.outbound  # noqa: F401
        except Exception:
            return "fake"
        return "real"
    return "fake"


def get_dialer() -> Any | None:
    if _override is not None:
        return _override
    m = mode()
    if m == "off":
        return None
    if m == "real":
        from core.voice.outbound import ElevenLabsDialer

        env = _env()
        for key in ("ELEVENLABS_AGENT_CALLER_ID", "ELEVENLABS_PHONE_NUMBER_ID"):
            os.environ.setdefault(key, env[key])
        return ElevenLabsDialer(api_key=env["ELEVENLABS_API_KEY"])
    return _fake


def _consent_ai_calls(member_id: str) -> bool:
    person = db.members.get(member_id, {})
    return bool(person.get("consent", {}).get("ai_calls") is True)


async def dial_verification(verification_id: str) -> dict[str, Any]:
    """Call the claimed member for a pending verification. Never redials when call_placed_at is set."""
    row = db.verifications.get(verification_id)
    if row is None:
        return {"placed": False, "status": "unknown_verification"}
    if row.get("state") != "pending":
        return {"placed": False, "status": "terminal"}
    if row.get("call_placed_at"):
        return {"placed": False, "status": "already_placed"}
    channels = [c.get("via") if isinstance(c, dict) else c for c in row.get("channels", [])]
    if "outbound_call" not in channels:
        return {"placed": False, "status": "no_call_channel"}
    member_id = row.get("claimed_member_id", "")
    if not _consent_ai_calls(member_id):
        return {"placed": False, "status": "skipped_no_consent"}
    dialer = get_dialer()
    if dialer is None:
        return {"placed": False, "status": "dialer_off"}
    try:
        import core.voice.outbound as outbound
        from core.voice.outbound import OutboundRequest, OutboundService
    except Exception:
        return {"placed": False, "status": "no_outbound_module"}
    if getattr(outbound.member, "__name__", "") != "_live_member":
        file_member = outbound.member

        def _live_member(mid: str):
            # prefer the live member row: /auth/redeem may have set the judge's phone + consent (D11)
            return db.members.get(mid) or file_member(mid)

        outbound.member = _live_member
    from core import services

    name = str(db.members.get(member_id, {}).get("name", member_id)).split()[0]
    village = row.get("village", "v_reyes")
    try:
        await services.ledger(village, f"dial:{verification_id}", "running", f"Calling {name} to verify", role="Verifier")
        result = await OutboundService(dialer).place(OutboundRequest(member_id=member_id, verification_id=verification_id))
    except Exception as exc:  # a failed dial must never break the money flow; the deadline still closes the row
        result = {"placed": False, "status": "dial_failed", "error": type(exc).__name__}
    status = "done" if result.get("placed") else ("fallback" if result.get("status") == "dial_failed" else "refused")
    await services.ledger(village, f"dial:{verification_id}", status, f"Calling {name} to verify", result=str(result.get("status")), role="Verifier")
    return result


def dial_in_background(verification_id: str) -> None:
    task = asyncio.get_running_loop().create_task(dial_verification(verification_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Test helper: wait for background dials."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
