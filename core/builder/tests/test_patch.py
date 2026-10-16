from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from core.builder import templates
from core.builder.llm_port import FakeLLM
from core.builder.patch import PatchError, apply_ops, patch, prompt_examples


def _ex(n: int, role: str) -> dict:
    out = deepcopy(prompt_examples()[n])
    out["role"] = role
    return out


def test_rfc6902_ops_apply_to_copy() -> None:
    doc = {"a": [1, 2], "b": {"c": 1}}
    out = apply_ops(doc, [{"op": "add", "path": "/a/-", "value": 3}, {"op": "replace", "path": "/b/c", "value": 2}, {"op": "move", "from": "/b/c", "path": "/d"}, {"op": "copy", "from": "/a/0", "path": "/e"}, {"op": "test", "path": "/e", "value": 1}, {"op": "remove", "path": "/a/1"}])
    assert out == {"a": [1, 3], "b": {}, "d": 2, "e": 1}
    assert doc == {"a": [1, 2], "b": {"c": 1}}
    with pytest.raises(PatchError):
        apply_ops(doc, [{"op": "remove", "path": "/zzz"}])


def test_example5_scamcheck_on_elder_is_valid() -> None:
    spec = templates.spec("care")
    res = asyncio.run(patch(spec, "elder", "two calls in Marco's name", llm=FakeLLM(responses=[_ex(5, "elder")])))
    assert res.status == "valid", res.errors
    assert res.spec["views"]["elder"]["elements"]["scam"]["type"] == "ScamCheck"
    assert "scam" not in spec["views"]["elder"]["elements"]


def test_example6_incident_card_on_helper_and_one_repair() -> None:
    spec = templates.spec("care")
    broken = _ex(6, "helper")
    broken["ops"][1]["path"] = "/elements/s/children/99"
    res = asyncio.run(patch(spec, "helper", "family should see every money request", llm=FakeLLM(responses=[broken, _ex(6, "helper")])))
    assert res.status == "repaired" and res.attempts == 2


def test_example4_invalid_twice_leaves_spec_unchanged() -> None:
    spec = templates.spec("care")
    bad = _ex(4, "helper")
    bad["ops"][1]["path"] = "/elements/ghost/children/-"
    res = asyncio.run(patch(spec, "helper", "symptom log", llm=FakeLLM(responses=[bad, bad])))
    assert res.status == "invalid" and res.spec is None and not res.valid


def test_safety_refusal_and_model_off_receptionist() -> None:
    spec = templates.spec("care")
    assert asyncio.run(patch(spec, "helper", "let Mamá send money to Marco")).status == "refused"
    res = asyncio.run(patch(spec, "coordinator", "Village answers unknown callers first"))
    assert res.status == "valid" and "receptionist" in res.spec["views"]["coordinator"]["elements"]
