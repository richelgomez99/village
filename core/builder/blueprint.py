"""Blueprint first (D9 speed 1): streamed `extract_blueprint`, one `control{reasoning}` frame per
finding as soon as it is complete in the partial JSON, ≤2 follow-up questions, no invented people."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import jiter

from . import frames
from .mapping import normalize_profile, role_for_person
from .paths import FIXTURES
from .spans import span
from .tools import all_tools

STAGES = ["kind", "people", "edges", "needs", "rules", "life_areas", "questions"]
RELATION_ALIASES = {
    "mother": ["mom", "mother", "mama", "mamá", "ma", "mum", "abuela"],
    "father": ["dad", "father", "papa", "papá", "pop"],
    "grandmother": ["grandma", "granny", "abuela", "nana"],
    "grandfather": ["grandpa", "abuelo"],
}
FIRST_PERSON = re.compile(r"\b(i|me|my|i'm|i've)\b", re.I)

SYSTEM = """You extract a founding blueprint for Village, software built for one group of people.
Call extract_blueprint exactly once. Rules:
- People: ONLY people the speaker names or clearly refers to ("Mom", "my brother Sam", "I"). Never invent names.
  The speaker ("I") is the coordinator; if unnamed, name them "You". A referred-to person without a name keeps the
  word used ("Mom"). Ids: m_<firstname> for care villages, b_<name> for blocks, lowercase ascii.
