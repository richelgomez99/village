"""Builder patch (V4 consumer): `patch_app` → RFC 6902 ops on one role's view → apply to a copy →
validate the whole spec → one repair → otherwise no change. Spec rev rules: invariant 6."""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any

from .mapping import ensure_chat
from .paths import PROMPTS
from .render import system_prompt
from .tools import all_tools
from .validate import validate_spec

DOMAIN_AREA = {"medication": "health", "health_observation": "health", "money": "money", "safety": "health", "scheduling": "people", "social": "people", "information": "information", "resources": "home", "logistics": "daily_living"}
REFUSE_RE = re.compile(r"send money|wire|gift card|crypto|bank account|dos(e|is|age)\b|double (the )?dose|share the family word", re.I)


class PatchError(ValueError):
    pass


@dataclass
class PatchResult:
    ops: list[dict[str, Any]]
    needs_added: list[dict[str, Any]] = field(default_factory=list)
    needs_served: dict[str, list[str]] = field(default_factory=dict)
    reason: str = ""
    plan: str = ""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    status: str = "valid"  # valid | repaired | invalid | refused | noop
    attempts: int = 0
    spec: dict[str, Any] | None = None


# ---- RFC 6902 ---------------------------------------------------------------------------------
def _tokens(path: str) -> list[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise PatchError(f"bad pointer {path}")
    return [t.replace("~1", "/").replace("~0", "~") for t in path[1:].split("/")]


def _parent(doc: Any, path: str) -> tuple[Any, str]:
    toks = _tokens(path)
    if not toks:
        raise PatchError("cannot target the root")
    cur = doc
    for t in toks[:-1]:
        cur = cur[int(t)] if isinstance(cur, list) else cur[t]
    return cur, toks[-1]


def _get(doc: Any, path: str) -> Any:
    cur = doc
    for t in _tokens(path):
        cur = cur[int(t)] if isinstance(cur, list) else cur[t]
    return cur


def _add(doc: Any, path: str, value: Any) -> None:
    parent, key = _parent(doc, path)
    if isinstance(parent, list):
        idx = len(parent) if key == "-" else int(key)
        if idx > len(parent):
            raise PatchError(f"index {idx} out of range at {path}")
        parent.insert(idx, value)
    else:
        parent[key] = value


def _remove(doc: Any, path: str) -> Any:
    parent, key = _parent(doc, path)
    if isinstance(parent, list):
        return parent.pop(int(key))
    if key not in parent:
        raise PatchError(f"remove: {path} missing")
    return parent.pop(key)


def apply_ops(doc: Any, ops: list[dict[str, Any]]) -> Any:
    """Apply RFC 6902 ops to a deep copy; raises PatchError (the original is untouched)."""
    out = copy.deepcopy(doc)
    try:
        for op in ops:
            kind, path = op["op"], op["path"]
            if kind == "add":
                _add(out, path, copy.deepcopy(op["value"]))
            elif kind == "remove":
                _remove(out, path)
            elif kind == "replace":
                _get(out, path)
                parent, key = _parent(out, path)
                parent[int(key) if isinstance(parent, list) else key] = copy.deepcopy(op["value"])
            elif kind == "move":
                _add(out, path, _remove(out, op["from"]))
            elif kind == "copy":
                _add(out, path, copy.deepcopy(_get(out, op["from"])))
            elif kind == "test":
                if _get(out, path) != op["value"]:
                    raise PatchError(f"test failed at {path}")
            else:
                raise PatchError(f"unknown op {kind}")
    except PatchError:
        raise
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise PatchError(f"{type(exc).__name__} applying {op}") from exc
    return out


# ---- builder patch ----------------------------------------------------------------------------
def apply_to_copy(spec: dict[str, Any], role: str, out: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    cand = copy.deepcopy(spec)
    try:
        cand["views"][role] = apply_ops(cand["views"][role], out.get("ops", []))
    except PatchError as exc:
        return None, [str(exc)]
    view = cand["views"][role]
    view.setdefault("needs_served", {}).update({k: v for k, v in (out.get("needs_served") or {}).items() if k in view["elements"]})
    for eid in list(view["needs_served"]):
        if eid not in view["elements"]:
            view["needs_served"].pop(eid)
    bp = cand["blueprint"]
    known = {n["id"] for n in bp["needs"]}
    for n in out.get("needs_added", []) or []:
        if n["id"] in known:
            continue
        area = DOMAIN_AREA.get(n.get("domain", ""), bp["life_areas"][0]["id"])
        target = next((a for a in bp["life_areas"] if a["id"] == area), bp["life_areas"][0])
        bp["needs"].append({"id": n["id"], "text": n.get("statement", n.get("text", ""))[:160], "priority": n.get("priority", 3), "domain": n.get("domain", "safety"), "life_area": target["id"], "subject_member_ids": n.get("subject_member_ids", []), "source_span": None, "origin": "evolve"})
        target["need_ids"].append(n["id"])
    cand = ensure_chat(cand)
    report = validate_spec(cand)
    return (cand if report.ok else None), report.errors


def rules_patch(spec: dict[str, Any], role: str, instruction: str) -> dict[str, Any]:
    view = spec["views"][role]
    if re.search(r"receptionist|unknown caller", instruction, re.I) and "receptionist" not in view["elements"]:
        return {
            "role": role,
            "plan": "unknown callers → receptionist on her line → info card for the family",
            "reason": "Village answers unknown callers first and checks with the real person before the call reaches her.",
            "ops": [
                {"op": "add", "path": "/elements/receptionist", "value": {"type": "Text", "props": {"text": "Village answers unknown calls first.", "size": "l", "tone": "info"}}},
                {"op": "add", "path": "/elements/s/children/1", "value": "receptionist"},
            ],
            "needs_served": {},
        }
    return {"role": role, "plan": "no-op", "reason": "No view change needed.", "ops": [], "needs_served": {}}


async def patch(spec: dict[str, Any], role: str, instruction: str, *, llm: Any | None = None, current_view: dict[str, Any] | None = None) -> PatchResult:
    if REFUSE_RE.search(instruction):
        return PatchResult(ops=[], reason="That change would break a safety rule (money never moves; no dose advice; family word stays private).", plan="refused", status="refused")
    base = copy.deepcopy(spec)
    if current_view is not None:
        base["views"][role] = copy.deepcopy(current_view)
    tool = all_tools()["patch_app"]
    user = json.dumps({"mode": "patch", "role": role, "current_view": base["views"][role], "needs": [{"id": n["id"], "text": n["text"]} for n in base["blueprint"]["needs"]], "members": [{"id": p["id"], "name": p["name"]} for p in base["blueprint"]["people"]], "instruction": instruction}, ensure_ascii=False)
    attempts = 0
    out: dict[str, Any] = {}
    errors: list[str] = []
    for attempt in range(2):
        attempts += 1
        if llm is None:
            if attempt:
                break
            out = rules_patch(base, role, instruction)
        else:
            msg = user if not attempt else user + "\n\nYour previous patch_app input:\n" + json.dumps(out, ensure_ascii=False)[:8000] + "\nIt failed:\n" + "\n".join(errors[:10]) + "\nFix it and call patch_app again."
            out = await llm.tool_call(system=system_prompt(), messages=[{"role": "user", "content": msg}], tool=tool, max_tokens=3000)
        if not out.get("ops"):
            return PatchResult(ops=[], reason=out.get("reason", ""), plan=out.get("plan", ""), status="noop", attempts=attempts, spec=base)
        cand, errors = apply_to_copy(base, role, out)
        if cand is not None:
            return PatchResult(ops=out["ops"], needs_added=out.get("needs_added", []), needs_served=out.get("needs_served", {}), reason=out.get("reason", ""), plan=out.get("plan", ""), status="valid" if attempt == 0 else "repaired", attempts=attempts, spec=cand)
    return PatchResult(ops=out.get("ops", []), reason=out.get("reason", ""), plan=out.get("plan", ""), valid=False, errors=errors, status="invalid", attempts=attempts)


def prompt_examples() -> dict[int, dict[str, Any]]:
    """Examples 4–6 of prompts/builder_system.md (patch mode)."""
    text = (PROMPTS / "builder_system.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"### Example (\d) .*?```json\n(.*?)\n```", text, re.S):
        n = int(m.group(1))
        if n >= 4:
            out[n] = json.loads(m.group(2))
    return out


def validate_patch_on_copy(village: dict[str, Any], role: str, ops: list[dict[str, Any]]) -> PatchResult:
    cand, errors = apply_to_copy(village, role, {"ops": ops})
    return PatchResult(ops=ops, valid=cand is not None, errors=errors, status="valid" if cand is not None else "invalid", spec=cand)
