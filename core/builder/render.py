"""Per-role views in parallel (D9 speed 2): `render_app` per role via asyncio.gather (45 s per role,
60 s total), validate (pydantic mirror + invariants), one repair, template fallback, status frames."""
from __future__ import annotations

import asyncio
import json
import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from . import frames, templates
from .capabilities import CapabilityPlan, catalog
from .mapping import ensure_chat
from .prompts import get_builder_prompt
from .spans import span
from .tools import all_tools
from .validate import validate_spec

PER_ROLE_S = 45.0
TOTAL_S = 60.0

ADDENDUM = """
CONTRACT 1.2.0 ADDENDUM (overrides anything above where they differ)
- Roles are view keys: care villages elder / coordinator / helper; blocks coordinator / resident / volunteer.
- The user message carries "reference_view": a valid view for this role. Use only component types and prop names
  that appear in reference_view or the catalog above. Keep element ids lowercase.
- needs_served may cite ONLY ids listed in village.needs, or n_safety.
- Do not add VillageChat: Core inserts it into every non-elder view. Never put VillageChat in an elder view.
- Elder views (D22): TonightCard + exactly 3 BigButtons (call Village · call the coordinator · I need help, in her language) + a 911
  ContactCard; no medication names; confirm on danger buttons.
- "capabilities" lists what the Founder chose for each person and the components each one implements: build the
  view from those.
"""


@dataclass
class RoleResult:
    status: str  # validated | repaired | template
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    ms: int = 0
    reason: str = ""
    plan: str = ""


_SYSTEM_CACHE: str | None = None


def system_prompt() -> str:
    global _SYSTEM_CACHE
    if _SYSTEM_CACHE is None:
        text = get_builder_prompt("local").text
        m = re.search(r"## SYSTEM PROMPT\s*```\n(.*?)\n```", text, re.S)
        _SYSTEM_CACHE = (m.group(1) if m else text) + ADDENDUM
    return _SYSTEM_CACHE


def role_input(spec: dict[str, Any], role: str, plan: CapabilityPlan | None, primary: bool) -> dict[str, Any]:
    people = spec["blueprint"]["people"]
    members = [p for p in people if p.get("view") == role]
    caps = catalog()["capabilities"]
    return {
        "mode": "render",
        "role": role,
        "primary": False,  # village-level fields come from the blueprint step + template (D9/D10)
        "members_in_role": [p["id"] for p in members],
        "village": {
            "description": spec["blueprint"]["description"]["text"],
            "kind": spec["village"]["kind"],
            "members": [{"id": p["id"], "name": p["name"], "role": p["role"], "lang": p["profile"].get("lang"), "profile": {k: p["profile"].get(k) for k in ("memory", "tech_comfort", "reading_level", "vision") if p["profile"].get(k)}} for p in people],
            "needs": [{"id": n["id"], "text": n["text"], "domain": n["domain"], "priority": n["priority"]} for n in spec["blueprint"]["needs"]],
        },
        "capabilities": {p["id"]: [{"id": c, "implements": caps[c].get("implements", [])} for c in (plan.for_member(p["id"]) if plan else [])] for p in members},
        "reference_view": templates.strip_chat(spec["views"][role]),
    }


