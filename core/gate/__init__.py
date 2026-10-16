"""Pure policy gate for Village."""

from __future__ import annotations

from core.gate.models import (
    Candidate,
    Decision,
    DoseWindow,
    GateInput,
    Verification,
    VillageState,
    gate_input_from_args,
)
from core.gate.rules.safety import decide_safety
from core.gate.say import Say, say
from core.gate.sm_dose_window import FakeClock, step_dose_window
from core.gate.sm_verification import step_verification

__all__ = [
    "Candidate",
    "Decision",
    "DoseWindow",
    "GateInput",
    "Verification",
    "VillageState",
    "gate_input_from_args",
    "Say",
    "say",
    "decide",
    "FakeClock",
    "step_dose_window",
    "step_verification",
]


def decide(*args, **kwargs) -> Decision:
    """Return a contract-shaped Decision without performing I/O."""

    inp = gate_input_from_args(*args, **kwargs)
    return decide_safety(inp)
