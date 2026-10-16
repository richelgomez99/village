"""Capabilities, not components (AGENT.md §4). Score each catalog capability per person; record
the choice and the reason as decision rows (mode acted_alone)."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from .decisions import builder_decision
from .paths import ROOT

CATALOG_PATH = ROOT / "core" / "agent" / "capabilities.yaml"
SUPPORT_ROLES = {"caregiver", "professional_caregiver", "coordinator"}


@lru_cache
def catalog() -> dict[str, Any]:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def list_capabilities() -> list[dict[str, Any]]:
    """Founder tool `capabilities.list`."""
    return [{"id": cid, **body} for cid, body in catalog()["capabilities"].items()]


@dataclass
class Choice:
    member_id: str
    capability: str
    score: int
    reasons: list[str]
    need_ids: list[str] = field(default_factory=list)
    implements: list[str] = field(default_factory=list)


@dataclass
class Rejection:
    member_id: str
    capability: str
    reason: str


@dataclass
class CapabilityPlan:
    choices: list[Choice]
    rejected: list[Rejection]

    def for_member(self, member_id: str) -> list[str]:
        return [c.capability for c in self.choices if c.member_id == member_id]

    def as_dict(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for c in self.choices:
            out.setdefault(c.member_id, []).append(c.capability)
        return out


def relevant_needs(person: dict[str, Any], needs: list[dict[str, Any]], center_id: str | None) -> list[dict[str, Any]]:
    out = []
    for need in needs:
        subjects = need.get("subject_member_ids") or []
        if not subjects or person["id"] in subjects:
            out.append(need)
        elif center_id and center_id in subjects and person.get("role") in SUPPORT_ROLES:
            out.append(need)
    return out


def _signals(blueprint: dict[str, Any], signals: dict[str, Any] | None) -> dict[str, Any]:
    out = {"money_attempts": sum(1 for n in blueprint.get("needs", []) if n.get("domain") == "money")}
    out.update(signals or {})
    return out


def score_person(person: dict[str, Any], blueprint: dict[str, Any], kind: str, center_id: str | None, signals: dict[str, Any]) -> tuple[list[Choice], list[Rejection]]:
    cat = catalog()
    role = person.get("role")
    tech = (person.get("profile") or {}).get("tech_comfort", "app")
    needs = relevant_needs(person, blueprint.get("needs", []), center_id)
    choices: list[Choice] = []
    rejected: list[Rejection] = []
    for cid, cap in cat["capabilities"].items():
        aw, fits = cap.get("applies_when", {}), cap.get("fits", {})
        if role not in aw.get("roles", [role]):
            continue  # not for this kind of person; not worth a rejection line
        if kind not in aw.get("kinds", [kind]):
            continue
        missing = [r for r in aw.get("requires", []) if not _requirement(r, signals)]
        if missing:
            rejected.append(Rejection(person["id"], cid, _requirement_reason(missing[0], signals)))
            continue
        domains = aw.get("need_domains")
        matched = [n for n in needs if not domains or n.get("domain") in domains] if domains else []
        if domains and not matched:
            rejected.append(Rejection(person["id"], cid, f"no {'/'.join(domains)} need for {person['name'].split()[0]}"))
            continue
        if "tech_comfort" in fits and tech not in fits["tech_comfort"]:
            rejected.append(Rejection(person["id"], cid, f"doesn't fit: tech_comfort {tech}, needs {'/'.join(fits['tech_comfort'])}"))
            continue
        score = int(cap.get("weight", 1)) + 2 * min(len(matched), 2) + int(cap.get("role_bonus", {}).get(role, 0))
        reasons = []
        if "tech_comfort" in fits:
            reasons.append(f"fits tech_comfort {tech}")
        if (person.get("profile") or {}).get("memory") in ("mild_lapses", "significant") and cid in ("fridge_card", "check_in_call"):
            reasons.append(f"memory {person['profile']['memory']}")
            score += 1
        for n in matched[:2]:
            reasons.append(f"need {n['id']}: {n.get('text', '')[:60]}")
        if role in cap.get("role_bonus", {}):
            reasons.append(f"{role} approves changes")
        if cid == "check_in_call" and (person.get("consent") or {}).get("ai_calls") is not True:
            reasons.append("asks consent first; she can decline")
        if score < cat["pick"]["min_score"]:
            rejected.append(Rejection(person["id"], cid, f"score {score} below {cat['pick']['min_score']}"))
            continue
        choices.append(Choice(person["id"], cid, score, reasons, [n["id"] for n in matched], list(cap.get("implements", []))))
    choices.sort(key=lambda c: -c.score)
    cap_n = cat["pick"]["max_per_person"]
    for extra in choices[cap_n:]:
        rejected.append(Rejection(person["id"], extra.capability, f"ranked below top {cap_n}"))
    return choices[:cap_n], rejected


def _requirement(req: str, signals: dict[str, Any]) -> bool:
    if req == "money_attempts_2":
        return int(signals.get("money_attempts", 0)) >= 2
    return bool(signals.get(req))


def _requirement_reason(req: str, signals: dict[str, Any]) -> str:
    if req == "money_attempts_2":
        n = int(signals.get("money_attempts", 0))
        return f"{n} money attempt so far; Village proposes this after a second" if n == 1 else f"{n} money attempts so far"
    return f"precondition {req} not met"


def plan_capabilities(spec_or_blueprint: dict[str, Any], *, kind: str | None = None, center_id: str | None = None, signals: dict[str, Any] | None = None) -> CapabilityPlan:
    blueprint = spec_or_blueprint.get("blueprint", spec_or_blueprint)
    village = spec_or_blueprint.get("village", {})
    kind = kind or village.get("kind") or blueprint.get("kind", "care")
    center_id = center_id or village.get("care_recipient_id") or next((p["id"] for p in blueprint.get("people", []) if p.get("role") == "care_recipient"), None)
    sig = _signals(blueprint, signals)
    choices: list[Choice] = []
    rejected: list[Rejection] = []
    for person in blueprint.get("people", []):
        c, r = score_person(person, blueprint, kind, center_id, sig)
        choices.extend(c)
        rejected.extend(r)
    return CapabilityPlan(choices, rejected)


def decision_rows(village_id: str, plan: CapabilityPlan, people: list[dict[str, Any]], trace_id: str | None = None) -> list[dict[str, Any]]:
    labels = {cid: body.get("label", cid) for cid, body in catalog()["capabilities"].items()}
    rows = []
    for person in people:
        mine = [c for c in plan.choices if c.member_id == person["id"]]
        first = person.get("short_name") or person["name"].split()[0]
        if not mine:
            text = f"{first}: no capability scored high enough; gets the default for their view."
            need_ids: list[str] = []
        else:
            picks = " + ".join(labels[c.capability].lower() for c in mine)
            why = "; ".join(dict.fromkeys(r for c in mine for r in c.reasons[:2]))
            text = f"{first}: {picks}. Why: {why}."
            need_ids = list(dict.fromkeys(n for c in mine for n in c.need_ids))
        notpicked = [r for r in plan.rejected if r.member_id == person["id"] and r.capability in ("receptionist_line", "phone_line", "dashboard")]
        if notpicked:
            text += f" Not {labels[notpicked[0].capability].lower()}: {notpicked[0].reason}."
        refs = [{"kind": "member", "id": person["id"], "label": first}] + [{"kind": "need", "id": n} for n in need_ids[:4]]
        rows.append(builder_decision(village_id, text, refs=refs, mode="acted_alone", trace_id=trace_id))
    return rows
