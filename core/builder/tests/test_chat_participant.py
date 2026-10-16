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


def _ask_msgs(db, n):
    return [m for m in _village_msgs(db, n) if any(r.get("kind") == "ask" for r in m["refs"])]


def test_need_someone_asks_on_duty_and_cover_in_one_message_and_yes_writes_shift() -> None:
    os.environ["ASK_TIMEOUT_S"] = "30"
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from core.builder.actors import set_actors
    from core.db import db
    from core.evolve import proposals as ev

    set_actors([])
    with _app() as c:
        n, nprops = len(db.messages), sum(len(v) for v in ev.STORE.values())
        t0 = time.time()
        assert _post(c, "hey guys, will need someone to take care of mom tomorrow")["routed"] == "none"
        got = _wait(lambda: _ask_msgs(db, n))
        assert got and time.time() - t0 < 2.0
        msg = got[0]
        assert msg["kind"] == "answer" and msg["text"] == "Tomorrow's Saturday, Marco's night. Marco, still good? Lucía, can you cover if not?"
        asks_ = [r for r in msg["refs"] if r["kind"] == "ask"]
        assert [r["member"] for r in asks_] == ["m_marco", "m_lucia"] and all(r["answered"] is None for r in asks_)
        assert not [m for m in _village_msgs(db, n) if m["kind"] == "nudge"], "one message, not three"
        assert sum(len(v) for v in ev.STORE.values()) == nprops, "no proposal for a need"
        # (4) wall-clock timestamp on a live post
        at = datetime.fromisoformat(msg["at"])
        assert abs((at - datetime.now(ZoneInfo("America/New_York"))).total_seconds()) < 120
        lucia, marco = asks_[1]["id"], asks_[0]["id"]
        assert c.post(f"/villages/v_reyes/asks/{lucia}/answer", json={"answer": "yes"}, headers={"Authorization": "Bearer m_lucia"}).json()["status"] == "open"
        refreshed = next(m for m in db.messages if m["id"] == msg["id"])
        assert next(r for r in refreshed["refs"] if r["member"] == "m_lucia")["answered"] == "yes"
        assert "Lucía: can do" in refreshed["text_i18n"]["en"]
        r = c.post(f"/villages/v_reyes/asks/{marco}/answer", json={"answer": "no"}, headers={"Authorization": "Bearer m_marco"}).json()
        assert r["status"] == "resolved" and r["event_id"]
        assert "Marco: can't · Lucía: can do" in next(m for m in db.messages if m["id"] == msg["id"])["text_i18n"]["en"]
        shift = next(e for e in db.events if e["id"] == r["event_id"])
        assert shift["payload"]["on_duty"] == "m_lucia" and shift["payload"]["backup"] == "m_marco" and shift["payload"]["change"] == "swapped"
        from core.bindings import rota_week

        assert next(d for d in rota_week("v_reyes") if d["date"] == shift["payload"]["date"])["on_duty"] == "m_lucia"
        assert any(m["text"].startswith("Saturday: Lucía covers for Marco.") for m in _village_msgs(db, n))
        assert c.post(f"/villages/v_reyes/asks/{lucia}/answer", json={"answer": "yes"}, headers={"Authorization": "Bearer m_ana"}).status_code == 403
        n2 = len(db.messages)
        _post(c, "lol mom's telenovela is on again", "m_marco")
        time.sleep(0.3)
        assert not _village_msgs(db, n2), "chit-chat must get no reply"


def test_cover_for_marco_does_not_ask_marco_and_a_chat_yes_resolves() -> None:
    os.environ["ASK_TIMEOUT_S"] = "30"
    from core.builder.actors import set_actors
    from core.db import db

    set_actors([])
    with _app() as c:
        n = len(db.messages)
        _post(c, "I need someone to cover for Marco tomorrow")
        msg = _wait(lambda: _ask_msgs(db, n))[0]
        assert msg["text"] == "Tomorrow's Saturday, Marco's night. Lucía, can you cover?"
        assert [r["member"] for r in msg["refs"] if r["kind"] == "ask"] == ["m_lucia"]
        _post(c, "yes I can take it", "m_lucia")
        done = _wait(lambda: [m for m in _village_msgs(db, n) if "covers for" in m["text"]])
        assert done and done[0]["text"].startswith("Saturday: Lucía covers for Marco.")


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


