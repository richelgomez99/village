"""Founder (AGENT.md §2, docs/FOUNDING-INTAKE.md D29): listening → clarify (intake turns) → working →
draft → review. After every answer: record_answer → coverage meter → side effects (DailyMed per med,
the helper's consent call, the rota coverage check) → next highest-risk question. Then capabilities
per person, a second opinion, parallel renders, and the review turn (word edits → patch)."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from . import frames, templates
from .blueprint import heuristic_blueprint, stream_blueprint
from .capabilities import decision_rows as capability_rows
from .capabilities import plan_capabilities
from .conversation import DAYS, IntakeState, Question, Review, load_intake, med_names, merge, next_question, now_i_know, record_answer
from .critique import critique
from .dailymed import fixture_transport, lookup_medication
from .decisions import builder_decision
from .dialer import ScriptedConsentDialer, consent_call_payload, default_dialer, demo_script
from .llm_port import get_llm
from .mapping import ensure_chat
from .progressive import DraftBuilder
from .registry import kind_config, record as kind_record
from .render import RoleResult, render_views
from .services_stub import MemoryServices
from .spans import span
from .validate import validate_spec

STATES = ["listening", "clarify", "working", "draft", "review"]
DAILYMED_FIXTURES = Path(__file__).parent / "tests" / "data" / "dailymed"


@dataclass
class FoundingInput:
    description: str
    language: str = "en"
    channel: str = "text"
    members: list[dict[str, Any]] = field(default_factory=list)
    needs: list[dict[str, Any]] = field(default_factory=list)
    kind: str | None = None
    medications: list[str] | None = None
    answers: list[str] = field(default_factory=list)


@dataclass
class FoundingOptions:
    mode: str = "full"  # full | fixture (fixture = no model; side effects still real)
    llm: str | None = None  # off | on | None (env)
    clarify_wait_s: float = 0.0  # per turn: wait for POST /answers, then proceed with what we have
    per_role_s: float = 45.0
    total_s: float = 60.0
    dialer: Any | None = None
    dailymed: str = "live"  # live | fixture | off
    demo_record: bool = True
    signals: dict[str, Any] = field(default_factory=dict)
    llm_client: Any | None = None
    replay: list[Any] | None = None  # recorded answers: rows {text, topic, asked} (A1…A12) or plain strings in order
    replay_delay_s: float = 0.0
    resume: int | None = None  # replay answers until the meter reaches N, then live answers
    review: bool = True


@dataclass
class BuilderRun:
    village_id: str
    trace_id: str
    state: str = "listening"
    states: list[str] = field(default_factory=list)
    mode: str = "full"
    spec: dict[str, Any] | None = None
    roles: dict[str, RoleResult] = field(default_factory=dict)
    blueprint: dict[str, Any] | None = None
    capabilities: dict[str, list[str]] = field(default_factory=dict)
    critique: dict[str, Any] = field(default_factory=dict)
    ledger: list[str] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    timings: dict[str, Any] = field(default_factory=dict)
    total_ms: int = 0
    error: str | None = None
    intake: dict[str, Any] = field(default_factory=dict)
    turns: list[dict[str, Any]] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)
    closing: str = ""
    family_word: str | None = field(default=None, repr=False)  # never in summary/frames

    def summary(self) -> dict[str, Any]:
        return {
            "village_id": self.village_id,
            "trace_id": self.trace_id,
            "state": self.state,
            "states": self.states,
            "mode": self.mode,
            "roles": {r: {"status": v.status, "ms": v.ms, "attempts": v.attempts, "reason": v.reason} for r, v in self.roles.items()},
            "capabilities": self.capabilities,
            "critique": self.critique,
            "ledger": self.ledger,
            "intake": self.intake,
            "turns": self.turns,
            "question": self.turns[-1]["question"] if self.turns and self.state == "clarify" else None,
            "review": self.review,
            "closing": self.closing,
            "timings": self.timings,
            "total_ms": self.total_ms,
            "error": self.error,
        }


@dataclass
class FoundingSession:
    run: BuilderRun
    answers: asyncio.Queue = field(default_factory=asyncio.Queue)
    intake: IntakeState | None = None
    question: Any = None
    draft: Any = None
    waiting: bool = False  # True only while Village waits for a live answer (not during replay)


SESSIONS: dict[str, FoundingSession] = {}
RUNS: dict[str, BuilderRun] = {}


def _set_state(run: BuilderRun, state: str) -> None:
    run.state = state
    if not run.states or run.states[-1] != state:
        run.states.append(state)


def rebase_spans(spec: dict[str, Any], text: str, need_quotes: dict[str, list[str]] | None = None) -> None:
    """Point every need's source_span at the founder's words; needs not found become origin data."""
    old = spec["blueprint"]["description"]["text"]
    spec["blueprint"]["description"]["text"] = text
    for need in spec["blueprint"]["needs"]:
        s = need.get("source_span")
        quotes = [old[s["start"] : s["end"]]] if s else (need_quotes or {}).get(need["id"], [])
        need["source_span"] = None
        for q in quotes:
            at = text.find(q)
            if at >= 0:
                need["source_span"] = {"start": at, "end": at + len(q)}
                if not s:
                    need["origin"] = "follow_up"
                break
        if need["source_span"] is None and s:
            need["origin"] = "data"


def apply_member_rules(spec: dict[str, Any], record: dict[str, Any], *, pending_at: str | None = None) -> list[dict[str, Any]]:
    """D24 #5 the center person's own rules → P-QH-01. Pending (D29) until she says them on the welcome call."""
    applied = []
    people = {p["id"]: p for p in spec["blueprint"]["people"]}
    for rule in record.get("rules_from_members", []):
        person = people.get(rule["member_id"])
        if not person or rule["rule_id"] != "P-QH-01":
            continue
        qh, src = rule["params"]["quiet_hours"], rule["source"]
        person["profile"]["quiet_hours"] = qh
        if pending_at:
            params = {"quiet_hours": qh, "status": "pending_her_words", "source_kind": "call", "source_ref": "welcome_call", "welcome_call_at": pending_at}
        else:
            params = {"quiet_hours": qh, "status": "confirmed", "source_kind": src["kind"], "source_ref": src["ref"], "source_secs": src["secs"], "words": rule.get("words", "")[:120]}
        policy = next((p for p in spec["policies"] if p["rule_id"] == "P-QH-01"), None)
        if policy is None:
            policy = {"rule_id": "P-QH-01", "params": {}, "applies_to_member_ids": [person["id"]]}
            spec["policies"].append(policy)
        policy["params"], policy["applies_to_member_ids"] = params, [person["id"]]
        applied.append({"member": person, "rule": rule, "pending": bool(pending_at)})
    return applied


