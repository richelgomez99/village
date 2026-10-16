from __future__ import annotations

import asyncio
import json
from copy import deepcopy

from core.builder import templates
from core.builder.render import render_views
from core.builder.services_stub import MemoryServices
from core.builder.validate import validate_spec


class RoleFake:
    """Dispatches render_app responses by the role in the user message."""

    model = "fake"

    def __init__(self, script: dict) -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []

    async def tool_call(self, *, system, messages, tool, max_tokens=4096):
        role = json.loads(messages[0]["content"].split("\n\nYour previous")[0])["role"]
        self.calls.append(role)
        item = self.script[role].pop(0)
        if isinstance(item, tuple):
            await asyncio.sleep(item[0])
            item = item[1]
        if isinstance(item, BaseException):
            raise item
        return deepcopy(item)


def _valid(spec: dict, role: str, marker: str | None = None) -> dict:
    view = templates.strip_chat(spec["views"][role])
    served = view.pop("needs_served")
    if marker:
        view["elements"]["s"]["props"]["title"] = marker
    return {"role": role, "plan": f"{role} plan", "needs": [{"id": "n_turns", "statement": "x", "priority": 1, "domain": "scheduling"}], "view": view, "needs_served": served}


def _broken(spec: dict, role: str) -> dict:
    out = _valid(spec, role)
    out["view"]["elements"]["s"]["children"].append("ghost")
    return out


def _run(script, per_role_s=45.0, total_s=60.0):
    spec = templates.spec("care", village_id="v_rr")
    svc = MemoryServices()
    fake = RoleFake(script)
    out, results = asyncio.run(render_views(spec, village_id="v_rr", services=svc, llm=fake, per_role_s=per_role_s, total_s=total_s))
    return spec, out, results, svc, fake


def test_all_valid() -> None:
    spec = templates.spec("care")
    script = {r: [_valid(spec, r, f"{r} rendered")] for r in spec["views"]}
    _, out, results, svc, _ = _run(script)
    assert {r.status for r in results.values()} == {"validated"}
    assert validate_spec(out).ok
    assert out["views"]["helper"]["elements"]["s"]["props"]["title"] == "helper rendered"
    assert sum(1 for e in out["views"]["helper"]["elements"].values() if e["type"] == "VillageChat") == 1
    assert not any(e["type"] == "VillageChat" for e in out["views"]["elder"]["elements"].values())


def test_one_repaired_one_template() -> None:
    spec = templates.spec("care")
    script = {
        "elder": [_valid(spec, "elder")],
        "coordinator": [_broken(spec, "coordinator"), _valid(spec, "coordinator", "fixed")],
        "helper": [_broken(spec, "helper"), _broken(spec, "helper")],
    }
    base, out, results, svc, _ = _run(script)
    assert results["coordinator"].status == "repaired" and results["coordinator"].attempts == 2
    assert results["helper"].status == "template"
    assert out["views"]["helper"] == base["views"]["helper"]
    assert any(d["text"].startswith("template helper: invalid after repair") for d in svc.decisions)
    assert validate_spec(out).ok
    texts = [f["payload"]["text"] for f in svc.frames if f["kind"] == "reasoning"]
    assert "coordinator view: rendering" in texts and any(t.startswith("coordinator view: repaired") for t in texts)


def test_timeout_falls_back_to_template() -> None:
    spec = templates.spec("care")
    script = {"elder": [_valid(spec, "elder")], "coordinator": [(1.0, _valid(spec, "coordinator"))], "helper": [RuntimeError("boom")]}
    _, out, results, svc, _ = _run(script, per_role_s=0.2, total_s=0.5)
    assert results["elder"].status == "validated"
    assert results["coordinator"].status == "template" and results["coordinator"].reason.startswith("timeout")
    assert results["helper"].status == "template" and "boom" in results["helper"].reason
    assert validate_spec(out).ok


def test_model_off_is_all_template() -> None:
    spec = templates.spec("block", village_id="v_bb")
    svc = MemoryServices()
    out, results = asyncio.run(render_views(spec, village_id="v_bb", services=svc, llm=None))
    assert {r.status for r in results.values()} == {"template"} and validate_spec(out).ok
    assert [d["text"] for d in svc.decisions] == [f"template {r}: model off" for r in spec["views"]]
