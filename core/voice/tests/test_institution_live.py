"""BLOCK-VOICE live branch with the fake dialer: the call goes only to DEMO_INSTITUTION_NUMBER, the post-call
webhook maps data_collection_results to live facts, and an unanswered call becomes 'no answer at <time>'."""
from __future__ import annotations

import asyncio

import pytest

from core import dialer as dialer_mod
from core import village as villages
from core.db import db
from core import services
from core.fixtures import reset_demo
from core.voice import institution_calls as ic


def _block() -> str:
    return next(v for v in villages.village_ids() if villages.village_data(v).get("institutions"))


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("DEMO_INSTITUTION_NUMBER", "+15555550199")
    monkeypatch.setenv("INSTITUTION_CALL_WAIT_S", "2")
    monkeypatch.setattr(ic, "live_mode", lambda: True)
    fake = dialer_mod._fake
    monkeypatch.setattr(dialer_mod, "get_dialer", lambda: fake)
    fake.calls.clear()
    return fake


def test_live_call_goes_only_to_demo_number_and_post_call_writes_live_facts(live) -> None:
    async def main():
        await reset_demo()
        vid = _block()
        inst = ic.institutions(vid)[0]
        task = asyncio.ensure_future(ic._one(vid, inst, "run1"))
        await asyncio.sleep(0.2)
        assert live.calls and live.calls[-1]["to_number"] == "+15555550199"
        dv = live.calls[-1]["conversation_initiation_client_data"]["dynamic_variables"]
        assert dv["purpose"] == "institution_check" and dv["place_name"] == inst["name"] and dv["questions"]
        conv = next(k for k in db.idem if k.startswith("instconv:")).split(":", 1)[1]
        assert await ic.apply_post_call({"type": "post_call", "conversation_id": conv, "duration_secs": 41,
                                         "data_collection_results": {"has_power": {"value": "yes"}, "open_until": "8 PM", "takes_oxygen": "unknown"}})
        out = await task
        await services.drain_chat()
        assert out["mode"] == "live" and out["facts"] == 3
        rows = [m for m in db.messages if m.get("village") == vid and m["kind"] == "nudge" and inst["name"] in m["text"]]
        assert rows and "power yes" in rows[-1]["text"] and "[demo]" not in rows[-1]["text"]
        assert any(d["value"] == "8 PM" and d["extra_labels"]["demo"] == "false" for d in ic.fact_drafts(vid))
        assert await ic.apply_post_call({"type": "post_call", "conversation_id": "conv_unknown"}) is False
    asyncio.run(main())


def test_unanswered_live_call_becomes_no_answer_fact(live) -> None:
    async def main():
        await reset_demo()
        vid = _block()
        inst = ic.institutions(vid)[1]
        out = await ic._one(vid, inst, "run2")  # nobody posts a post-call payload within INSTITUTION_CALL_WAIT_S
        assert out["mode"] == "live_no_answer"
        await services.drain_chat()
        rows = [m for m in db.messages if m.get("village") == vid and inst["name"] in m["text"]]
        assert rows and rows[-1]["text"].startswith("No answer at")
        assert any(d["value"].startswith("no answer at") for d in ic.fact_drafts(vid) if d["entity"] == inst["id"])
    asyncio.run(main())