def confirm_quiet_hours(spec: dict[str, Any], member_id: str, quiet_hours: str, words: str, secs: float, ref: str = "welcome_call") -> dict[str, Any]:
    """Voice lane hook: after the welcome call, P-QH-01 becomes her words with call provenance."""
    pol = next(p for p in spec["policies"] if p["rule_id"] == "P-QH-01")
    pol["params"] = {"quiet_hours": quiet_hours, "status": "confirmed", "source_kind": "call", "source_ref": ref, "source_secs": secs, "words": words[:120]}
    pol["applies_to_member_ids"] = [member_id]
    return pol


async def _emit(services: Any, run: BuilderRun, text: str, kind: str = "note", source: str = "founder", mode: str | None = None) -> None:
    await services.broadcast_control(run.village_id, frames.reasoning(run.village_id, text, kind, run.trace_id, source=source, mode=mode))


class Ledger:
    """1.2.1 `control{kind: ledger}` rows, updated in place (same id) running → done|fallback."""

    def __init__(self, services: Any, run: BuilderRun) -> None:
        self.svc, self.run, self.t0, self.n = services, run, {}, 0

    async def start(self, what: str, status: str = "running") -> str:
        self.n += 1
        rid = f"lg_{self.run.trace_id[:8]}_{self.n:02d}"
        self.t0[rid] = time.perf_counter()
        await self.svc.broadcast_control(self.run.village_id, frames.ledger(self.run.village_id, rid, status, what, trace_id=self.run.trace_id))
        return rid

    async def finish(self, rid: str, status: str, what: str, result: str = "", mode: str = "acted_alone") -> None:
        ms = int((time.perf_counter() - self.t0.get(rid, time.perf_counter())) * 1000)
        self.run.ledger.append(frames.ledger_line(status, what, result))
        await self.svc.broadcast_control(self.run.village_id, frames.ledger(self.run.village_id, rid, status, what, result or None, mode=mode, trace_id=self.run.trace_id, elapsed_ms=ms))

    async def row(self, status: str, what: str, result: str = "", mode: str = "acted_alone") -> None:
        await self.finish(await self.start(what), status, what, result, mode)


async def check_medications(run: BuilderRun, services: Any, opts: FoundingOptions, medications: list[str], ledger: Ledger, center: str | None) -> None:
    if not medications:
        return
    if opts.dailymed == "off":
        await ledger.row("fallback", "DailyMed check", "will check after you invite")
        return
    transport = fixture_transport(DAILYMED_FIXTURES) if opts.dailymed == "fixture" else None
    t0 = time.perf_counter()

    async def one(name: str, client: httpx.AsyncClient) -> None:
        what = f"DailyMed: {name}"
        rid = await ledger.start(what)
        r = await lookup_medication(name, client)
        if r.checked:
            fact = r.fact(run.village_id, center)
            run.facts.append(fact)
            if hasattr(services, "record_fact"):
                await services.record_fact(fact)
            title = (r.title or r.name).split("[")[0].strip().title()
            note = " (high-alert, bleeding)" if name in ("apixaban", "warfarin") else ""
            await ledger.finish(rid, "done", what, f"✓{note} {title} label ({r.published}) {r.url}")
            await services.record_decision(builder_decision(run.village_id, f"Checked {r.name} on DailyMed{note}: {title} label, published {r.published}. {r.url}"[:400], refs=[{"kind": "fact", "id": f"med_label:{r.name}"}], source={"kind": "url", "ref": "dailymed", "url": r.url}, trace_id=run.trace_id))
        else:
            await ledger.finish(rid, "fallback", what, f"will check after you invite ({r.error})")

    async with httpx.AsyncClient(timeout=6.0, transport=transport) as client:
        await asyncio.gather(*(one(m, client) for m in medications))
    run.timings["dailymed_ms"] = int((time.perf_counter() - t0) * 1000)


