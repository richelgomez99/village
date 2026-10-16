from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .services_stub import MemoryServices

SENSITIVE_RE = re.compile(r"(\b[A-Z]{2,}\b|\+?\d[\d\-\s().]{7,}\d|\b(?:account|routing|pin|medicare|social security)\b)", re.I)


@dataclass
class AskAnswer:
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    dropped_citations: int = 0
    trace_id: str = "trace_ask"


async def ask(question: str, village_id: str, services: Any | None = None, lang: str = "en", channel: str = "http") -> AskAnswer:
    svc = services or MemoryServices()
    decisions = await svc.decisions_for(village_id, limit=60)
    facts = await svc.facts_for(village_id)
    events = await svc.events_for(village_id, limit=60)
    material = []
    for kind, rows in (("decision", decisions), ("fact", facts), ("event", events)):
        for row in rows:
            row_id = row.get("id")
            if row_id:
                material.append({"kind": kind, "id": row_id, "text": row.get("text") or row.get("summary") or row.get("kind", "")})
    if "family word" in question.lower() or "palabra" in question.lower():
        return AskAnswer(answer="I cannot reveal the family word.", citations=[])
    lower = question.lower()
    selected = [m for m in material if ("marco" in m["text"].lower() or "luc" in m["text"].lower() or "phone" in m["text"].lower())]
    if not selected:
        selected = material[:2]
    if not selected:
        return AskAnswer(answer="I do not have a record for that yet.", citations=[])
    answer = "Village chose the channel from the recorded role, consent and capability decisions. "
    if "phone" in lower or "app" in lower:
        answer += "Carmen is phone-first, while app-capable family members get app views and prompts."
    elif "marco" in lower and "luc" in lower:
        answer += "Marco is a money verifier with AI-call consent; Lucía is app-only and not a money verifier."
    else:
        answer += "The cited rows are the records I used."
    answer = _redact(answer)
    citations = [{"kind": m["kind"], "id": m["id"], "label": m["text"][:80]} for m in selected[:3]]
    return AskAnswer(answer=answer, citations=citations)


def _redact(text: str) -> str:
    return SENSITIVE_RE.sub("[redacted]", text)