- Order the output: kind, people, edges, needs, rules, life_areas, questions.
- Needs: each with source_span = [start, end) character offsets of the words in the description that state it.
- Profiles: only what the words support; otherwise memory/tech_comfort "unknown".
- consent.ai_calls / app_prompts = null unless stated.
- questions: at most 2 short follow-ups that would change the software (e.g. "Anyone else who helps?").
- care = family caring for someone; block = neighbors/building/crisis group."""


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def mentioned(person: dict[str, Any], text: str, allowed_ids: set[str] = frozenset()) -> bool:
    if person.get("id") in allowed_ids:
        return True
    hay = _fold(text)
    words = set(re.findall(r"[a-z]+", hay))
    tokens = [t for t in re.findall(r"[a-z]+", _fold(person.get("name", "") + " " + person.get("short_name", ""))) if len(t) > 1]
    if any(t in words for t in tokens if t not in {"you", "the", "mrs", "mr", "ms"}):
        return True
    for alias in RELATION_ALIASES.get(_fold(person.get("relation", "")), []):
        if _fold(alias) in words:
            return True
    return False


def sanitize(bp: dict[str, Any], description: str, *, allowed_ids: set[str] = frozenset()) -> tuple[dict[str, Any], list[str]]:
    """Drop invented people (and edges to them), clamp spans, ≤2 questions, contract enums."""
    out = deepcopy(bp)
    dropped: list[str] = []
    people = []
    speaker_used = False
    for p in out.get("people", []):
        if mentioned(p, description, allowed_ids):
            people.append(p)
        elif p.get("role") == "coordinator" and not speaker_used and FIRST_PERSON.search(description):
            speaker_used = True  # the speaker ("I") is the coordinator
            people.append(p)
        else:
            dropped.append(p.get("name", p.get("id", "?")))
    kind = out.get("kind", "care")
    for p in people:
        p["profile"] = normalize_profile(p.get("profile", {}))
        p["view"] = role_for_person(kind, {**p, "view": None})
    ids = {p["id"] for p in people}
    out["people"] = people
    out["edges"] = [e for e in out.get("edges", []) if e.get("from") in ids and e.get("to") in ids]
    n = len(description)
    for need in out.get("needs", []):
        need["subject_member_ids"] = [m for m in need.get("subject_member_ids", []) if m in ids]
        s = _span(need.get("source_span"))
        need["source_span"] = s if s and 0 <= s["start"] < s["end"] <= n else None
    for area in out.get("life_areas", []):
        if "trusted_contacts" in area:
            area["trusted_contacts"] = [m for m in area["trusted_contacts"] if m in ids]
    out["questions"] = list(out.get("questions", []))[:2]
    return out, dropped


@dataclass
class StreamParser:
    """Feed `partial_json` deltas; `feed()` returns findings `(stage, item)` that are complete."""

    buf: str = ""
    emitted: dict[str, int] = field(default_factory=lambda: {s: 0 for s in STAGES})

    def _parse(self) -> dict[str, Any]:
        if not self.buf.strip():
            return {}
        try:
            return jiter.from_json(self.buf.encode(), partial_mode="trailing-strings") or {}
        except ValueError:
            return {}

    def feed(self, delta: str) -> list[tuple[str, Any]]:
        self.buf += delta
        return self._collect(self._parse(), final=False)

    def finish(self) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
        try:
            data = json.loads(self.buf) if self.buf.strip() else {}
        except json.JSONDecodeError:
            data = self._parse()
        return data, self._collect(data, final=True)

    def _collect(self, data: dict[str, Any], final: bool) -> list[tuple[str, Any]]:
        out: list[tuple[str, Any]] = []
        keys = list(data.keys())
        for stage in STAGES:
            if stage not in data:
                continue
            closed = final or keys.index(stage) < len(keys) - 1  # a later key started → this one is done
            value = data[stage]
            if stage == "kind":
                if closed and not self.emitted["kind"]:
                    out.append(("kind", value))
                    self.emitted["kind"] = 1
                continue
            if not isinstance(value, list):
                continue
            ready = len(value) if closed else max(0, len(value) - 1)
            for i in range(self.emitted[stage], ready):
                out.append((stage, value[i]))
            self.emitted[stage] = max(self.emitted[stage], ready)
        return out


def _span(s: Any) -> dict[str, int] | None:
    if isinstance(s, (list, tuple)) and len(s) == 2:
        return {"start": int(s[0]), "end": int(s[1])}
    if isinstance(s, dict) and "start" in s and "end" in s:
        return {"start": int(s["start"]), "end": int(s["end"])}
    return None


def finding_text(stage: str, item: Any, description: str) -> tuple[str, str]:
    if stage == "kind":
        return "plan", f"Group type: {'family care village' if item == 'care' else 'block / neighbors village'}."
    if stage == "people":
        reason = item.get("reason", "")
        return "note", f"Found {item.get('name')} ({item.get('relation', item.get('role'))}, {item.get('role')}). {reason}"
    if stage == "needs":
        s = _span(item.get("source_span"))
        quote = f' "{description[s["start"]:s["end"]]}"' if s and s["end"] <= len(description) else ""
        return "note", f"Need {item.get('id')}: {item.get('text')}.{quote}"
    if stage == "life_areas":
        return "note", f"Life area {item.get('id')}: {', '.join(item.get('need_ids', []))}."
    if stage == "rules":
        return "decision", f"Rule on: {item}."
    if stage == "edges":
        return "note", f"{item.get('from')} → {item.get('to')}: {item.get('label', item.get('kind'))}."
    return "note", f"Question: {item}"


def heuristic_blueprint(description: str, kind: str = "care", answers: str = "") -> dict[str, Any]:
    """Model-off blueprint from the kind's fixture, keeping only what the words support."""
    from .registry import fixture_path

    fx = json.loads(fixture_path(kind).read_text(encoding="utf-8"))
    bp = fx["blueprint"]
    text = description + ("\n" + answers if answers else "")
    tool_people = []
    for p in bp["people"]:
        prof = p.get("profile", {})
        tp = {
            "id": p["id"], "name": p["name"], "relation": p.get("relation", ""), "role": p["role"], "view": p.get("view"),
            "profile": {k: prof[k] for k in ("lang", "memory", "tech_comfort", "quiet_hours") if k in prof}
            | {"preferred_channels": prof.get("preferred_channels") or ["app"]},
            "consent": {"ai_calls": p.get("consent", {}).get("ai_calls"), "app_prompts": p.get("consent", {}).get("app_prompts")},
            "reason": (p.get("notes") or "")[:200],
        }
        if p.get("short_name"):
            tp["short_name"] = p["short_name"]
        tool_people.append(tp)
    needs = []
    fx_text = bp["description"]["text"]
    for n in bp["needs"]:
        s = n.get("source_span")
        if not s:
            continue
        quote = fx_text[s["start"]:s["end"]]
        at = description.find(quote)
        if at < 0:
            continue
        needs.append({k: n[k] for k in ("id", "text", "priority", "domain", "life_area", "subject_member_ids") if k in n} | {"source_span": {"start": at, "end": at + len(quote)}})
    need_ids = {n["id"] for n in needs}
    areas = []
    for a in bp["life_areas"]:
        ids = [i for i in a["need_ids"] if i in need_ids]
        if ids:
            areas.append({"id": a["id"], "label": a["label"][:40], "need_ids": ids, "rules": a.get("rules", [])} | ({"trusted_contacts": a["trusted_contacts"]} if a.get("trusted_contacts") else {}))
    bp_out = {
        "kind": kind,
        "people": tool_people,
        "edges": [],
        "needs": needs,
        "rules": [r for r in bp.get("rules", [])],
        "life_areas": areas,
        "questions": [],
    }
    clean, _ = sanitize(bp_out, text)
    if kind == "care" and not any(p["role"] == "caregiver" for p in clean["people"][2:]) or len(clean["people"]) < 4:
        clean["questions"] = ["Anyone else who helps?"] if kind == "care" else ["Who on the block has a phone but no app?"]
    return clean