async def consent_call(spec: dict[str, Any], run: BuilderRun, services: Any, opts: FoundingOptions, ledger: Ledger, helper_first: str | None = None) -> dict[str, Any] | None:
    people = spec["blueprint"]["people"]
    helper = next((p for p in people if helper_first and p["name"].split()[0] == helper_first), None) or next((p for p in people if p["role"] in ("caregiver", "volunteer") and p.get("phone") and p.get("consent", {}).get("ai_calls") is not False), None)
    if helper is None:
        return None
    first = helper["name"].split()[0]
    days = "/".join(d for d in DAYS if d in {x for a in helper["profile"].get("availability", []) for x in a["days"]})
    what = f"Calling {first} to confirm {days or 'availability'} and ask if Village may call him"
    dialer = opts.dialer or default_dialer()
    if dialer is None:
        await ledger.row("fallback", what, "will call after you invite")
        return None
    rid = await ledger.start(what)
    coord = next((p for p in people if p["id"] == spec["village"].get("coordinator_id")), people[0])
    payload = consent_call_payload(helper, village_id=run.village_id, coordinator_name=coord["name"].split()[0], family_label=spec["village"].get("name", "the family"))
    try:
        result = await dialer.outbound_call(payload)
    except Exception as exc:
        await ledger.finish(rid, "fallback", what, f"{type(exc).__name__}; will call after you invite")
        return None
    ans = result.get("answer")
    if not ans:
        await ledger.finish(rid, "running", what, f"ringing ({result.get('conversation_id', '')}); answer shows when the call ends")
        return result
    text = f"{first} confirmed {'/'.join(ans.get('availability_days', []))} · {'yes to calls' if ans.get('ai_calls') else 'no calls'}"
    await ledger.finish(rid, "done", what, text + (" (mocked dialer)" if result.get("mocked") else ""))
    await services.record_decision(builder_decision(run.village_id, f"{text} (Founder's call during the intake{', mocked' if result.get('mocked') else ''}).", refs=[{"kind": "member", "id": helper["id"], "label": first}], rule_id="R-VERIFY-CONSENT", source={"kind": "call", "ref": result.get("conversation_id") or "founder_call", "secs": float(ans.get("secs", 0))}, trace_id=run.trace_id))
    helper["consent"]["ai_calls"] = bool(ans.get("ai_calls"))
    return result


def rota_check(intake: IntakeState, helper: str) -> tuple[bool, str]:
    a = intake.fields["availability"]
    names: dict[str, str] = {}

    def days(v: Any) -> list[str]:
        return v.get("days", []) if isinstance(v, dict) else []

    for d in days(a.get("speaker_days")):
        names[d] = intake.speaker
    for d in days(a.get("helper_days")):
        names[d] = helper
    gaps = [d for d in DAYS if d not in names]
    if gaps:
        return False, f"no one on {', '.join(gaps)}"
    return True, f"every night has a name. Thursday is {names['Thu']}."