def _candidate(spec: dict[str, Any], role: str, out: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    view = deepcopy(out.get("view") or {})
    if not isinstance(view, dict) or "elements" not in view:
        return spec, ["render_app output has no view.elements"]
    elements = view.get("elements", {})
    served = out.get("needs_served") or view.get("needs_served") or {}
    view["needs_served"] = {k: v for k, v in served.items() if k in elements}
    view.setdefault("root", "s")
    view.setdefault("lang", spec["views"][role].get("lang", "en"))
    cand = deepcopy(spec)
    cand["views"][role] = view
    cand = ensure_chat(cand)
    report = validate_spec(cand)
    return cand, ([] if report.ok else report.errors)


async def render_role(spec: dict[str, Any], role: str, *, llm: Any, plan: CapabilityPlan | None, primary: bool, timeout_s: float) -> tuple[dict[str, Any] | None, RoleResult]:
    t0 = time.perf_counter()
    tool = all_tools()["render_app"]
    user = json.dumps(role_input(spec, role, plan, primary), ensure_ascii=False)
    res = RoleResult(status="template")

    async def attempt() -> dict[str, Any] | None:
        messages = [{"role": "user", "content": user}]
        res.attempts = 1
        out = await llm.tool_call(system=system_prompt(), messages=messages, tool=tool, max_tokens=6000)
        res.plan = str(out.get("plan", ""))[:280]
        cand, errors = _candidate(spec, role, out)
        if not errors:
            res.status = "validated"
            return cand["views"][role]
        res.errors = errors
        res.attempts = 2
        repair_msg = user + "\n\nYour previous render_app input:\n" + json.dumps(out, ensure_ascii=False)[:12000] + "\n\nIt failed validation:\n" + "\n".join(errors[:12]) + "\nFix every error and call render_app again with the complete output."
        out2 = await llm.tool_call(system=system_prompt(), messages=[{"role": "user", "content": repair_msg}], tool=tool, max_tokens=6000)
        cand2, errors2 = _candidate(spec, role, out2)
        if not errors2:
            res.status = "repaired"
            res.plan = str(out2.get("plan", res.plan))[:280]
            return cand2["views"][role]
        res.errors = errors2
        res.reason = f"invalid after repair: {errors2[0][:120]}"
        return None

    try:
        view = await asyncio.wait_for(attempt(), timeout=max(0.01, timeout_s))
    except asyncio.TimeoutError:
        view, res.reason = None, f"timeout after {timeout_s:.0f} s"
    except Exception as exc:
        view, res.reason = None, f"{type(exc).__name__}: {str(exc)[:120]}"
    if view is None:
        res.status = "template"
    res.ms = int((time.perf_counter() - t0) * 1000)
    return view, res


async def render_views(
    spec: dict[str, Any],
    *,
    village_id: str,
    services: Any,
    llm: Any | None,
    plan: CapabilityPlan | None = None,
    per_role_s: float = PER_ROLE_S,
    total_s: float = TOTAL_S,
    trace_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, RoleResult]]:
    """`spec` is the template-based draft; returns it with rendered views swapped in where valid."""
    roles = list(spec["views"])
    results: dict[str, RoleResult] = {}
    out = deepcopy(spec)
    if llm is None:
        for role in roles:
            results[role] = RoleResult(status="template", reason="model off")
            await services.record_decision(templates.template_decision(village_id, role, "model off"))
            await services.broadcast_control(village_id, frames.reasoning(village_id, f"{role} view: template (model off)", "note", trace_id))
        return out, results
    deadline = time.perf_counter() + total_s
    primary = spec["village"].get("kind") == "block" and "coordinator" or "coordinator"
    for role in roles:
        await services.broadcast_control(village_id, frames.reasoning(village_id, f"{role} view: rendering", "note", trace_id))

    async def one(role: str) -> tuple[str, dict[str, Any] | None, RoleResult]:
        with span("builder.render_app", "LLM", **{"session.id": f"village-{village_id}", "graph.node.id": f"render_{role}", "graph.node.parent_id": "found", "role": role}) as sp:
            view, res = await render_role(spec, role, llm=llm, plan=plan, primary=role == primary, timeout_s=min(per_role_s, deadline - time.perf_counter()))
            sp.set("status", res.status)
            sp.set("ms", res.ms)
        return role, view, res

    done = await asyncio.gather(*(one(r) for r in roles))
    for role, view, res in done:
        if view is not None:
            out["views"][role] = view
        results[role] = res
    # whole-spec check: a view valid alone can still clash; fall back role by role
    report = validate_spec(out)
    for role in roles:
        if report.ok:
            break
        if results[role].status != "template" and any(f"views/{role}" in e or f" {role}" in e for e in report.errors):
            out["views"][role] = deepcopy(spec["views"][role])
            results[role].status, results[role].reason = "template", f"merge conflict: {report.errors[0][:120]}"
            report = validate_spec(out)
    if not report.ok:  # last resort: every view from the template
        for role in roles:
            out["views"][role] = deepcopy(spec["views"][role])
            if results[role].status != "template":
                results[role].status, results[role].reason = "template", "merge failed"
    for role in roles:
        r = results[role]
        if r.status == "template":
            await services.record_decision(templates.template_decision(village_id, role, r.reason or "fallback"))
            text = f"{role} view: template ({r.reason})"
        else:
            text = f"{role} view: {r.status} in {r.ms / 1000:.1f} s" + (f" — {r.plan}" if r.plan else "")
            if r.plan:
                from .decisions import builder_decision

                await services.record_decision(builder_decision(village_id, r.plan, kind="plan", trace_id=trace_id))
        await services.broadcast_control(village_id, frames.reasoning(village_id, text, "note", trace_id))
    return out, results
