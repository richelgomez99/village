from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path

from core.builder import templates
from core.builder.decisions import mode_of
from core.builder.founding import SESSIONS, FoundingInput, answer, demo_options, found, replay_input
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


def test_found_model_off_opener_only() -> None:
    svc = MemoryServices()
    run = asyncio.run(found(FoundingInput(description=ANA), village_id="v_reyes", services=svc, options=demo_options(llm="off")))
    assert run.states == ["listening", "clarify", "working", "draft", "review"]
    spec = svc.specs["v_reyes"]
    assert spec["village"]["status"] == "draft" and validate_spec(spec).ok
    qh = next(p for p in spec["policies"] if p["rule_id"] == "P-QH-01")
    assert qh["params"]["quiet_hours"] == "21:30-07:00" and qh["params"]["source_ref"] == "welcome_call" and qh["params"]["source_secs"] == 108
    row = next(d for d in svc.decisions if d.get("rule_id") == "P-QH-01")
    assert row["source"] == {"kind": "call", "ref": "welcome_call", "secs": 108, "quote": "Después de las nueve y media, no."}
    med_lines = [l for l in run.ledger if "DailyMed" in l]
    assert len(med_lines) == 4 and all(" · done · " in l and "dailymed.nlm.nih.gov" in l for l in med_lines)
    assert any("Marco confirmed Tue/Thu/Fri/Sat · yes to calls" in l for l in run.ledger)
    assert all(f["source"]["kind"] == "url" for f in run.facts)
    assert all(d.get("mode") in ("acted_alone", "asked_human", "refused") for d in svc.decisions)
    assert set(run.capabilities["m_carmen"]) == {"phone_line", "check_in_call", "fridge_card"}
    for f in svc.frames:
        if f["type"] == "patch":
            assert not contract_errors(f, "ws_messages.schema.json#/$defs/patch"), f
        elif not (f["kind"] == "blueprint" and f["payload"]["stage"] == "will_build"):  # stage pending in the contract
            assert not contract_errors(f, "ws_messages.schema.json#/$defs/control"), f
    ledger_ids = [f["payload"]["id"] for f in svc.frames if f.get("kind") == "ledger"]
    assert len(ledger_ids) > len(set(ledger_ids))  # rows updated in place
    assert {r.status for r in run.roles.values()} == {"template"}


def _replay(**kw):
    inp, answers = replay_input()
    svc = MemoryServices()
    run = asyncio.run(found(inp, village_id="v_reyes", services=svc, options=demo_options(llm="off", replay=answers, **kw)))
    return run, svc


def test_full_intake_replay_matches_the_spec_of_record() -> None:
    run, svc = _replay()
    meters = [int(t["meter"].split()[0]) for t in run.turns]
    assert meters == [2, 2, 3, 4, 5, 6, 6, 7, 8, 9, 10]
    assert run.turns[0]["question"].startswith("Who else is in this besides you and Marco")
    assert run.turns[1]["question"] == "What is Marco's week like? When can he actually be there?"
    assert run.turns[6]["answer"] == "[family word] · set"
    assert run.family_word == "Pavo"
    blob = json.dumps(svc.frames, ensure_ascii=False) + json.dumps(svc.decisions, ensure_ascii=False) + json.dumps(svc.specs, ensure_ascii=False)
    assert "Pavo" not in blob and "Pavo" not in json.dumps(run.summary(), ensure_ascii=False)
    led = "\n".join(run.ledger)
    assert "every night has a name. Thursday is Marco." in led
    assert led.count("DailyMed: ") == 4 and "high-alert, bleeding" in led
    assert "Marco confirmed Tue/Thu/Fri/Sat · yes to calls" in led
    assert "lisinopril 10 mg (was 5 mg, Oct 3, Dr. Park)" in led
    spec = svc.specs["v_reyes"]
    assert validate_spec(spec).ok
    assert run.review["patch"].startswith("RefillCard added to Lucía's view")
    assert any(e["type"] == "RefillCard" for e in spec["views"]["helper"]["elements"].values())
    qh = next(p for p in spec["policies"] if p["rule_id"] == "P-QH-01")
    assert qh["params"]["status"] == "pending_her_words" and qh["params"]["welcome_call_at"] == "13:30"
    needs = spec["blueprint"]["needs"]
    text = spec["blueprint"]["description"]["text"]
    assert len(needs) == 5 and all(n["source_span"] for n in needs)
    assert "old lisinopril bottle" in text[needs[3]["source_span"]["start"] : needs[3]["source_span"]["end"]]
    marco = next(p for p in spec["blueprint"]["people"] if p["id"] == "m_marco")
    assert marco["profile"]["availability"][0]["days"] == ["Tue", "Thu", "Fri", "Sat"]
    assert run.states[-1] == "review"
    notes = [f["payload"]["text"] for f in svc.frames if f.get("kind") == "reasoning" and f["payload"]["text"].startswith("Now I know")]
    assert any("10 of 10 covered" in n for n in notes)


def test_resume_at_8_takes_live_answers() -> None:
    inp, answers = replay_input()
    svc = MemoryServices()

    async def go():
        task = asyncio.create_task(found(inp, village_id="v_resume", services=svc, options=demo_options(llm="off", replay=answers, resume=8, clarify_wait_s=3)))
        live = [r["text"] for r in answers[9:]]  # A10, A11, A12
        while live:
            await asyncio.sleep(0.02)
            s = SESSIONS.get("v_resume")
            if s and s.waiting and s.answers.empty():
                answer("v_resume", live.pop(0))
        return await task

    run = asyncio.run(go())
    assert [t["meter"].split()[0] for t in run.turns][-3:] == ["8", "9", "10"]
    assert run.review.get("patch", "").startswith("RefillCard added")