def test_demo_actors_answer_with_the_demo_mark_and_ask_refs() -> None:
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
            for m in demo:
                assert m["source"] == {"kind": "system", "ref": "demo_actor"}
                assert any(r["kind"] == "member" and r["id"] == m["author"] for r in m["refs"]) and any(r["kind"] == "ask" for r in m["refs"])
    finally:
        set_actors([])
        os.environ.pop("DEMO_ACTOR_DELAY_S", None)


# ---- CORE-GLUE-7: a need that is not a night cover → open plan item + ask, model off ----

def test_weekday_resolution_relative_to_the_clock() -> None:
    from datetime import date

    from core.builder.plan_need import extract_rules, resolve_day

    assert resolve_day("friday", None, date(2026, 10, 14)) == ("2026-10-16", "Friday")
    assert resolve_day("lunes", None, date(2026, 10, 16)) == ("2026-10-19", "Monday")
    assert resolve_day("Fri", None, date(2026, 10, 16)) == ("2026-10-16", "Friday")
    assert resolve_day(None, "tomorrow", date(2026, 10, 16)) == ("2026-10-17", "Saturday")
    n = extract_rules("Hey fam, I need someone to take mom to the doctor's on friday")
    assert n["what"] == "take mom to the doctor" and n["weekday"] == "friday" and n["needs_on_site"] and not n["is_night_cover"] and n["time"] == ""
    assert extract_rules("can anyone cover tomorrow night")["is_night_cover"]
    r = extract_rules("can someone call the pharmacy on Tuesday at 10am")
    assert not r["needs_on_site"] and r["time"] == "10:00 AM" and not r["is_night_cover"]


def test_group_agnostic_classify_model_off() -> None:
    assert asyncio.run(classify("the library cooling center closed early. We're moving everyone who needs cool air to the Hamilton Grange center on 145th at 3")) == "change"
    assert asyncio.run(classify("Hey fam, I need someone to take mom to the doctor's on friday")) == "need"


def test_doctor_on_friday_is_a_plan_item_and_ask_not_a_cover_and_yes_sets_owner() -> None:
    os.environ["ASK_TIMEOUT_S"] = "30"
    from datetime import timedelta

    from core.bindings_v3 import plan
    from core.builder.actors import set_actors
    from core.clock import clock
    from core.db import db

    set_actors([])
    with _app() as c:
        n, nevents = len(db.messages), len(db.events)
        before = len(plan("v_reyes", "needs").get("items", []))
        _post(c, "Hey fam, I need someone to take mom to the doctor's on friday")
        msg = _wait(lambda: _ask_msgs(db, n))[0]
        assert msg["text"].startswith("Friday: Ana needs someone to take ") and "doctor" in msg["text"]
        assert "night" not in msg["text"] and "Saturday" not in msg["text"] and "cover" not in msg["text"]
        asked = [r for r in msg["refs"] if r["kind"] == "ask"]
        assert asked and "m_ana" not in [r["member"] for r in asked] and "m_carmen" not in [r["member"] for r in asked]
        items = plan("v_reyes", "needs")["items"]
        assert len(items) == before + 1
        it = items[-1]
        today = clock.now().date()
        friday = (today + timedelta(days=(4 - today.weekday()) % 7)).isoformat()
        assert it["status"] == "open" and it["owner"] == "" and it["kind"] == "appointment" and it["when"] == friday and it["note"] == "who?"
        who = asked[0]["member"]
        r = c.post(f"/villages/v_reyes/asks/{asked[0]['id']}/answer", json={"answer": "yes"}, headers={"Authorization": f"Bearer {who}"}).json()
        assert r["status"] == "resolved"
        assert plan("v_reyes", "needs")["items"][-1]["owner"] == who
        out = _wait(lambda: [m for m in _village_msgs(db, n) if m["text"].startswith("Friday: ") and " takes " in m["text"]])
        assert out and "doctor" in out[0]["text"]
        assert not [e for e in db.events[nevents:] if e.get("kind") == "shift"], "the rota is untouched"


def test_cover_tomorrow_night_keeps_the_cover_path() -> None:
    os.environ["ASK_TIMEOUT_S"] = "30"
    from core.builder.actors import set_actors
    from core.db import db

    set_actors([])
    with _app() as c:
        n = len(db.messages)
        _post(c, "can anyone cover tomorrow night")
        msg = _wait(lambda: _ask_msgs(db, n))[0]
        assert msg["text"].startswith("Tomorrow's Saturday, Marco's night.")
