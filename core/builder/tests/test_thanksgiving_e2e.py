"""D36 end to end on core's app (model off, fake release): Ana's @Village message → change intent →
proposal in proposals:pending → approve → each view has its card in the right place."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from core.builder.chat_intent import build_change_ops, classify, extract_rules

MSG = json.loads((Path(__file__).resolve().parents[3] / "data" / "builder" / "thanksgiving_change.jsonl").read_text().splitlines()[0])["text"]


def test_extractor_and_intent_model_off() -> None:
    import asyncio

    assert asyncio.run(classify(MSG)) == "change"
    assert asyncio.run(classify("@Village why does Marco get calls and not Lucía?")) == "why"
    ch = extract_rules(MSG)
    assert ch["event"] == "Thanksgiving" and ch["date_day"] == 27 and ch["people_count"] == 12
    assert {(b["who"], b["what"]) for b in ch["brings"]} == {("Marco", "the turkey"), ("Lucía", "the pie")}
    assert ch["arrivals"] == [{"who": "Lucía", "train": "11:40", "pickup_place": "Penn Station", "pickup_at": "1"}]
    assert ch["dietary"] == ["Grandpa needs a low-salt plate"] and ch["rule"] == "no politics at the table"


def test_ops_land_in_the_right_place() -> None:
    from core.builder import templates

    spec = templates.spec("care")
    b = build_change_ops(spec, extract_rules(MSG))
    els = lambda r: b["ops"][r][0]["value"]  # noqa: E731
    assert els("coordinator")["type"] == "PlanBoard" and els("coordinator")["props"] == {"title": "Thanksgiving · Nov 27", "bind": "plan:thanksgiving_1127", "date": "Thu Nov 27", "allow_claim": True}
    items = b["plan"]["items"]
    assert b["plan"]["id"] == "thanksgiving_1127"
    assert {"text": "Pick up Lucía at Penn Station", "kind": "pickup", "owner": "m_marco", "when": "1:00 PM", "status": "claimed", "note": ""} in items
    assert [i["text"] for i in items] == ["12 people at Mom's", "Marco: turkey", "Lucía: pie", "Lucía: 11:40 train", "Pick up Lucía at Penn Station", "Grandpa: low-salt plate", "Rule: no politics at the table"]
    assert els("helper")["props"]["text"] == "Thanksgiving: Marco brings the turkey · Lucía brings the pie, 11:40 train"
    assert els("elder")["props"]["text"] == "El jueves 27 vienen todos. Marco trae el pavo."
    kids = {r: spec["views"][r]["elements"]["s"]["children"] for r in spec["views"]}
    at = {r: int(b["ops"][r][1]["path"].rsplit("/", 1)[1]) for r in b["ops"]}
    assert kids["elder"][at["elder"] - 1] == "tonight" and kids["helper"][at["helper"] - 1] == "ans" and kids["coordinator"][at["coordinator"] - 1] == "areas"
    assert any(l.startswith("Pick up Lucía at Penn Station, 1 PM (Marco)") for l in b["lines"])
    assert b["blueprint_ops"] and b["blueprint_ops"][1]["value"]["label"] == "Thanksgiving · Nov 27"


@pytest.mark.timeout(60) if hasattr(pytest.mark, "timeout") else (lambda f: f)
def test_e2e_on_core_app() -> None:
    os.environ["VILLAGE_EVOLVE_RELEASE"] = "fake"
    os.environ.setdefault("VILLAGE_LLM", "off")
    os.environ["SURREAL_DB_URL"] = ""  # never write test rows to the shared SurrealDB Cloud instance
    from core.settings import get_settings

    get_settings.cache_clear()
    assert not get_settings().surreal_db_url
    from fastapi.testclient import TestClient

    from core.app import app
    from core.db import db

    with TestClient(app) as c:
        r = c.post("/villages/v_reyes/messages", json={"text": MSG, "mention": "village"}, headers={"Authorization": "Bearer m_ana"})
        assert r.status_code == 201 and r.json()["routed"] == "ask"
        prop = None
        for _ in range(200):
            rows = [m for m in db.messages if m.get("village") == "v_reyes" and m.get("kind") == "proposal" and "Thanksgiving" in m.get("text", "")]
            if rows:
                prop = next(ref["id"] for ref in rows[-1]["refs"] if ref["kind"] == "proposal")
                break
            time.sleep(0.05)
        assert prop, "no proposal posted"
        from core.bindings import proposals_pending

        pending = proposals_pending("v_reyes")
        assert any(p["proposal_id"] == prop for p in pending)
        a = c.post(f"/villages/v_reyes/proposals/{prop}/approve?wait=true", headers={"Authorization": "Bearer m_ana"})
        assert a.status_code == 202, a.text
        spec = db.specs["v_reyes"]
        for role, typ in (("coordinator", "PlanBoard"), ("helper", "Text"), ("elder", "Text")):
            el = spec["views"][role]["elements"]["plan_event"]
            assert el["type"] == typ
        assert any(a_["label"].startswith("Thanksgiving") for a_ in spec["blueprint"]["life_areas"])
        from core.builder.chat_intent import plan_data

        assert plan_data("v_reyes", "thanksgiving_1127")["items"][1]["text"] == "Marco: turkey"
        answer = [m for m in db.messages if m.get("kind") == "answer" and "Thanksgiving" in m.get("text", "")]
        assert answer and answer[-1]["refs"][0]["kind"] == "proposal"