def test_found_with_stub_model_renders_and_critiques() -> None:
    svc = MemoryServices()
    llm = StubLLM()
    run = asyncio.run(found(FoundingInput(description=ANA), village_id="v_reyes", services=svc, options=demo_options(llm_client=llm)))
    assert llm.tools[0] == "extract_blueprint" and llm.tools[1] == "critique_plan"
    assert sorted(llm.tools[2:]) == ["render_app"] * 3
    assert {r.status for r in run.roles.values()} == {"validated"}
    assert run.critique["source"] == "model"
    assert validate_spec(svc.specs["v_reyes"]).ok


def test_block_found_model_off() -> None:
    svc = MemoryServices()
    text = json.loads((Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "block_spec.json").read_text())["blueprint"]["description"]["text"]
    run = asyncio.run(found(FoundingInput(description=text, kind="block"), village_id="v_w147", services=svc, options=demo_options(llm="off")))
    assert validate_spec(svc.specs["v_w147"]).ok
    assert set(run.capabilities["b_tanya"]) == {"dashboard", "village_chat"}
    assert not any("DailyMed" in l for l in run.ledger)


def test_block_village_born_through_the_same_intake() -> None:
    inp, answers = replay_input(kind="block")
    svc = MemoryServices()
    run = asyncio.run(found(inp, services=svc, options=demo_options("block", llm="off", replay=answers)))
    spec = svc.specs["v_w147"]
    assert validate_spec(spec).ok
    fx = json.loads((Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "block_spec.json").read_text())
    assert list(spec["views"]) == list(fx["views"])
    assert [p["name"] for p in spec["blueprint"]["people"]] == [p["name"] for p in fx["blueprint"]["people"]]
    assert int(run.turns[-1]["meter"].split()[0]) == 10
    assert len(run.turns) == 6
    assert any("DailyMed: insulin" in l for l in run.ledger)
    assert any("Darnell confirmed" in l for l in run.ledger)
    needs = {n["id"]: n for n in spec["blueprint"]["needs"]}
    assert needs["n_infant"]["source_span"] and needs["n_mobility"]["source_span"]


def _timeline(svc):
    out = []
    for i, f in enumerate(svc.frames):
        if f["type"] == "patch":
            out.append(("patch", f["role"], f["highlight"], i))
        elif f["kind"] == "reasoning" and f["payload"]["source"] == "founder" and f["payload"]["text"].startswith(("Ana: ", "Tanya: ")):
            out.append(("answer", f["payload"]["text"][:40], None, i))
        elif f["kind"] == "blueprint" and f["payload"]["stage"] == "will_build":
            out.append(("will_build", [(x["person"], x["component"]) for x in f["payload"]["items"]], None, i))
    return out


def test_d33_cause_then_effect_frame_order_per_answer() -> None:
    run, svc = _replay()
    tl = _timeline(svc)
    answers = [i for i, x in enumerate(tl) if x[0] == "answer"]
    # A2 (Marco's week) → HelperAnswer for Marco, announced after A2 and before A3, then patched into helper
    a2, a3 = answers[1], answers[2]
    wb = [i for i in range(a2, a3) if tl[i][0] == "will_build" and ("m_marco", "HelperAnswer") in tl[i][1]]
    assert wb, tl[a2:a3]
    assert any(tl[i][0] == "patch" and tl[i][1] == "helper" and "ans" in tl[i][2] for i in range(wb[0], a3))
    # A6 (money) → VerificationPrompt for Marco
    a6, a7 = answers[5], answers[6]
    assert any(tl[i][0] == "will_build" and ("m_marco", "VerificationPrompt") in tl[i][1] for i in range(a6, a7))
    # every patch follows a will_build with no answer in between
    last = None
    for x in tl:
        if x[0] in ("will_build", "answer"):
            last = x[0]
        if x[0] == "patch":
            assert last == "will_build"
    # nothing for routine before A5
    a5 = answers[4]
    assert not any(x[0] == "will_build" and any(c == "TonightCard" for _, c in x[1]) for x in tl[:a5])
    # review edit → RefillCard for Lucía, and "Draft ready" only after the review
    assert any(x[0] == "will_build" and ("m_lucia", "RefillCard") in x[1] for x in tl)
    done = [i for i, f in enumerate(svc.frames) if f.get("kind") == "blueprint" and f["payload"]["stage"] == "done"]
    review_i = max(i for i, f in enumerate(svc.frames) if f.get("kind") == "reasoning" and f["payload"]["text"].startswith("Ana: Lucía should"))
    assert done and done[0] > review_i
    assert any("· done · Draft ready · rev" in l for l in run.ledger)


def test_d33_block_emits_the_same_frames() -> None:
    inp, answers = replay_input(kind="block")
    svc = MemoryServices()
    asyncio.run(found(inp, services=svc, options=demo_options("block", llm="off", replay=answers)))
    tl = _timeline(svc)
    assert any(x[0] == "will_build" and ("b_tanya", "CheckIn") in x[1] for x in tl)
    assert any(x[0] == "patch" and x[1] == "resident" for x in tl)
