"""Founder (AGENT.md §2): listening → clarify → working → draft. Blueprint streams first; the Founder
picks capabilities per person, takes a second opinion, renders views in parallel and — while views
render — does real work (D23 #4): DailyMed lookups and the helper's availability + consent call."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from . import frames, templates
from .blueprint import stream_blueprint
from .capabilities import decision_rows as capability_rows
from .capabilities import plan_capabilities
from .critique import critique
from .dailymed import fixture_transport, lookup_medication
from .decisions import builder_decision
from .dialer import REYES_SCRIPT, ScriptedConsentDialer, consent_call_payload, default_dialer
from .llm_port import get_llm
from .mapping import ensure_chat
from .paths import DATA
from .render import RoleResult, render_views
from .services_stub import MemoryServices
from .spans import span
from .validate import validate_spec

STATES = ["listening", "clarify", "working", "draft"]
DAILYMED_FIXTURES = Path(__file__).parent / "tests" / "data" / "dailymed"
REYES_RECORD = DATA / "villages" / "reyes_family.json"


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
    mode: str = "full"  # full | fixture
    llm: str | None = None  # off | on | None (env)
    clarify_wait_s: float = 0.0  # text founding: 30 s pause for an answer, then proceed
    per_role_s: float = 45.0
    total_s: float = 60.0
    dialer: Any | None = None
    dailymed: str = "live"  # live | fixture | off
    demo_record: bool = True  # care villages: use data/villages/reyes_family.json meds + member rules
    signals: dict[str, Any] = field(default_factory=dict)
    llm_client: Any | None = None  # injected (tests)


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
            "questions": (self.blueprint or {}).get("questions", []),
            "timings": self.timings,
            "total_ms": self.total_ms,
            "error": self.error,
        }


@dataclass
class FoundingSession:
    """Lets `POST /villages/{id}/answers` feed the clarify pause."""

    run: BuilderRun
    answers: asyncio.Queue = field(default_factory=asyncio.Queue)


SESSIONS: dict[str, FoundingSession] = {}
RUNS: dict[str, BuilderRun] = {}


def _set_state(run: BuilderRun, state: str) -> None:
    run.state = state
    run.states.append(state)


def rebase_spans(spec: dict[str, Any], text: str) -> None:
    """Point every need's source_span at the founding words; needs not in them become origin data."""
    old = spec["blueprint"]["description"]["text"]
    spec["blueprint"]["description"]["text"] = text
    for need in spec["blueprint"]["needs"]:
        s = need.get("source_span")
        if not s:
            continue
        quote = old[s["start"] : s["end"]]
        at = text.find(quote)
        if at >= 0:
            need["source_span"] = {"start": at, "end": at + len(quote)}
        else:
            need["source_span"] = None
            need["origin"] = "data"


def apply_member_rules(spec: dict[str, Any], record: dict[str, Any]) -> list[dict[str, Any]]:
    """D24 #5: the center's own rules (Carmen's quiet hours, her words on the welcome call)."""
    applied = []
    people = {p["id"]: p for p in spec["blueprint"]["people"]}
    for rule in record.get("rules_from_members", []):
        person = people.get(rule["member_id"])
        if not person or rule["rule_id"] != "P-QH-01":
            continue
        qh = rule["params"]["quiet_hours"]
        src = rule["source"]
        person["profile"]["quiet_hours"] = qh
        params = {"quiet_hours": qh, "source_kind": src["kind"], "source_ref": src["ref"], "source_secs": src["secs"], "words": rule.get("words", "")[:120]}
        policy = next((p for p in spec["policies"] if p["rule_id"] == "P-QH-01"), None)
        if policy is None:
            policy = {"rule_id": "P-QH-01", "params": {}, "applies_to_member_ids": [person["id"]]}
            spec["policies"].append(policy)
        policy["params"] = params
        policy["applies_to_member_ids"] = [person["id"]]
        applied.append({"member": person, "rule": rule})
    return applied


def _record() -> dict[str, Any]:
    try:
        return json.loads(REYES_RECORD.read_text(encoding="utf-8"))
    except Exception:
        return {}


async def _emit(services: Any, run: BuilderRun, text: str, kind: str = "note") -> None:
    await services.broadcast_control(run.village_id, frames.reasoning(run.village_id, text, kind, run.trace_id))


async def _ledger(services: Any, run: BuilderRun, status: str, what: str, result: str) -> None:
    line = frames.ledger_line(status, what, result)
    run.ledger.append(line)
    await _emit(services, run, line, "decision")