def apply_intake(spec: dict[str, Any], intake: IntakeState) -> dict[str, Any]:
    """Intake fields → the draft: people's days/notes, consent, contacts, fridge card, refill list owner."""
    f = intake.fields
    people = {p["name"].split()[0]: p for p in spec["blueprint"]["people"]}
    changes: dict[str, Any] = {}
    a = f["availability"]
    helper = next((m["name"] for m in (f["members"].get("members") or []) if m.get("relation") != "self" and not m.get("remote")), None)
    if helper in people and isinstance(a.get("helper_days"), dict) and a["helper_days"].get("days"):
        people[helper]["profile"]["availability"] = [{"days": a["helper_days"]["days"], "window": "17:00-21:30", "note": "; ".join(a["helper_days"].get("constraints", []) + ([a["helper_days"]["reminder"]] if a["helper_days"].get("reminder") else []))[:200]}]
        changes[helper] = a["helper_days"]["days"]
    coord = next((p for p in spec["blueprint"]["people"] if p["id"] == spec["village"].get("coordinator_id")), None)
    if coord and isinstance(a.get("speaker_days"), dict) and a["speaker_days"].get("days"):
        coord["profile"]["availability"] = [{"days": a["speaker_days"]["days"], "window": "16:00-22:00", "note": ", ".join(a.get("speaker_does", []))[:200] or "from the intake"}]
    for m in f["members"].get("members") or []:
        p = people.get(m["name"])
        if p and m.get("relation") != "self":
            bits = [x for x in (m.get("lives"), m.get("distance") and f"{m['distance']} away", m.get("remote") and "can't come on short notice", m.get("takes_on") and ", ".join(m["takes_on"])) if x]
            if bits:
                p["notes"] = ("; ".join(bits) + ". " + p.get("notes", ""))[:400]
    center = next((p for p in spec["blueprint"]["people"] if p["id"] == spec["village"].get("care_recipient_id")), None)
    if center:
        ch = f["channels"]
        if ch.get("center_lang") == "es":
            center["profile"]["lang"] = "es"
        nearby = f["home"].get("nearby") or []
        hosp = f["emergencies"].get("hospital")
        extra = "; ".join(x for x in (", ".join(nearby) and f"Nearby: {', '.join(nearby)}", f["home"].get("building"), hosp and f"Hospital: {hosp}") if x)
        if extra:
            center["notes"] = (extra + ". " + center.get("notes", ""))[:400]
        changes["contacts"] = nearby
    for pr in spec.get("printables", []):
        if pr.get("kind") == "fridge_card" and f["emergencies"].get("hospital"):
            pr["emergency_line"] = f"Emergencia: llame al 911 primero. Hospital: {f['emergencies']['hospital'].replace(' Hospital', '')}."
    # D29 review beat: the helper view starts without the refill list; the review patch adds it
    hv = spec["views"].get("helper")
    if hv:
        for eid in [e for e, el in hv["elements"].items() if el["type"] == "RefillCard"]:
            hv["elements"].pop(eid)
            hv.get("needs_served", {}).pop(eid, None)
            for el in hv["elements"].values():
                if "children" in el:
                    el["children"] = [c for c in el["children"] if c != eid]
            for area in spec["blueprint"]["life_areas"]:
                area["modules"] = [m for m in area["modules"] if m != f"helper:{eid}"] or area["modules"]
        changes["helper_refill_removed"] = True
    return changes


def review_patch(spec: dict[str, Any], text: str) -> tuple[dict[str, Any], str | None]:
    """Word edits on the draft. 'X should see the refill list too' → RefillCard in X's view."""
    m = re.search(r"([A-ZÁÉÍÓÚ][a-zá-ú]+) should see the refill (list|checklist)", text)
    if not m:
        return spec, None
    person = next((p for p in spec["blueprint"]["people"] if p["name"].split()[0] == m.group(1)), None)
    if not person or not person.get("view"):
        return spec, None
    role = person["view"]
    out = deepcopy(spec)
    view = out["views"][role]
    if any(el["type"] == "RefillCard" for el in view["elements"].values()):
        return out, f"{m.group(1)} already sees the refill list"
    view["elements"]["refill"] = {"type": "RefillCard", "props": {"title": "Refill checklist", "bind": "prescriptions:current", "owner": m.group(1), "show_superseded": True, "show_schedule": True, "show_source": True}}
    view["elements"]["s"]["children"].insert(1, "refill")
    need = next((n["id"] for n in out["blueprint"]["needs"] if n["id"] in ("n_refills", "n_dose_change")), "n_safety")
    view.setdefault("needs_served", {})["refill"] = [need]
    health = next((a for a in out["blueprint"]["life_areas"] if a["id"] == "health"), None)
    if health and f"{role}:refill" not in health["modules"]:
        health["modules"].append(f"{role}:refill")
    return out, f"RefillCard added to {m.group(1)}'s view ({role})"


def surfaces_line(spec: dict[str, Any]) -> str:
    out = []
    for p in spec["blueprint"]["people"]:
        ch = spec["channels"].get(p["id"], [])
        bits = [("app" if any(c.startswith("app:") for c in ch) else ""), ("phone line" if "phone_line" in ch else ""), ("calls" if "verification:call" in ch else ""), ("fridge card" if "fridge_card" in ch else "")]
        out.append(f"{p['name'].split()[0]} {' + '.join(b for b in bits if b) or 'no channel yet'}")
    return "Surfaces: " + "; ".join(out)


def topic_line(topic: str, intake: IntakeState, spec: dict[str, Any]) -> str:
    f = intake.fields
    t = next((x for x in intake.topics if x["id"] == topic), {})
    if intake.kind == "care":
        if topic == "routine":
            return "Rules on: never says how many pills · dose already logged → report, tell the on-duty person · missed dose → reminder, then the on-duty person"
        if topic == "money":
            return f"Rules on: money in a family member's name → check with that person first · not confirmed → don't send · Village never moves money · verifier: {f['money'].get('handler', '?')} (first), {intake.speaker}"
        if topic == "emergencies":
            return f"Emergency → 911 first · ladder {f['emergencies'].get('first', '')} · {f['emergencies'].get('hospital', '')} on the fridge card"
        if topic == "consent":
            return f"Welcome call planned {f['consent'].get('welcome_call', '?')} · quiet hours pending her words"
        if topic == "home":
            return "Contacts: " + ", ".join(f["home"].get("nearby", []))
    if topic == "channels":
        return surfaces_line(spec)
    return t.get("does", "covered")


