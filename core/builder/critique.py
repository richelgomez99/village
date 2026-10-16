"""Plan → critique → commit (AGENT.md §4): one critique call before render — "for this person, what
would fail? what did we assume?" — and the diff is applied to the capability plan once."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from . import frames
from .capabilities import CapabilityPlan, Choice, catalog
from .spans import span

CRITIQUE_TOOL = {
    "name": "critique_plan",
    "description": "Second opinion on a per-person capability plan. Propose at most 3 changes.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["changes", "assumptions", "summary"],
        "properties": {
            "changes": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["member_id", "capability", "op", "reason"],
                    "properties": {
                        "member_id": {"type": "string"},
                        "capability": {"type": "string"},
                        "op": {"enum": ["add", "remove"]},
                        "reason": {"type": "string", "maxLength": 200},
                    },
                },
            },
            "assumptions": {"type": "array", "maxItems": 4, "items": {"type": "string", "maxLength": 200}},
            "summary": {"type": "string", "maxLength": 200},
        },
    },
}

SYSTEM = """You are the second opinion for Village's Founder. For EACH person in the plan ask: what would fail
for this person? what did we assume? Use only the capability ids given. Never add an app capability for someone
whose tech_comfort is phone; never add village_chat for the care recipient. Propose a change only if it fixes a
concrete failure; otherwise list the assumption. Call critique_plan once."""


@dataclass
class CritiqueResult:
    applied: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    summary: str = ""
    source: str = "rules"


def plan_text(plan: CapabilityPlan, people: list[dict[str, Any]]) -> str:
    rows = []
    for p in people:
        prof = p.get("profile", {})
        rows.append(
            {
                "member_id": p["id"],
                "name": p["name"],
                "role": p["role"],
                "profile": {k: prof.get(k) for k in ("lang", "memory", "tech_comfort", "quiet_hours", "availability") if prof.get(k)},
                "consent_ai_calls": p.get("consent", {}).get("ai_calls"),
                "notes": p.get("notes", "")[:160],
                "chosen": plan.for_member(p["id"]),
                "not_chosen": [{"capability": r.capability, "why": r.reason} for r in plan.rejected if r.member_id == p["id"]][:4],
            }
        )
    return json.dumps({"capabilities": list(catalog()["capabilities"]), "people": rows}, ensure_ascii=False)


def rules_critique(plan: CapabilityPlan, people: list[dict[str, Any]]) -> dict[str, Any]:
    """Model-off second opinion: deterministic checks that name concrete assumptions."""
    assumptions, changes = [], []
    for p in people:
        mine = plan.for_member(p["id"])
        first = p.get("short_name") or p["name"].split()[0]
        prof = p.get("profile", {})
        if "check_in_call" in mine and p.get("consent", {}).get("ai_calls") is not True:
            assumptions.append(f"{first} hasn't agreed to calls yet: the check-in starts only after she says yes on the welcome call.")
        if "check_in_call" in mine and prof.get("quiet_hours"):
            assumptions.append(f"{first}'s check-in must end before quiet hours ({prof['quiet_hours']}).")
        if prof.get("tech_comfort") == "phone":
            for app_cap in ("village_chat", "dashboard", "is_it_my_turn", "refill_day"):
                if app_cap in mine:
                    changes.append({"member_id": p["id"], "capability": app_cap, "op": "remove", "reason": f"{first} is phone-only"})
    return {"changes": changes, "assumptions": assumptions, "summary": f"second opinion: {len(changes)} changes, {len(assumptions)} assumptions"}


def apply_critique(plan: CapabilityPlan, people: list[dict[str, Any]], out: dict[str, Any]) -> CritiqueResult:
    ids = {p["id"]: p for p in people}
    caps = catalog()["capabilities"]
    res = CritiqueResult(assumptions=list(out.get("assumptions", []))[:4], summary=out.get("summary", ""))
    for ch in list(out.get("changes", []))[:3]:
        person = ids.get(ch.get("member_id"))
        cap = ch.get("capability")
        ok = person is not None and cap in caps
        if ok and ch["op"] == "add":
            tech = person.get("profile", {}).get("tech_comfort")
            fits = caps[cap].get("fits", {}).get("tech_comfort")
            if (fits and tech not in fits) or (cap == "village_chat" and person.get("role") == "care_recipient"):
                ok = False
        if not ok:
            res.refused.append(ch)
            continue
        if ch["op"] == "remove":
            before = len(plan.choices)
            plan.choices = [c for c in plan.choices if not (c.member_id == person["id"] and c.capability == cap)]
            (res.applied if len(plan.choices) < before else res.refused).append(ch)
        elif cap not in plan.for_member(person["id"]):
            plan.choices.append(Choice(person["id"], cap, 0, [f"second opinion: {ch['reason']}"], [], list(caps[cap].get("implements", []))))
            res.applied.append(ch)
    return res


async def critique(plan: CapabilityPlan, people: list[dict[str, Any]], *, village_id: str, services: Any, llm: Any | None = None, trace_id: str | None = None) -> CritiqueResult:
    with span("builder.critique", "EVALUATOR", **{"session.id": f"village-{village_id}", "graph.node.id": "critique", "graph.node.parent_id": "found"}) as sp:
        source = "rules"
        if llm is not None:
            try:
                out = await llm.tool_call(system=SYSTEM, messages=[{"role": "user", "content": plan_text(plan, people)}], tool=CRITIQUE_TOOL, max_tokens=1200)
                source = "model"
            except Exception as exc:  # critique is a quality lever, never a blocker
                out = rules_critique(plan, people)
                out["assumptions"] = (out["assumptions"] + [f"critique model failed: {type(exc).__name__}"])[:4]
        else:
            out = rules_critique(plan, people)
        res = apply_critique(plan, people, out)
        res.source = source
        sp.set("eval.name", "founder_critique")
        sp.set("eval.changes_applied", len(res.applied))
        sp.set("eval.changes_refused", len(res.refused))
        sp.set("output.value", json.dumps(out, ensure_ascii=False)[:2000])
    line = f"Second opinion: {len(res.applied)} change{'s' if len(res.applied) != 1 else ''}"
    if res.applied:
        line += " — " + "; ".join(f"{c['op']} {c['capability']} for {c['member_id']}: {c['reason']}" for c in res.applied)
    elif res.assumptions:
        line += " — checked: " + res.assumptions[0]
    await services.broadcast_control(village_id, frames.reasoning(village_id, line, "decision", trace_id))
    return res