async def stream_blueprint(
    description: str,
    village_id: str,
    services: Any,
    kind: str | None = None,
    *,
    llm: Any | None = None,
    answers: str = "",
    allowed_ids: set[str] = frozenset(),
    trace_id: str | None = None,
    timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timings = timings if timings is not None else {}
    t0 = time.perf_counter()
    text = description + (f"\nFollow-up answers: {answers}" if answers else "")
    kind_hint = kind or ("block" if re.search(r"\b(block|building|blackout|neighbors?)\b", description, re.I) else "care")

    async def emit(stage: str, item: Any) -> None:
        k, line = finding_text(stage, item, description)
        await services.broadcast_control(village_id, frames.reasoning(village_id, line, k, trace_id))
        if stage in ("people", "needs", "life_areas"):
            await services.broadcast_control(village_id, frames.blueprint(village_id, stage, [item], trace_id))
        elif stage in ("rules", "kind", "questions"):
            key = {"rules": "rule", "kind": "kind", "questions": "question"}[stage]
            await services.broadcast_control(village_id, frames.blueprint(village_id, stage, [{key: item}], trace_id))

    with span("builder.blueprint", "CHAIN", **{"session.id": f"village-{village_id}", "graph.node.id": "blueprint", "graph.node.parent_id": "found"}) as sp:
        if llm is None:
            bp = heuristic_blueprint(description, kind_hint, answers)
            timings["blueprint_mode"] = "heuristic"
            for stage in STAGES:
                items = [bp[stage]] if stage == "kind" else bp.get(stage, [])
                for item in items:
                    if timings.get("blueprint_ttft_ms") is None:
                        timings["blueprint_ttft_ms"] = int((time.perf_counter() - t0) * 1000)
                    await emit(stage, item)
            dropped: list[str] = []
        else:
            tool = all_tools()["extract_blueprint"]
            parser = StreamParser()
            pending: list[tuple[str, Any]] = []
            timings["blueprint_mode"] = "model"
            stream: AsyncIterator[str] = llm.stream_tool(system=SYSTEM, messages=[{"role": "user", "content": f"Village kind hint: {kind_hint}\nDescription:\n{text}"}], tool=tool, max_tokens=4096)
            people_seen: list[dict[str, Any]] = []
            async for delta in stream:
                if timings.get("blueprint_ttft_ms") is None:
                    timings["blueprint_ttft_ms"] = int((time.perf_counter() - t0) * 1000)
                for stage, item in parser.feed(delta):
                    pending.append((stage, item))
                for stage, item in pending:
                    if stage == "people" and not _keep_person(item, text, allowed_ids, people_seen):
                        continue
                    if stage == "questions" and parser.emitted["questions"] > 2:
                        continue
                    await emit(stage, item)
                pending = []
            raw, tail = parser.finish()
            for stage, item in tail:
                if stage == "people" and not _keep_person(item, text, allowed_ids, people_seen):
                    continue
                await emit(stage, item)
            bp, dropped = sanitize(raw, text, allowed_ids=allowed_ids)
            bp.setdefault("kind", kind_hint)
        for name in dropped:
            await services.broadcast_control(village_id, frames.reasoning(village_id, f"Dropped {name}: not in what you said.", "decision", trace_id))
        await services.broadcast_control(village_id, frames.counter("people_found", len(bp["people"]), "people found"))
        timings["blueprint_ms"] = int((time.perf_counter() - t0) * 1000)
        sp.set("people", len(bp["people"]))
        sp.set("dropped", dropped)
    bp["dropped_people"] = dropped
    return bp


def _keep_person(item: dict[str, Any], text: str, allowed: set[str], seen: list[dict[str, Any]]) -> bool:
    if mentioned(item, text, allowed):
        seen.append(item)
        return True
    if item.get("role") == "coordinator" and FIRST_PERSON.search(text) and not any(p.get("_speaker") for p in seen):
        seen.append({**item, "_speaker": True})
        return True
    return False
