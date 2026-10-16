"""Pure policy gate for Village.

The public functions in this package are deliberately dict-shaped because Core
loads and persists contract JSON.  The gate never performs I/O.
"""

from core.gate.models import (
    Candidate,
    Decision,
    DoseWindow,
    GateInput,
    Verification,
    VillageState,
    gate_input_from_args,
)
from core.gate.say import Say, say

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
]