async def founder_work(spec: dict[str, Any], run: BuilderRun, services: Any, opts: FoundingOptions, medications: list[str]) -> None:
    """DailyMed per medication + availability/consent call to the helper, in parallel with render."""
    t0 = time.perf_counter()
    vid = run.village_id
    center = spec["village"].get("care_recipient_id")

    async def meds() -> None:
        if not medications or opts.dailymed == "off":
            if medications:
                await _ledger(services, run, "later", "DailyMed check", "will check after you invite")
            return
        transport = fixture_transport(DAILYMED_FIXTURES) if opts.dailymed == "fixture" else None
        async with httpx.AsyncClient(timeout=6.0, transport=transport) as client:
            results = await asyncio.gather(*(lookup_medication(m, client) for m in medications))
        for r in results:
            if r.checked:
                fact = r.fact(vid, center)
                run.facts.append(fact)
                if hasattr(services, "record_fact"):
                    await services.record_fact(fact)
                title = (r.title or r.name).split("[")[0].strip().title()
                await _ledger(services, run, "checked", f"DailyMed {r.name}", f"{title} label ({r.published}) {r.url}")
                await services.record_decision(builder_decision(vid, f"Checked {r.name} on DailyMed: {title} label, published {r.published}. {r.url}"[:400], refs=[{"kind": "fact", "id": f"med_label:{r.name}"}], mode="acted_alone", source={"kind": "url", "ref": "dailymed", "url": r.url}, trace_id=run.trace_id))
            else:
                await _ledger(services, run, "later", f"DailyMed {r.name}", f"will check after you invite ({r.error})")
        run.timings["dailymed_ms"] = max((r.ms for r in results), default=0)

    async def consent_call() -> None:
        people = spec["blueprint"]["people"]
        helper = next((p for p in people if p["role"] in ("caregiver", "volunteer") and p.get("phone") and p.get("consent", {}).get("ai_calls") is not False), None)
        if helper is None:
            return
        dialer = opts.dialer or default_dialer()
        first = helper["name"].split()[0]
        if dialer is None:
            await _ledger(services, run, "later", f"call {first} (availability + consent)", "will call after you invite")
            return
        coord = next((p for p in people if p["id"] == spec["village"].get("coordinator_id")), people[0])
        payload = consent_call_payload(helper, village_id=vid, coordinator_name=coord["name"].split()[0], family_label=spec["village"].get("name", "the family"))
        try:
            result = await dialer.outbound_call(payload)
        except Exception as exc:
            await _ledger(services, run, "failed", f"call {first}", f"{type(exc).__name__}; will call after you invite")
            return
        answer = result.get("answer")
        conv = result.get("conversation_id", "")
        if answer:
            days = "/".join(answer.get("availability_days", []))
            agreed = "agreed to calls" if answer.get("ai_calls") else "declined calls"
            text = f"{first} confirmed {days}; {agreed}"
            await _ledger(services, run, "done", f"call {first} (availability + consent)", text)
            await services.record_decision(builder_decision(vid, f"{text} (Founder's call before the draft{', mocked' if result.get('mocked') else ''}).", refs=[{"kind": "member", "id": helper["id"], "label": first}], mode="acted_alone", rule_id="R-VERIFY-CONSENT", source={"kind": "call", "ref": conv or "founder_call", "secs": float(answer.get("secs", 0))}, trace_id=run.trace_id))
        else:
            await _ledger(services, run, "placed", f"call {first} (availability + consent)", f"ringing ({conv}); answer shows when the call ends")

    await asyncio.gather(meds(), consent_call())
    run.timings["founder_work_ms"] = int((time.perf_counter() - t0) * 1000)


