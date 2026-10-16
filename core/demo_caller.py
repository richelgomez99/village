"""Stage switch for the presenter's single phone (in-memory; reset -> "elder").

elder   (default) the presenter's number (DEMO_ELDER_CALLER_ID / the care recipient's phone) is the care recipient
unknown           the same number is treated as an unknown caller (receptionist beat: the presenter plays the scammer)"""
from __future__ import annotations

ROLES = ("elder", "unknown")
_STATE = {"role": "elder"}


def role() -> str:
    return _STATE["role"]


def set_role(value: str) -> str:
    if value not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    _STATE["role"] = value
    return value


def reset() -> None:
    _STATE["role"] = "elder"
