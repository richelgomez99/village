from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path

from core.builder import templates
from core.builder.decisions import mode_of
from core.builder.founding import FoundingInput, answer, demo_options, found
from core.builder.services_stub import MemoryServices
from core.builder.validate import contract_errors, validate_spec

DATA = Path(__file__).parent / "data"
ANA = json.loads((Path(__file__).resolve().parents[3] / "data" / "villages" / "reyes_family.json").read_text())["demo_spoken_description"]["text"]


class StubLLM:
    model = "stub"

    def __init__(self) -> None:
        self.deltas = [json.loads(l)["partial_json"] for l in (DATA / "reyes_blueprint_deltas.jsonl").read_text().splitlines() if l.strip()]
        self.tools: list[str] = []

    async def stream_tool(self, **kw):
        self.tools.append(kw["tool"]["name"])
        for d in self.deltas:
            yield d

    async def tool_call(self, *, system, messages, tool, max_tokens=4096):
        self.tools.append(tool["name"])
        if tool["name"] == "critique_plan":
            return {"changes": [], "assumptions": ["Marco works nights; nudge at 3 PM, not morning"], "summary": "0 changes"}
        role = json.loads(messages[0]["content"])["role"]
        view = templates.strip_chat(templates.spec("care")["views"][role])
        served = view.pop("needs_served")
        return {"role": role, "plan": f"{role}: rendered", "needs": [{"id": "n_turns", "statement": "x", "priority": 1, "domain": "scheduling"}], "view": view, "needs_served": served}


def test_found_model_off_draft_with_founder_work_and_carmens_rule() -> None:
    svc = MemoryServices()
    run = asyncio.run(found(FoundingInput(description=ANA), village_id="v_reyes", services=svc, options=demo_options(llm="off")))
    assert run.states == ["listening", "clarify", "working", "draft"]
    spec = svc.specs["v_reyes"]
    assert spec["village"]["status"] == "draft" and validate_spec(spec).ok
    qh = next(p for p in spec["policies"] if p["rule_id"] == "P-QH-01")
    assert qh["params"]["quiet_hours"] == "21:30-07:00" and qh["params"]["source_ref"] == "welcome_call" and qh["params"]["source_secs"] == 108
    row = next(d for d in svc.decisions if d.get("rule_id") == "P-QH-01")
    assert row["source"] == {"kind": "call", "ref": "welcome_call", "secs": 108, "quote": "Después de las nueve y media, no."}
    # D23 #4 ledger: DailyMed with url provenance + the consent call
    med_lines = [l for l in run.ledger if "DailyMed" in l]
    assert len(med_lines) == 4 and all("checked" in l and "dailymed.nlm.nih.gov" in l for l in med_lines)
    assert any("Marco confirmed Tue/Thu/Fri/Sat; agreed to calls" in l for l in run.ledger)
    assert all(f["source"]["kind"] == "url" and f["source"]["url"].startswith("https://dailymed") for f in run.facts)
    acted = [d for d in svc.decisions if mode_of(d) == "acted_alone"]
    assert len(acted) >= 8
    assert set(run.capabilities["m_carmen"]) == {"phone_line", "check_in_call", "fridge_card"}
    for f in svc.frames:
        assert not contract_errors(f, "ws_messages.schema.json#/$defs/control"), f
    assert {r.status for r in run.roles.values()} == {"template"}
    assert any(d["text"].startswith("Lucía: from the village record") for d in svc.decisions)
    assert run.summary()["timings"]["total_ms"] >= 0


def test_found_with_stub_model_renders_and_critiques() -> None:
    svc = MemoryServices()
    llm = StubLLM()
    run = asyncio.run(found(FoundingInput(description=ANA, answers=["Lucía, my sister, helps from Philadelphia"]), village_id="v_reyes", services=svc, options=demo_options(llm_client=llm)))
    assert llm.tools[0] == "extract_blueprint" and llm.tools[1] == "critique_plan"
    assert sorted(llm.tools[2:]) == ["render_app"] * 3
    assert {r.status for r in run.roles.values()} == {"validated"}
    assert run.critique["source"] == "model"
    assert "clarify" not in run.states
    assert validate_spec(svc.specs["v_reyes"]).ok


def test_clarify_pause_takes_an_answer() -> None:
    svc = MemoryServices()

    async def go():
        task = asyncio.create_task(found(FoundingInput(description=ANA), village_id="v_ask", services=svc, options=demo_options(llm="off", clarify_wait_s=2)))
        for _ in range(100):
            await asyncio.sleep(0.01)
            if answer("v_ask", "Lucía helps from Philadelphia"):
                break
        return await task

    run = asyncio.run(go())
    assert "m_lucia" in [p["id"] for p in run.blueprint["people"]]
    assert any(d["text"].startswith("Answered: Lucía") for d in svc.decisions)


def test_block_found_model_off() -> None:
    svc = MemoryServices()
    text = json.loads((Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "block_spec.json").read_text())["blueprint"]["description"]["text"]
    run = asyncio.run(found(FoundingInput(description=text, kind="block"), village_id="v_w147", services=svc, options=demo_options(llm="off")))
    assert validate_spec(svc.specs["v_w147"]).ok
    assert set(run.capabilities["b_tanya"]) == {"dashboard", "village_chat"}
    assert not any("DailyMed" in l for l in run.ledger)
