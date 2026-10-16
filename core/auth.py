"""Demo token resolution. Accepted member tokens: the member id (`m_marco`), a minted token
`mt_<firstname>_<anything>` (QR / fixture form, e.g. mt_marco_9Qe2vLx7Rk3pZ0aB), or the
control token (`control`, or CONTROL_TOKEN from the environment)."""
from __future__ import annotations

import os
import unicodedata

from core.db import db


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def resolve_token(token: str | None) -> str | None:
    """Return a member id, 'control', or None for an unknown token."""
    if not token:
        return None
    token = token.removeprefix("Bearer ").strip()
    control = os.getenv("CONTROL_TOKEN")
    if token == "control" or (control and token == control):
        return "control"
    if token in db.members:
        return token
    if token.startswith("mt_"):
        first = token.split("_")[1] if token.count("_") >= 1 else ""
        for member_id, person in db.members.items():
            if member_id == f"m_{first}" or _ascii(str(person.get("name", "")).split()[0]) == first:
                return member_id
    return None


def role_of(member_id: str | None) -> str:
    if member_id == "control":
        return "control"
    person = db.members.get(member_id or "")
    return person.get("view", "elder") if person else "elder"


def first_name(member_id: str | None) -> str:
    person = db.members.get(member_id or "", {})
    return str(person.get("name", member_id or "")).split()[0]
