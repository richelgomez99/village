"""Contract-shaped models for the pure gate.

These are intentionally thin wrappers over dictionaries.  Gate input and output
must round-trip against ``contracts/schemas/gate.schema.json`` without hidden
state, mutation, network calls, clocks, or database handles.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, TypeAlias

JsonObject: TypeAlias = dict[str, Any]
VillageState: TypeAlias = JsonObject
Candidate: TypeAlias = JsonObject
Decision: TypeAlias = JsonObject
Verification: TypeAlias = JsonObject
DoseWindow: TypeAlias = JsonObject


@dataclass(frozen=True)
class GateInput:
    village_state: VillageState
    event: Candidate
    alloc: JsonObject
    idempotency_key: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateInput":
        missing = {"village_state", "event", "alloc"} - set(value)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"GateInput missing required field(s): {names}")
        return cls(
            village_state=deepcopy(dict(value["village_state"])),
            event=deepcopy(dict(value["event"])),
            alloc=deepcopy(dict(value["alloc"])),
            idempotency_key=value.get("idempotency_key"),
        )

    def to_dict(self) -> JsonObject:
        value: JsonObject = {
            "village_state": deepcopy(self.village_state),
            "event": deepcopy(self.event),
            "alloc": deepcopy(self.alloc),
        }
        if self.idempotency_key is not None:
            value["idempotency_key"] = self.idempotency_key
        return value


def gate_input_from_args(*args: Any, **kwargs: Any) -> GateInput:
    """Accept both contract and Core convenience call forms.

    Supported:
    - ``decide(gate_input_dict)``
    - ``decide(GateInput(...))``
    - ``decide(state, event, alloc, now=None)``
    """

    if len(args) == 1 and isinstance(args[0], GateInput):
        return args[0]
    if len(args) == 1 and isinstance(args[0], Mapping):
        return GateInput.from_mapping(args[0])
    if len(args) in {3, 4}:
        state = deepcopy(dict(args[0]))
        event = deepcopy(dict(args[1]))
        alloc = deepcopy(dict(args[2]))
        now = args[3] if len(args) == 4 else kwargs.get("now")
        if now is not None:
            state["now"] = str(now)
            event.setdefault("at", str(now))
        return GateInput(state, event, alloc, kwargs.get("idempotency_key"))
    raise TypeError("expected GateInput, mapping, or state/event/alloc[/now]")


def member_by_id(state: VillageState, member_id: str | None) -> JsonObject | None:
    if member_id is None:
        return None
    for member in state.get("members", []):
        if member.get("id") == member_id:
            return member
    return None


def member_name(state: VillageState, member_id: str | None, fallback: str = "la familia") -> str:
    member = member_by_id(state, member_id)
    return str(member.get("name") or fallback) if member else fallback


def copy_payload(event: Candidate) -> JsonObject:
    return deepcopy(dict(event.get("payload", {})))


def decision_base(inp: GateInput, rule_id: str, decision: str) -> Decision:
    return {
        "id": inp.alloc["decision_id"],
        "rule_id": rule_id,
        "decision": decision,
        "say": {"es": "", "en": ""},
        "notify": [],
        "writes": [],
        "rules_fired": [rule_id],
    }


def append_rule(decision: Decision, rule_id: str) -> None:
    rules = decision.setdefault("rules_fired", [])
    if rule_id not in rules:
        rules.append(rule_id)


def as_decision(value: MutableMapping[str, Any]) -> Decision:
    return deepcopy(dict(value))
