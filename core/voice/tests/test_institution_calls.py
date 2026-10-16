"""BLOCK-VOICE: institution check calls (fixture mode) write facts + [demo] chat rows, idempotently."""
from __future__ import annotations

import asyncio

import pytest

from core import village as village_reg
from core.builder import chat_intent
from core.db import db
from core.voice import institution_calls as ic


def _with_and_without() -> tuple[str, str]:
    ids = village_reg.village_ids()
    has = [v for v in ids if village_reg.village_data(v).get("institutions")]
    hasnt = [v for v in ids if not village_reg.village_data(v).get("institutions")]
    assert has and hasnt
    return has[0], hasnt[0]


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(ic, "MAX_WAIT_S", 0.0)
    asyncio.run(db.reset())
    yield
    asyncio.run(db.reset())


def _village_rows(vid: str) -> list[dict]:
    return [m for m in db.messages if m.get("village") == vid and m.get("author") == "village"] if isinstance(db.messages, list) else \
        [m for m in db.messages.values() if m.get("village") == vid and m.get("author") == "village"]


def test_fixture_run_writes_facts_and_demo_rows_idempotently() -> None:
    vid, _ = _with_and_without()
    n = len(ic.institutions(vid))
    out = asyncio.run(ic.run_calls(vid, "run1"))
    assert out["mode"] == "fixture" and len(out["results"]) == n
    drafts = ic.fact_drafts(vid)
    assert len(drafts) == n * len(ic.KEYS)
    assert {d["source"]["kind"] for d in drafts} == {"call"}
    rows = _village_rows(vid)
    assert len(rows) == n
    for row in rows:
        assert row["text"].startswith("[demo] ") and row["text"].endswith(" · demo") and row["kind"] == "nudge"
        assert row["refs"][0]["kind"] == "fact"
    again = asyncio.run(ic.run_calls(vid, "run1"))
    assert all(r.get("replayed") for r in again["results"])
    assert len(ic.fact_drafts(vid)) == n * len(ic.KEYS) and len(_village_rows(vid)) == n


def test_village_without_institutions_is_noop_and_classify_falls_through() -> None:
    with_id, vid = _with_and_without()
    out = asyncio.run(ic.run_calls(vid, "run1"))
    assert out["results"] == [] and _village_rows(vid) == []
    text = "@Village can the cooling center or the hospital take people, do they have power?"
    assert not chat_intent.is_call_out(vid, text, village_reg.coordinator_id(vid))
    assert chat_intent.is_call_out(with_id, text, village_reg.coordinator_id(with_id))
    assert not chat_intent.is_call_out(with_id, "lol mom's telenovela is on again", village_reg.coordinator_id(with_id))


def test_chat_text_shapes() -> None:
    inst = {"id": "i1", "name": "Place"}
    assert ic.chat_text(inst, {"has_power": "yes", "open_until": "8 PM", "takes_oxygen": "yes"}, "2:41 PM", demo=False) == \
        "Place: power yes · open until 8 PM · takes oxygen: yes (called 2:41 PM)"
    assert ic.chat_text(inst, {"no_answer": True}, "2:43 PM", demo=False) == "No answer at Place (2:43 PM). I'll try again in 20 minutes."
