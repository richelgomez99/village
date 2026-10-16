"""Shared-secret check for ElevenLabs -> Core calls (tool webhooks + init webhook).

The agents send `X-Village-Secret` from the ElevenLabs workspace secret `VILLAGE_TOOL_SECRET`.
Core enforces it only when the same value is set in its env (`VILLAGE_TOOL_SECRET`, legacy `VILLAGE_SECRET`),
so a Core without the secret keeps answering (dev, tests, the live demo before the env is synced).
"""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException


def expected_secret() -> str:
    return os.getenv("VILLAGE_TOOL_SECRET") or os.getenv("VILLAGE_SECRET") or ""


def require_secret(received: str | None) -> None:
    expected = expected_secret()
    if expected and not hmac.compare_digest(expected, received or ""):
        raise HTTPException(status_code=401, detail="bad voice secret")
