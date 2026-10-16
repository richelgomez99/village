from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.builder import routes
from core.builder.services_stub import MemoryServices
from core.builder.validate import validate_spec


def _client() -> tuple[TestClient, MemoryServices]:
    svc = MemoryServices()
    routes.set_services(svc)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app), svc


def _wait(c: TestClient, vid: str, cond, timeout: float = 10.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        body = c.get(f"/villages/{vid}").json()
        if cond(body):
            return body
        time.sleep(0.05)
    raise AssertionError(f"timeout; last={body.get('builder', {}).get('state')}")


def test_resume_8_through_routes_then_activate_redeem_ask() -> None:
    c, svc = _client()
    with c:
        r = c.post("/villages?resume=8", json={"kind": "care", "mode": "fixture", "dailymed": "fixture", "clarify_wait_s": 5})
        assert r.status_code == 202
        vid = r.json()["village_id"]
        b = _wait(c, vid, lambda b: b.get("builder", {}).get("question") and b["builder"].get("meter", "").startswith("8 of 10"))
        assert b["builder"]["question"].startswith("Her phone and her language")
        a = c.post(f"/villages/{vid}/answers", json={"text": "Spanish only. A regular phone, she won't use apps. Big letters if anything. She'll answer a call; she won't read a text."}).json()
        assert a["accepted"] and a["meter"].startswith("9 of 10")
        _wait(c, vid, lambda b: (b["builder"].get("question") or "").startswith("Two things"))
        c.post(f"/villages/{vid}/answers", json={"text": "After lunch, around one-thirty. And she hates calls at night."})
        _wait(c, vid, lambda b: (b["builder"].get("question") or "").startswith("Here is the draft"))
        c.post(f"/villages/{vid}/answers", json={"text": "Lucía should see the refill list too, she does the ordering."})
        b = _wait(c, vid, lambda b: b["builder"].get("review", {}).get("patch"))
        assert b["builder"]["review"]["patch"].startswith("RefillCard added")
        spec = c.get(f"/villages/{vid}").json()
        assert spec["village"]["status"] == "draft" and len(spec["views"]) == 3
        assert c.patch(f"/villages/{vid}/draft", json={"ops": [{"op": "replace", "path": "/views/helper/elements/s/props/title", "value": "¿Me toca?"}]}).status_code == 200
        assert c.patch(f"/villages/{vid}/draft", json={"ops": [{"op": "remove", "path": "/village/id"}]}).status_code == 422
        act = c.post(f"/villages/{vid}/activate")
        assert act.status_code == 200
        inv = act.json()["invites"]
        assert len(inv) >= 2 and all("join.html?i=" in i["url"] for i in inv)
        assert validate_spec(svc.specs[vid]).ok
        assert c.post(f"/villages/{vid}/activate").status_code == 409
        tok = next(i for i in inv if i["member_id"] == "m_marco")["url"].split("i=")[1]
        red = c.post("/builder/auth/redeem", json={"invite": tok, "consent": {"ai_calls": True, "text_version": "join_v1"}}).json()
        assert red["member_id"] == "m_marco" and red["consent_event"]["kind"] == "consent"
        assert c.post("/builder/auth/redeem", json={"invite": tok}).status_code == 409
        tok_hashes = list(routes.INVITES)
        assert tok not in tok_hashes  # stored hashed
        ans = c.post(f"/villages/{vid}/ask", json={"question": "Why does Marco get calls and not Lucía?", "llm": "off"}).json()
        assert len(ans["citations"]) >= 1


def test_text_founding_202_and_draft_model_off() -> None:
    c, svc = _client()
    with c:
        r = c.post("/villages", json={"description": "Mom forgets her pills", "mode": "fixture", "clarify_wait_s": 0.05, "dailymed": "off"})
        assert r.status_code == 202
        vid = r.json()["village_id"]
        b = _wait(c, vid, lambda b: b.get("builder", {}).get("state") == "review" and "views" in b)
        assert validate_spec(svc.specs[vid]).ok
        assert c.get("/villages/v_nope").status_code == 404
