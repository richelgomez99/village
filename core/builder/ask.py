"""Explainer (`POST /villages/{id}/ask`, "@Village why…"): answer from the village's own records with
citations. Material = decisions + facts + events (cap 60) → `cite_answer` → citation validation (ids
not in the material are dropped) → redaction (family word, phone numbers, account numbers)."""
from __future__ import annotations

import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any

from .services_stub import MemoryServices
from .spans import span
from .tools import all_tools

CAP = 60
PHONE_RE = re.compile(r"\+?\d[\d\-\s().]{8,}\d")
ACCOUNT_RE = re.compile(r"\b(?:acct|account|routing|card|iban|ssn)\b[^.\n]{0,20}?\d{4,}|\b\d{8,}\b", re.I)
FAMILY_WORD_Q = re.compile(r"family word|palabra|code ?word|contraseña|password", re.I)
STOP = {"why", "does", "did", "the", "and", "not", "get", "gets", "a", "an", "is", "of", "to", "for", "what", "who", "how", "her", "his", "she", "he", "it", "on", "in", "village"}

SYSTEM = """You are Village's Explainer. Answer the question using ONLY the material rows given (decisions, facts,
events). Cite the ids of the rows you used (2-4 when possible). Never invent ids, never mention a family word,
phone numbers or account numbers. Plain words, at most 3 sentences, in the asker's language. Call cite_answer once."""


@dataclass
class AskAnswer:
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    dropped_citations: int = 0
    redacted: bool = False
    refused: bool = False
    trace_id: str = ""
    source: str = "rules"

    def as_dict(self) -> dict[str, Any]:
        return {"answer": self.answer, "citations": self.citations, "dropped_citations": self.dropped_citations, "redacted": self.redacted, "refused": self.refused, "trace_id": self.trace_id, "source": self.source}


def _fold(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c))


def _row_text(kind: str, row: dict[str, Any]) -> str:
    if kind == "decision":
        return row.get("text", "")
    if kind == "fact":
        return f"{row.get('entity', '')} {row.get('key', '')}: {row.get('value', '')}"
    payload = row.get("payload") or {}
    return f"{row.get('kind', '')} {json.dumps(payload, ensure_ascii=False)[:200]}"


async def gather_material(village_id: str, services: Any) -> list[dict[str, Any]]:
    decisions = await services.decisions_for(village_id, limit=CAP)
    facts = await services.facts_for(village_id) if hasattr(services, "facts_for") else []
    events = await services.events_for(village_id, limit=CAP) if hasattr(services, "events_for") else []
    material: list[dict[str, Any]] = []
    for kind, rows in (("decision", decisions), ("fact", facts), ("event", events)):
        for row in rows:
            rid = row.get("id") or row.get("key")
            if rid:
                material.append({"kind": kind, "id": str(rid), "text": _row_text(kind, row)[:400], "rule_id": row.get("rule_id")})
    return material[-CAP:] if len(material) > CAP else material


def redact(text: str, family_word: str | None = None) -> tuple[str, bool]:
    out = text
    if family_word and len(family_word) >= 2 and not family_word.startswith("["):
        out = re.sub(re.escape(family_word), "[family word]", out, flags=re.I)
    out = PHONE_RE.sub("[phone]", out)
    out = ACCOUNT_RE.sub("[account]", out)
    return out, out != text


def _family_word(spec: dict[str, Any] | None) -> str | None:
    for p in (spec or {}).get("printables", []):
        if p.get("kind") == "fridge_card" and p.get("family_word"):
            return p["family_word"]
    return None


def _rank(question: str, material: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = {w for w in re.findall(r"[a-z]+", _fold(question)) if w not in STOP and len(w) > 2}
    scored = []
    for i, m in enumerate(material):
        hay = _fold(m["text"])
        s = sum(1 for t in terms if t in hay)
        if s:
            scored.append((s, -i, m))
    scored.sort(key=lambda x: (-x[0], x[1]))
    ranked = [m for _, _, m in scored]
    # cover every named term first ("why A and not B" needs a row for each person)
    picked: list[dict[str, Any]] = []
    for t in sorted(terms):
        hit = next((m for m in ranked if t in _fold(m["text"]) and m not in picked and _fold(m["text"]).lstrip().startswith(t)), None)
        hit = hit or next((m for m in ranked if t in _fold(m["text"]) and m not in picked), None)
        if hit:
            picked.append(hit)
    return picked + [m for m in ranked if m not in picked]


def rules_answer(question: str, material: list[dict[str, Any]]) -> dict[str, Any]:
    top = _rank(question, material)[:3]
    if not top:
        return {"answer": "I don't have a record that explains that yet.", "citations": []}
    body = " ".join(m["text"].rstrip(".") + "." for m in top[:2])
    return {"answer": f"From the village's records: {body}"[:1200], "citations": [{"id": m["id"], "kind": m["kind"], "label": m["text"][:60]} for m in top]}


async def ask(
    village_id: str,
    question: str,
    *,
    services: Any | None = None,
    llm: Any | None = None,
    lang: str = "en",
    channel: str = "http",
    spec: dict[str, Any] | None = None,
) -> AskAnswer:
    svc = services or MemoryServices()
    trace_id = uuid.uuid4().hex
    if spec is None and hasattr(svc, "get_spec"):
        spec = await svc.get_spec(village_id)
    family_word = _family_word(spec)
    with span("builder.ask", "AGENT", **{"session.id": f"village-{village_id}", "graph.node.id": "ask", "channel": channel, "input.value": question[:300]}) as sp:
        if FAMILY_WORD_Q.search(question):
            sp.set("refused", True)
            return AskAnswer(answer="I can't share the family word here. The coordinator has it on the fridge card.", refused=True, trace_id=trace_id)
        material = await gather_material(village_id, svc)
        safe_material = [{**m, "text": redact(m["text"], family_word)[0]} for m in material]
        source = "rules"
        if llm is not None:
            try:
                out = await llm.tool_call(system=SYSTEM, messages=[{"role": "user", "content": json.dumps({"question": question, "lang": lang, "material": safe_material}, ensure_ascii=False)}], tool=all_tools()["cite_answer"], max_tokens=800)
                source = "model"
            except Exception:
                out = rules_answer(question, safe_material)
        else:
            out = rules_answer(question, safe_material)
        known = {(m["kind"], m["id"]) for m in material}
        known_ids = {m["id"]: m["kind"] for m in material}
        cites, dropped = [], 0
        for c in out.get("citations", []):
            cid = c.get("id")
            if (c.get("kind"), cid) in known or cid in known_ids:
                cites.append({"id": cid, "kind": c.get("kind") if (c.get("kind"), cid) in known else known_ids[cid], "label": c.get("label", "")[:80]})
            else:
                dropped += 1
        answer, red = redact(str(out.get("answer", "")), family_word)
        sp.set("citations", len(cites))
        sp.set("dropped_citations", dropped)
        sp.set("output.value", answer[:500])
    return AskAnswer(answer=answer, citations=cites, dropped_citations=dropped, redacted=red, trace_id=trace_id, source=source)
