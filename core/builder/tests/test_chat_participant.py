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


def test_operator_line_gets_a_rota_grounded_swap_question() -> None:
    from core.db import db

    with _app() as c:
        n = len(db.messages)
        t0 = time.time()
        r = c.post("/villages/v_reyes/messages", json={"text": "hey guys, will need someone to take care of mom tomorrow"}, headers={"Authorization": "Bearer m_ana"})
        assert r.status_code == 201 and r.json()["routed"] == "none"
        for _ in range(100):
            got = _village_msgs(db, n)
            if got:
                break
            time.sleep(0.02)
        assert got, "Village stayed silent"
        assert time.time() - t0 < 2.0
        msg = got[0]
        from core import village as villages
        from core.bindings import rota_week

        assert msg["kind"] == "proposal"
        # grounded: day + on-duty from the rota, cover = someone else (names come from the village, not code)
        assert msg["text"].startswith("Tomorrow is ") and "'s night. Want me to ask " in msg["text"]
        assert any(ref["kind"] == "proposal" for ref in msg["refs"])
        pid = next(ref["id"] for ref in msg["refs"] if ref["kind"] == "proposal")
        a = c.post(f"/villages/v_reyes/proposals/{pid}/approve?wait=true", headers={"Authorization": "Bearer m_ana"})
        assert a.status_code == 202, a.text
        assert db.specs["v_reyes"]["views"]["helper"]["elements"]["swap_note"]["props"]["text"].startswith("Saturday: ")
        n2 = len(db.messages)
        c.post("/villages/v_reyes/messages", json={"text": "lol mom's telenovela is on again"}, headers={"Authorization": "Bearer m_marco"})
        time.sleep(0.3)
        assert not _village_msgs(db, n2), "chit-chat must get no reply"
