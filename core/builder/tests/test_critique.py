from __future__ import annotations

import asyncio
import json

from core.builder.capabilities import plan_capabilities
from core.builder.critique import critique
from core.builder.llm_port import FakeLLM
from core.builder.paths import FIXTURES
from core.builder.services_stub import MemoryServices
from core.builder.spans import RecordingTracer, set_tracer


def _spec() -> dict:
    return json.loads((FIXTURES / "reyes_spec.json").read_text())


def test_canned_critique_diff_applied_and_evaluator_span() -> None:
    tracer = RecordingTracer()
    set_tracer(tracer)
    try:
        spec = _spec()
        people = spec["blueprint"]["people"]
        plan = plan_capabilities(spec)
        canned = {
            "changes": [
                {"member_id": "m_lucia", "capability": "refill_day", "op": "remove", "reason": "Lucía is remote in Philadelphia; she can't fill the organizer"},
                {"member_id": "m_carmen", "capability": "village_chat", "op": "add", "reason": "bad idea"},
            ],
            "assumptions": ["Marco sleeps until 2 PM"],
            "summary": "1 change",
        }
        svc = MemoryServices()
        res = asyncio.run(critique(plan, people, village_id="v_reyes", services=svc, llm=FakeLLM(responses=[canned])))
        assert "refill_day" not in plan.for_member("m_lucia")
        assert "village_chat" not in plan.for_member("m_carmen")
        assert len(res.applied) == 1 and len(res.refused) == 1 and res.source == "model"
        ev = [s for s in tracer.spans if s.kind == "EVALUATOR"]
        assert ev and ev[0].name == "builder.critique" and ev[0].attrs["eval.changes_applied"] == 1
        assert svc.frames[-1]["payload"]["text"].startswith("Second opinion: 1 change")
    finally:
        set_tracer(None)


def test_rules_critique_model_off_names_assumptions() -> None:
    spec = _spec()
    plan = plan_capabilities(spec)
    res = asyncio.run(critique(plan, spec["blueprint"]["people"], village_id="v_reyes", services=MemoryServices()))
    assert res.source == "rules"
    assert any("21:30-07:00" in a for a in res.assumptions)
