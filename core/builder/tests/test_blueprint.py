from __future__ import annotations

import asyncio
import json
from pathlib import Path

from core.builder.blueprint import StreamParser, heuristic_blueprint, stream_blueprint
from core.builder.llm_port import FakeLLM
from core.builder.paths import DATA
from core.builder.services_stub import MemoryServices
from core.builder.validate import contract_errors

DELTAS = Path(__file__).parent / "data" / "reyes_blueprint_deltas.jsonl"
ANA = json.loads((DATA / "villages" / "reyes_family.json").read_text())["demo_spoken_description"]["text"]


def _deltas() -> list[str]:
    return [json.loads(line)["partial_json"] for line in DELTAS.read_text().splitlines() if line.strip()]


def _run(llm, text=ANA, kind="care"):
    svc = MemoryServices()
    timings: dict = {}
    bp = asyncio.run(stream_blueprint(text, "v_test", svc, kind, llm=llm, timings=timings))
    return bp, svc.frames, timings


def test_recorded_stream_emits_findings_in_order_without_invented_people() -> None:
    bp, frames, timings = _run(FakeLLM(deltas=_deltas()))
    for f in frames:
        assert not contract_errors(f, "ws_messages.schema.json#/$defs/control"), f
    reasoning = [f["payload"]["text"] for f in frames if f["kind"] == "reasoning"]
    assert len(reasoning) >= 5
    assert reasoning[0].startswith("Group type:")
    first_need = next(i for i, t in enumerate(reasoning) if t.startswith("Need "))
    last_person = max(i for i, t in enumerate(reasoning) if t.startswith("Found "))
    assert last_person < first_need
    assert {p["name"] for p in bp["people"]} <= {"You", "Mom", "Marco", "Ana", "Carmen"}
    assert any(p["name"] == "Marco" for p in bp["people"])
    assert len(bp["questions"]) <= 2
    for need in bp["needs"]:
        s = need["source_span"]
        assert s is None or 0 <= s["start"] < s["end"] <= len(ANA)
    assert frames[-1]["kind"] == "counter" and frames[-1]["payload"]["name"] == "people_found"
    assert timings["blueprint_ttft_ms"] is not None


def test_invented_person_is_dropped() -> None:
    raw = json.loads("".join(_deltas()))
    raw["people"].append({**raw["people"][-1], "id": "m_rosa", "name": "Rosa", "relation": "neighbor"})
    text = json.dumps(raw)
    deltas = [text[i : i + 37] for i in range(0, len(text), 37)]
    bp, frames, _ = _run(FakeLLM(deltas=deltas))
    assert "Rosa" not in {p["name"] for p in bp["people"]}
    assert bp["dropped_people"] == ["Rosa"]
    assert not any("Found Rosa" in f["payload"].get("text", "") for f in frames if f["kind"] == "reasoning")


def test_partial_parser_waits_for_complete_items() -> None:
    p = StreamParser()
    assert p.feed('{"kind": "care", "people": [{"id": "m_a", "name": "An') == [("kind", "care")]
    assert p.feed('a"}, {"id": "m_b"') == [("people", {"id": "m_a", "name": "Ana"})]
    _, tail = p.finish()
    assert tail == [] or tail[0][0] == "people"


def test_heuristic_model_off() -> None:
    bp = heuristic_blueprint(ANA)
    assert [p["id"] for p in bp["people"]] == ["m_carmen", "m_ana", "m_marco"]
    assert [n["id"] for n in bp["needs"]] == ["n_evening_pills", "n_scam_calls", "n_turns"]
    assert bp["questions"] == ["Anyone else who helps?"]
    assert "m_lucia" in [p["id"] for p in heuristic_blueprint(ANA, answers="Lucía, my sister, helps from Philadelphia")["people"]]