async def found(
    input: FoundingInput,
    *,
    village_id: str = "v_reyes",
    services: Any | None = None,
    options: FoundingOptions | None = None,
    run: BuilderRun | None = None,
) -> BuilderRun:
    svc = services or MemoryServices()
    opts = options or FoundingOptions()
    run = run or BuilderRun(village_id=village_id, trace_id=uuid.uuid4().hex, mode=opts.mode)
    RUNS[village_id] = run
    session = SESSIONS.setdefault(village_id, FoundingSession(run=run))
    session.run = run
    t0 = time.perf_counter()
    llm = opts.llm_client if opts.llm_client is not None else (None if opts.mode == "fixture" else get_llm(opts.llm, "sonnet"))
    run.timings["llm"] = getattr(llm, "model", "off") if llm is not None else "off"
    with span("builder.found", "AGENT", **{"session.id": f"village-{village_id}", "graph.node.id": "found", "input.value": input.description[:500]}) as root:
        try:
            _set_state(run, "listening")
            await _emit(svc, run, f"Listening: {len(input.description.split())} words from the founder.", "plan")
            answers = " ".join(input.answers)
            bp = await stream_blueprint(input.description, village_id, svc, input.kind, llm=llm, answers=answers, allowed_ids={m["id"] for m in input.members if "id" in m}, trace_id=run.trace_id, timings=run.timings)
            if bp.get("questions") and not answers:
                _set_state(run, "clarify")
                for q in bp["questions"]:
                    await svc.record_decision(builder_decision(village_id, f"Asked: {q}", kind="note", trace_id=run.trace_id))
                if opts.clarify_wait_s > 0:
                    try:
                        answer = await asyncio.wait_for(session.answers.get(), timeout=opts.clarify_wait_s)
                        answers = str(answer)
                        await svc.record_decision(builder_decision(village_id, f"Answered: {answers}"[:400], kind="note", trace_id=run.trace_id))
                        bp = await stream_blueprint(input.description, village_id, svc, input.kind, llm=llm, answers=answers, trace_id=run.trace_id, timings={})
                    except asyncio.TimeoutError:
                        await _emit(svc, run, f"No answer in {opts.clarify_wait_s:.0f} s; building with what I have.")
            run.blueprint = bp
            _set_state(run, "working")
            kind = input.kind or bp.get("kind") or "care"
            spec = templates.spec(kind, village_id=village_id, status="draft")
            rebase_spans(spec, input.description)
            record = _record() if (kind == "care" and opts.demo_record) else {}
            bp_names = {p.get("name", "").split()[0].lower() for p in bp.get("people", [])}
            for p in spec["blueprint"]["people"]:
                if p["name"].split()[0].lower() not in bp_names and p.get("short_name", "").lower() not in bp_names and p["role"] not in ("coordinator", "care_recipient"):
                    await svc.record_decision(builder_decision(village_id, f"{p['name'].split()[0]}: from the village record, not from what you said; confirm on review.", kind="note", refs=[{"kind": "member", "id": p["id"]}], trace_id=run.trace_id))
            for item in apply_member_rules(spec, record):
                rule, person = item["rule"], item["member"]
                src = rule["source"]
                await svc.record_decision(builder_decision(village_id, f"{person.get('short_name') or person['name'].split()[0]}'s rule: no calls {rule['params']['quiet_hours']} — her words: \"{rule.get('words', '')}\" (welcome call, {int(src['secs']) // 60}:{int(src['secs']) % 60:02d}).", rule_id="P-QH-01", refs=[{"kind": "member", "id": person["id"]}, {"kind": "policy", "id": "P-QH-01"}], mode="acted_alone", source={"kind": src["kind"], "ref": src["ref"], "secs": src["secs"], "quote": rule.get("words", "")}, trace_id=run.trace_id))
                await _emit(svc, run, f"Quiet hours · after 9:30 PM, no calls (her words, welcome call {int(src['secs']) // 60}:{int(src['secs']) % 60:02d})", "decision")
            people = spec["blueprint"]["people"]
            plan = plan_capabilities(spec, signals=opts.signals)
            crit = await critique(plan, people, village_id=village_id, services=svc, llm=llm if opts.mode != "fixture" else None, trace_id=run.trace_id)
            run.critique = {"applied": crit.applied, "refused": crit.refused, "assumptions": crit.assumptions, "source": crit.source}
            run.capabilities = plan.as_dict()
            for row in capability_rows(village_id, plan, people, trace_id=run.trace_id):
                await svc.record_decision(row)
                await _emit(svc, run, row["text"], "decision")
            meds = input.medications
            if meds is None:
                meds = sorted({m["name"] for m in record.get("medications", []) if m.get("status") != "superseded"}) if record else []
            t_r = time.perf_counter()
            (spec, roles), _ = await asyncio.gather(
                render_views(spec, village_id=village_id, services=svc, llm=llm if opts.mode != "fixture" else None, plan=plan, per_role_s=opts.per_role_s, total_s=opts.total_s, trace_id=run.trace_id),
                founder_work(spec, run, svc, opts, meds),
            )
            run.timings["render_ms"] = int((time.perf_counter() - t_r) * 1000)
            run.timings["render_role_ms"] = {r: v.ms for r, v in roles.items()}
            run.roles = roles
            spec = ensure_chat(spec)
            for person in people:
                chans = ", ".join(spec["channels"].get(person["id"], []))
                await svc.record_decision(builder_decision(village_id, f"{person['name'].split()[0]}: {person['view'] or 'phone-only'} through {chans}.", refs=[{"kind": "member", "id": person["id"]}], mode="acted_alone", trace_id=run.trace_id))
            report = validate_spec(spec)
            if not report.ok:  # never ship an invalid draft: whole template
                await svc.record_decision(templates.template_decision(village_id, "all", report.errors[0][:200]))
                spec = templates.spec(kind, village_id=village_id, status="draft")
            run.spec = spec
            await svc.store_spec(village_id, spec, status="draft")
            _set_state(run, "draft")
            await svc.broadcast_control(village_id, frames.blueprint(village_id, "done", [{"rev": spec.get("rev", 1)}], run.trace_id))
            await _emit(svc, run, f"Draft ready: {len(spec['views'])} views, {len(people)} people, {len(run.ledger)} things checked.", "plan")
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            root.set("error", run.error)
            raise
        finally:
            run.total_ms = int((time.perf_counter() - t0) * 1000)
            run.timings["total_ms"] = run.total_ms
    return run


def demo_options(**kw: Any) -> FoundingOptions:
    """Model-off demo wiring: recorded DailyMed + scripted consent answer (both mocked, labelled)."""
    return FoundingOptions(dialer=ScriptedConsentDialer(answers=deepcopy(REYES_SCRIPT)), dailymed="fixture", **kw)


def answer(village_id: str, text: str) -> bool:
    session = SESSIONS.get(village_id)
    if session is None:
        return False
    session.answers.put_nowait(text)
    return True
