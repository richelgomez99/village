"""Operator test: Village answers member messages without @Village when someone is needed."""
from __future__ import annotations

import asyncio
import os
import time

import pytest

from core.builder.chat_intent import classify

UTTERANCES = [
    ("hey guys, will need someone to take care of mom tomorrow", "need"),
    ("can anyone cover Saturday? I'm stuck at work", "need"),
    ("why does Marco get calls and not Lucía?", "why"),
    ("we're doing Thanksgiving at Mom's on the 27th, Marco brings the turkey", "change"),
    ("lol mom's telenovela is on again", "chit_chat"),
    ("thanks everyone ❤️", "chit_chat"),
]


@pytest.mark.parametrize("text,intent", UTTERANCES)
def test_six_utterances_model_off(text: str, intent: str) -> None:
    assert asyncio.run(classify(text)) == intent


def _app():
    os.environ["VILLAGE_EVOLVE_RELEASE"] = "fake"
    os.environ.setdefault("VILLAGE_LLM", "off")
    os.environ["SURREAL_DB_URL"] = ""
    from core.settings import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from core.app import app

    return TestClient(app)


def _village_msgs(db, after: int):
    return [m for m in db.messages[after:] if m.get("village") == "v_reyes" and m.get("author") == "village"]


def _post(c, text, who="m_ana"):
    r = c.post("/villages/v_reyes/messages", json={"text": text}, headers={"Authorization": f"Bearer {who}"})
    assert r.status_code == 201
    return r.json()


def _wait(pred, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(0.02)
    return pred()


def test_operator_line_asks_the_people_and_a_yes_writes_the_shift() -> None:
    os.environ["ASK_TIMEOUT_S"] = "30"
    from core.builder import asks
    from core.builder.actors import set_actors
    from core.db import db
    from core.evolve import proposals as ev

    set_actors([])
    with _app() as c:
        n, nprops = len(db.messages), sum(len(v) for v in ev.STORE.values())
        t0 = time.time()
        assert _post(c, "hey guys, will need someone to take care of mom tomorrow")["routed"] == "none"
        got = _wait(lambda: [m for m in _village_msgs(db, n) if m["kind"] == "nudge"][1:] and _village_msgs(db, n))
        assert got and time.time() - t0 < 2.0
        reply = got[0]
        assert reply["kind"] == "answer" and reply["text"] == "Tomorrow's Saturday, Marco's night. Marco, still good? Lucía, can you cover if not?"
        nudges = [m for m in got if m["kind"] == "nudge"]
        assert [m["refs"][0]["id"] for m in nudges] == ["m_marco", "m_lucia"]
        assert sum(len(v) for v in ev.STORE.values()) == nprops, "no proposal for a need"
        ask_id = next(a for a in asks.ASKS if asks.ASKS[a]["status"] == "open" and asks.ASKS[a]["cover"] == "m_lucia")
        assert c.post(f"/villages/v_reyes/asks/{ask_id}/answer", json={"answer": "yes"}, headers={"Authorization": "Bearer m_lucia"}).json()["status"] == "open"
        r = c.post(f"/villages/v_reyes/asks/{ask_id}/answer", json={"answer": "no"}, headers={"Authorization": "Bearer m_marco"}).json()
        assert r["status"] == "resolved" and r["event_id"]
        shift = next(e for e in db.events if e["id"] == r["event_id"])
        assert shift["kind"] == "shift" and shift["payload"] == {"date": shift["payload"]["date"], "on_duty": "m_lucia", "backup": "m_marco", "change": "swapped"}
        from core.bindings import rota_week

        assert next(d for d in rota_week("v_reyes") if d["date"] == shift["payload"]["date"])["on_duty"] == "m_lucia"
        assert any(m["text"].startswith("Saturday: Lucía covers for Marco.") for m in _village_msgs(db, n))
        assert c.post(f"/villages/v_reyes/asks/{ask_id}/answer", json={"answer": "yes"}, headers={"Authorization": "Bearer m_ana"}).status_code in (200, 403)
        n2 = len(db.messages)
        _post(c, "lol mom's telenovela is on again", "m_marco")
        time.sleep(0.3)
        assert not _village_msgs(db, n2), "chit-chat must get no reply"


def test_nobody_answers_then_the_leader_is_asked() -> None:
    os.environ["ASK_TIMEOUT_S"] = "0.3"
    from core.builder.actors import set_actors
    from core.db import db

    set_actors([])
    with _app() as c:
        n = len(db.messages)
        _post(c, "can anyone cover tomorrow?")
        q = _wait(lambda: [m for m in _village_msgs(db, n) if m["kind"] == "nudge" and m["refs"][0]["id"] == "m_ana"], 3)
        assert q and q[0]["text"] == "No answer from Lucía or Marco. Ana, want me to keep asking or take Saturday yourself?"
    os.environ["ASK_TIMEOUT_S"] = "20"


def test_demo_actors_answer_with_the_demo_mark() -> None:
    os.environ["ASK_TIMEOUT_S"] = "30"
    os.environ["DEMO_ACTOR_DELAY_S"] = "0"
    from core.builder.actors import set_actors
    from core.db import db

    set_actors(["lucia", "marco"])
    try:
        with _app() as c:
            n = len(db.messages)
            _post(c, "hey guys, will need someone to take care of mom tomorrow")
            done = _wait(lambda: [m for m in _village_msgs(db, n) if "covers for" in m["text"]], 3)
            assert done
            demo = [m for m in db.messages[n:] if m.get("text", "").startswith("[demo] ")]
            assert {m["author"] for m in demo} == {"m_lucia", "m_marco"}
            assert all(m["source"]["kind"] == "system" and m["refs"][0] == {"kind": "member", "id": m["author"]} for m in demo)
    finally:
        set_actors([])
        os.environ.pop("DEMO_ACTOR_DELAY_S", None)
