from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .validate import validate_spec


@dataclass
class PatchResult:
    ops: list[dict[str, Any]]
    needs_added: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    plan: str = ""
    valid: bool = True
    errors: list[str] = field(default_factory=list)


async def patch(village: dict[str, Any], role: str, instruction: str, current_view: dict[str, Any] | None = None) -> PatchResult:
    if any(word in instruction.lower() for word in ("send money", "gift card", "dose", "dosage")):
        return PatchResult(ops=[], reason="The requested change would break a safety rule.", plan="safety request refused", valid=True)
    view = copy.deepcopy(current_view or village["views"][role])
    if "receptionist" in instruction.lower() or "unknown caller" in instruction.lower():
        eid = "receptionist"
        if eid not in view["elements"]:
            ops = [
                {"op": "add", "path": f"/elements/{eid}", "value": {"type": "Text", "props": {"text": "Village answers unknown calls first.", "size": "l", "tone": "info"}}},
                {"op": "add", "path": "/elements/s/children/-", "value": eid},
            ]
            return PatchResult(ops=ops, reason="Adds the approved receptionist explanation.", plan="unknown callers -> receptionist card")
    return PatchResult(ops=[], reason="No view change needed.", plan="no-op")


def validate_patch_on_copy(village: dict[str, Any], role: str, ops: list[dict[str, Any]]) -> PatchResult:
    candidate = copy.deepcopy(village)
    view = candidate["views"][role]
    try:
        for op in ops:
            _apply_view_op(view, op)
    except Exception as exc:
        return PatchResult(ops=ops, valid=False, errors=[str(exc)])
    report = validate_spec(candidate)
    return PatchResult(ops=ops, valid=report.ok, errors=report.errors)


def _apply_view_op(view: dict[str, Any], op: dict[str, Any]) -> None:
    parts = op["path"].strip("/").split("/")
    if parts[:1] != ["elements"]:
        raise ValueError(f"unsupported patch path {op['path']}")
    if len(parts) == 2:
        if op["op"] in {"add", "replace"}:
            view["elements"][parts[1]] = op["value"]
        elif op["op"] == "remove":
            view["elements"].pop(parts[1], None)
        return
    element = view["elements"][parts[1]]
    if parts[2] == "children":
        children = element.setdefault("children", [])
        if op["op"] == "add":
            if len(parts) == 3 or parts[3] == "-":
                children.append(op["value"])
            else:
                children.insert(int(parts[3]), op["value"])
        elif op["op"] == "remove":
            children.pop(int(parts[3]))
        return
    if parts[2] == "props":
        if len(parts) == 3:
            element["props"] = op["value"]
        elif op["op"] in {"add", "replace"}:
            element["props"][parts[3]] = op["value"]
        elif op["op"] == "remove":
            element["props"].pop(parts[3], None)
        return
    raise ValueError(f"unsupported patch path {op['path']}")