def closing_summary(spec: dict[str, Any], run: BuilderRun, intake: IntakeState | None) -> str:
    bp = spec["blueprint"]
    rules = len(spec.get("policies", []))
    pending = 1 if any(p["rule_id"] == "P-QH-01" and p["params"].get("status", "").startswith("pending") for p in spec["policies"]) else 0
    people = [p for p in bp["people"]]
    return f"Here is the draft: {len(people)} people, {len(bp['life_areas'])} life areas, {len(bp['needs'])} needs, {rules} rules on, {pending} thing pending your mom. What is wrong?"


async def found(
    input: FoundingInput,
    *,
    village_id: str | None = None,
    services: Any | None = None,
    options: FoundingOptions | None = None,
    run: BuilderRun | None = None,
) -> BuilderRun:
    svc = services or MemoryServices()
    opts = options or FoundingOptions()
    village_id = village_id or kind_config(input.kind or "care")["village_id"]
    run = run or BuilderRun(village_id=village_id, trace_id=uuid.uuid4().hex, mode=opts.mode)
    RUNS[village_id] = run
    intake = IntakeState(opener=input.description)
    session = SESSIONS.setdefault(village_id, FoundingSession(run=run))
    session.run, session.intake = run, intake
    t0 = time.perf_counter()
    llm = opts.llm_client if opts.llm_client is not None else (None if opts.mode == "fixture" else get_llm(opts.llm, "sonnet"))
    run.timings["llm"] = getattr(llm, "model", "off") if llm is not None else "off"
    ledger = Ledger(svc, run)
    tasks: dict[str, asyncio.Task] = {}
    pending = list(input.answers)
    replay = list(opts.replay or [])

    def pick(q: Any) -> str:
        """Replay rows are matched to the question actually asked (same text → same topic → next)."""
        rows = [r if isinstance(r, dict) else {"text": r} for r in replay]
        text = getattr(q, "text", None)
        topic = "review" if isinstance(q, Review) else getattr(q, "topic", None)
        idx = next((i for i, r in enumerate(rows) if text and r.get("asked") == text), None)
        if idx is None and topic:
            idx = next((i for i, r in enumerate(rows) if r.get("topic") == topic and not (topic == "money" and r.get("asked") and "word" in r["asked"] and getattr(q, "field", "") != "family_word")), None)
        if idx is None:
            idx = 0
        return rows[idx]["text"] if replay.pop(idx) is not None else ""

    async def get_answer(live_ok: bool) -> str | None:
        if pending:
            return pending.pop(0)
        if replay and (opts.resume is None or len(intake.covered()) < opts.resume):
            if opts.replay_delay_s:
                await asyncio.sleep(opts.replay_delay_s)
            return pick(session.question)
        if replay and opts.resume is not None:
            replay.clear()  # resume point reached: the rest is live
        if live_ok and opts.clarify_wait_s > 0:
            session.waiting = True
            try:
                return str(await asyncio.wait_for(session.answers.get(), timeout=opts.clarify_wait_s))
            except asyncio.TimeoutError:
                return None
            finally:
                session.waiting = False
        return None

    with span("builder.found", "AGENT", **{"session.id": f"village-{village_id}", "graph.node.id": "found", "input.value": input.description[:500]}) as root:
        try:
            _set_state(run, "listening")
            await _emit(svc, run, f"Listening: {len(input.description.split())} words from the founder.", "plan")
            bp = await stream_blueprint(input.description, village_id, svc, input.kind, llm=llm, allowed_ids={m["id"] for m in input.members if "id" in m}, trace_id=run.trace_id, timings=run.timings)
            kind = input.kind or bp.get("kind") or "care"
            spec = templates.spec(kind, village_id=village_id, status="draft")
            record = kind_record(kind) if opts.demo_record else {}
            center_id = spec["village"].get("care_recipient_id")
            speaker = next((p["name"].split()[0] for p in spec["blueprint"]["people"] if p["id"] == spec["village"].get("coordinator_id")), "Founder")
            intake = IntakeState(opener=input.description, kind=kind, speaker=speaker)
            session.intake = intake
            draft = DraftBuilder(templates.spec(kind, village_id=village_id, status="draft"), kind, village_id, svc, run.trace_id)
            session.draft = draft
            await draft.start()
            center_p = next((p for p in spec["blueprint"]["people"] if p["id"] == center_id), None)
            speaker_id = spec["village"].get("coordinator_id")

            def build_vars() -> dict[str, Any]:
                f = intake.fields
                mem = f.get("members", {}).get("members")
                helper_ = next((m["name"] for m in mem if isinstance(m, dict) and m.get("relation") != "self" and not m.get("remote")), None) if isinstance(mem, list) else None
                meds_ = f.get("meds", {}).get("meds") if isinstance(f.get("meds", {}).get("meds"), list) else []
                ch = next((m for m in meds_ if isinstance(m, dict) and m.get("change")), None)
                hd = f.get("availability", {}).get("helper_days")
                return {"center": (center_p or {}).get("short_name") or ((center_p or {}).get("name", "her").split()[0]), "speaker": speaker, "helper": helper_ or "the helper",
                        "handler": f.get("money", {}).get("handler") or helper_ or "the verifier", "reminder": (hd or {}).get("reminder", "reminder") if isinstance(hd, dict) else "reminder",
                        "change": f"{ch['name']} changed to {ch['change']['to']} mg" if ch else "a dose changed", "n_people": len(spec["blueprint"]["people"]), "n_meds": len(meds_) or "the"}

            found0 = await record_answer(input.description, None, intake, None)
            merge(intake, found0)
            q: Question | Review = next_question(intake)
            await _emit(svc, run, f"{now_i_know(intake, found0, None)} · {intake.meter()} · gaps: {', '.join(intake.gaps()[:4])}{'…' if len(intake.gaps()) > 4 else ''}" + (f" · next: {q.text}" if isinstance(q, Question) else ""))
            await draft.on_answer(intake, build_vars(), speaker_id=speaker_id, helper=None)
            await svc.broadcast_control(village_id, frames.counter("intake_covered", len(intake.covered()), "topics covered", of=10))
            # ---- intake turns (care villages; block villages go straight to the draft)
            while isinstance(q, Question):
                _set_state(run, "clarify")
                intake.asked.append(f"{q.topic}.{q.field}")
                session.question = q
                turn = {"n": q.n, "topic": q.topic, "question": q.text, "meter_before": intake.meter()}
                await _emit(svc, run, f"Village: {q.text}", "note", mode="asked_human")
                await svc.broadcast_control(village_id, frames.blueprint(village_id, "questions", [{"question": q.text}], run.trace_id))
                await svc.record_decision(builder_decision(village_id, f"Asked ({q.topic}): {q.text}", kind="note", mode="asked_human", trace_id=run.trace_id))
                ans = await get_answer(live_ok=True)
                if not ans:
                    turn["answer"] = None
                    run.turns.append(turn)
                    await _emit(svc, run, f"No answer yet; building with what I have · {intake.meter()}")
                    break
                is_word = q.topic == "money" and q.field == "family_word"
                intake.transcript.append({"who": "founder", "text": ans, "ask": f"{q.topic}.{q.field}"})
                shown = "[family word] · set" if is_word else ans
                await _emit(svc, run, f"{speaker}: {shown}")
                await svc.record_decision(builder_decision(village_id, f"Answered ({q.topic}): {shown}"[:400], kind="note", mode="asked_human", trace_id=run.trace_id))
                found_ = await record_answer(ans, q, intake, llm)
                newly = merge(intake, found_)
                if intake.family_word:
                    run.family_word = intake.family_word
                # side effects (the Founder does work between questions)
                av = intake.fields.get("availability", {})
                mem = intake.fields.get("members", {}).get("members")
                helper = next((m["name"] for m in mem if m.get("relation") != "self" and not m.get("remote")), None) if isinstance(mem, list) else None
                if "call" not in tasks and isinstance(av.get("helper_days"), dict) and av["helper_days"].get("days"):
                    hp = next((p for p in spec["blueprint"]["people"] if p["name"].split()[0] == helper), None)
                    if hp:
                        hp["profile"]["availability"] = [{"days": av["helper_days"]["days"], "window": "17:00-21:30"}]
                    tasks["call"] = asyncio.create_task(consent_call(spec, run, svc, opts, ledger, helper))
                if "call" not in tasks and "volunteers" in intake.covered():
                    tasks["call"] = asyncio.create_task(consent_call(spec, run, svc, opts, ledger))
                if "rota" not in tasks and av.get("helper_days") and av.get("speaker_days"):
                    ok, line = rota_check(intake, helper or "the helper")
                    await ledger.row("done" if ok else "fallback", "Rota coverage check", line)
                    tasks["rota"] = asyncio.create_task(asyncio.sleep(0))
                meds = med_names(intake)
                if meds and "meds" not in tasks:
                    tasks["meds"] = asyncio.create_task(check_medications(run, svc, opts, meds, ledger, center_id))
                    ch = next((m for m in (intake.fields.get("meds", {}).get("meds") or []) if isinstance(m, dict) and m.get("change")), None)
                    if ch:
                        await ledger.row("done", "Refill list", f"{ch['name']} {ch['change']['to']} mg (was 5 mg, Oct 3, {intake.fields['meds'].get('prescriber', '')}) · old bottle in the cabinet → need added")
                for t in newly:
                    await ledger.row("done", f"{t} covered", topic_line(t, intake, spec))
                if found_.get("money", {}).get("family_word"):
                    await ledger.row("done", "Family word", "set (never shown here)")
                q = next_question(intake)
                nxt = q.text if isinstance(q, Question) else "review"
                know = now_i_know(intake, found_, run.turns and q if False else None)
                turn.update({"answer": shown, "now_i_know": know, "meter": intake.meter(), "gaps": intake.gaps(), "next": nxt})
                run.turns.append(turn)
                await _emit(svc, run, f"{know} · {intake.meter()}" + (f" · gaps: {', '.join(intake.gaps()[:3])}" if intake.gaps() else "") + f" · next: {nxt}"[:160])
                turn["will_build"] = await draft.on_answer(intake, build_vars(), speaker_id=speaker_id, helper=helper)
                await svc.broadcast_control(village_id, frames.counter("intake_covered", len(intake.covered()), "topics covered", of=10))
                await asyncio.sleep(0)  # let the Founder's background work land between questions
            session.question = None
            run.intake = intake.to_dict()
            if intake.transcript:
                extra = heuristic_blueprint(input.description, kind, intake.answers_text())
                names = {p.get("name", "").split()[0].lower() for p in bp.get("people", [])}
                for p in extra["people"]:
                    if p["name"].split()[0].lower() not in names and p["role"] not in ("coordinator", "care_recipient"):
                        bp["people"].append(p)
            run.blueprint = bp
            _set_state(run, "working")
            text = (input.description + ("\n" + intake.answers_text() if intake.transcript else ""))[:2000]
            rebase_spans(spec, text, kind_config(kind).get("need_quotes"))
            changes = apply_intake(spec, intake) if (intake.transcript and kind == "care") else {}
            run.intake["applied"] = changes
            if not intake.transcript:
                bp_names = {p.get("name", "").split()[0].lower() for p in bp.get("people", [])}
                for p in spec["blueprint"]["people"]:
                    if p["name"].split()[0].lower() not in bp_names and p.get("short_name", "").lower() not in bp_names and p["role"] not in ("coordinator", "care_recipient"):
                        await svc.record_decision(builder_decision(village_id, f"{p['name'].split()[0]}: from the village record, not from what you said; confirm on review.", kind="note", mode="asked_human", refs=[{"kind": "member", "id": p["id"]}], trace_id=run.trace_id))
            cons = intake.fields.get("consent", {})
            pending_at = cons.get("welcome_call") if cons.get("center_rules") else None
            for item in apply_member_rules(spec, record, pending_at=pending_at):
                rule, person = item["rule"], item["member"]
                src = rule["source"]
                if item["pending"]:
                    await svc.record_decision(builder_decision(village_id, f"Quiet hours for {person['name'].split()[0]}: pending her words (welcome call {pending_at}). Village asks her, not {speaker}.", rule_id="P-QH-01", mode="asked_human", refs=[{"kind": "member", "id": person["id"]}, {"kind": "policy", "id": "P-QH-01"}], trace_id=run.trace_id))
                else:
                    mmss = f"{int(src['secs']) // 60}:{int(src['secs']) % 60:02d}"
                    await svc.record_decision(builder_decision(village_id, f"{person.get('short_name') or person['name'].split()[0]}'s rule: no calls {rule['params']['quiet_hours']} — her words: \"{rule.get('words', '')}\" (welcome call, {mmss}).", rule_id="P-QH-01", refs=[{"kind": "member", "id": person["id"]}, {"kind": "policy", "id": "P-QH-01"}], source={"kind": src["kind"], "ref": src["ref"], "secs": src["secs"], "quote": rule.get("words", "")}, trace_id=run.trace_id))
                    await _emit(svc, run, f"Quiet hours · after 9:30 PM, no calls (her words, welcome call {mmss})", "decision", mode="acted_alone")
            people = spec["blueprint"]["people"]
            plan = plan_capabilities(spec, signals=opts.signals)
            crit = await critique(plan, people, village_id=village_id, services=svc, llm=llm, trace_id=run.trace_id)
            run.critique = {"applied": crit.applied, "refused": crit.refused, "assumptions": crit.assumptions, "source": crit.source}
            run.capabilities = plan.as_dict()
            for row in capability_rows(village_id, plan, people, trace_id=run.trace_id):
                await svc.record_decision(row)
                await _emit(svc, run, row["text"], "decision", source="builder", mode="acted_alone")
            if "meds" not in tasks:
                meds = input.medications
                if meds is None:
                    meds = sorted({m["name"] for m in record.get("medications", []) if m.get("status") != "superseded"}) if record else []
                tasks["meds"] = asyncio.create_task(check_medications(run, svc, opts, meds, ledger, center_id))
            if "call" not in tasks:
                tasks["call"] = asyncio.create_task(consent_call(spec, run, svc, opts, ledger))
            t_r = time.perf_counter()
            render_ids = {r: await ledger.start(f"Render {r} view") for r in spec["views"]}
            spec, roles = await render_views(spec, village_id=village_id, services=svc, llm=llm, plan=plan, per_role_s=opts.per_role_s, total_s=opts.total_s, trace_id=run.trace_id)
            for r, res in roles.items():
                await ledger.finish(render_ids[r], "done" if res.status != "template" else "fallback", f"Render {r} view", f"{res.status}" + (f" ({res.reason})" if res.reason else f" in {res.ms / 1000:.1f} s"))
            run.timings["render_ms"] = int((time.perf_counter() - t_r) * 1000)
            run.timings["render_role_ms"] = {r: v.ms for r, v in roles.items()}
            run.roles = roles
            await asyncio.gather(*tasks.values())
            run.timings["founder_work_ms"] = int((time.perf_counter() - t0) * 1000)
            spec = ensure_chat(spec)
            for person in people:
                chans = ", ".join(spec["channels"].get(person["id"], []))
                await svc.record_decision(builder_decision(village_id, f"{person['name'].split()[0]}: {person['view'] or 'phone-only'} through {chans}.", refs=[{"kind": "member", "id": person["id"]}], trace_id=run.trace_id))
            report = validate_spec(spec)
            if not report.ok:
                run.timings["invalid_merge"] = report.errors[:3]
                await svc.record_decision(templates.template_decision(village_id, "all", report.errors[0][:200]))
                spec = templates.spec(kind, village_id=village_id, status="draft")
            run.spec = spec
            draft.store = False
            await svc.store_spec(village_id, spec, status="draft")
            _set_state(run, "draft")
            # ---- review turn: the founder edits in words, Village patches
            run.closing = closing_summary(spec, run, intake)
            await _emit(svc, run, f"Village: {run.closing}", "plan", mode="asked_human")
            if opts.review:
                _set_state(run, "review")
                session.question = Review(run.closing)
                edit = await get_answer(live_ok=True)
                session.question = None
                run.review = {"question": run.closing, "answer": edit}
                if edit:
                    await _emit(svc, run, f"{speaker}: {edit}")
                    patched, what = review_patch(spec, edit)
                    if what and validate_spec(patched).ok:
                        spec = patched
                        run.spec = spec
                        await svc.store_spec(village_id, spec, status="draft")
                        await ledger.row("done", "Patch from your words", what)
                        who = next((p for p in spec["blueprint"]["people"] if p["name"].split()[0] in edit), None)
                        role_ = (who or {}).get("view")
                        if who and role_ and "refill" in spec["views"].get(role_, {}).get("elements", {}):
                            el = spec["views"][role_]["elements"]["refill"]
                            await draft.add_element(role_, "refill", el, f"{who['name'].split()[0]} does the ordering (your words)", who, spec["views"][role_].get("needs_served", {}).get("refill", ["n_safety"]))
                        await svc.record_decision(builder_decision(village_id, f"Review edit: \"{edit[:120]}\" → {what}.", mode="asked_human", trace_id=run.trace_id))
                        run.review["patch"] = what
                    else:
                        await _emit(svc, run, "I couldn't turn that into a change yet; it stays a note on the draft.")
                await _emit(svc, run, "Send the invites.", "plan", mode="asked_human")
            rev = spec.get("rev", 1)
            await ledger.row("done", f"Draft ready · rev {rev}", f"{len(spec['views'])} apps · {len(spec['blueprint']['people'])} people")
            await svc.broadcast_control(village_id, frames.blueprint(village_id, "done", [{"rev": rev}], run.trace_id))
            if hasattr(svc, "push_snapshot"):
                await svc.push_snapshot(village_id)
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            root.set("error", run.error)
            for t in tasks.values():
                t.cancel()
            raise
        finally:
            run.total_ms = int((time.perf_counter() - t0) * 1000)
            run.timings["total_ms"] = run.total_ms
    return run


def demo_options(kind: str = "care", **kw: Any) -> FoundingOptions:
    """Replay wiring: recorded DailyMed + scripted consent answer (both mocked, labelled)."""
    kw.setdefault("dialer", ScriptedConsentDialer(answers=deepcopy(demo_script(kind))))
    kw.setdefault("dailymed", "fixture")
    return FoundingOptions(**kw)


def replay_input(path: Any = None, kind: str = "care") -> tuple[FoundingInput, list[dict[str, Any]]]:
    rows = load_intake(path, kind)
    return FoundingInput(description=rows[0]["text"], kind=kind), rows[1:]


def answer(village_id: str, text: str) -> bool:
    session = SESSIONS.get(village_id)
    if session is None:
        return False
    session.answers.put_nowait(text)
    return True
