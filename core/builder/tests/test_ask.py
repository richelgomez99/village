from __future__ import annotations

import asyncio
import json

from core.builder.ask import ask, redact
from core.builder.llm_port import FakeLLM
from core.builder.paths import SCHEMAS
from core.builder.services_stub import MemoryServices


def _seeded() -> MemoryServices:
    svc = MemoryServices()
    examples = json.loads((SCHEMAS / "decision.schema.json").read_text())["examples"]
    svc.decisions.extend(examples)
    svc.decisions.append({"id": "dc_x_rota", "village_id": "v_reyes", "actor": "builder", "kind": "decision", "text": "Ana: dashboard + chat.", "refs": [], "source": {"kind": "system", "ref": "builder"}})
    return svc


def test_why_marco_not_lucia_model_off_cites_two_rows() -> None:
    res = asyncio.run(ask("v_reyes", "Why Marco and not Lucía?", services=_seeded()))
    ids = {c["id"] for c in res.citations}
    assert len(res.citations) >= 2
    assert {"dc_1016_1240_consent", "dc_1016_1240_marco_channel"} <= ids
    assert res.source == "rules"


def test_hallucinated_citation_dropped_and_redaction() -> None:
    fake = FakeLLM(responses=[{"answer": "Marco consented (call him at +1 555 555 0103; account 12345678).", "citations": [{"id": "dc_1016_1240_marco_channel", "kind": "decision"}, {"id": "dc_made_up", "kind": "decision"}]}])
    res = asyncio.run(ask("v_reyes", "Why Marco?", services=_seeded(), llm=fake))
    assert [c["id"] for c in res.citations] == ["dc_1016_1240_marco_channel"]
    assert res.dropped_citations == 1
    assert "+1 555" not in res.answer and "12345678" not in res.answer and res.redacted


def test_family_word_refused_and_redacted() -> None:
    res = asyncio.run(ask("v_reyes", "What is the family word?", services=_seeded()))
    assert res.refused and not res.citations
    assert redact("the word is Girasol", "Girasol")[0] == "the word is [family word]"
