from datetime import datetime

from fastapi.testclient import TestClient

from core import services
from core.app import app
from core.clock import ET, clock
from core.db import db
from core.fixtures import reset_demo

from core.settings import CONTRACT_VERSION as V


def _hello(ws, token):
    ws.send_json({"type": "hello", "contract_version": V, "village": "v_reyes", "member_token": token})
    return ws.receive_json()


async def test_reset_seeds_first_two_chat_rows_and_ids() -> None:
    await reset_demo("v_reyes")
    assert [m["id"] for m in db.messages] == ["msg_1016_0811_nudge", "msg_1016_1355_marco"]
    msg = await services.post_message("v_reyes", author="village", kind="nudge", text="hi", refs=["ev_1012_0900_shift_1016"], source={"kind": "system", "ref": "scheduler"})
    assert msg["id"].startswith("msg_") and msg["refs"] == [{"kind": "event", "id": "ev_1012_0900_shift_1016"}]


def test_post_message_fans_out_to_non_elder_and_village_answer() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?m=m_ana") as ana, client.websocket_connect("/ws?m=m_carmen") as carmen, client.websocket_connect("/ws?m=control") as control:
            snap = _hello(ana, "mt_ana_0000000000000000")
            assert len(snap["data"]["chat:village"]) == 2
            carmen_snap = _hello(carmen, "mt_carmen_000000000000")
            assert "chat:village" not in carmen_snap["data"]
            _hello(control, "control")
            r = client.post("/villages/v_reyes/messages", json={"text": "On my way"}, headers={"Authorization": "Bearer mt_marco_9Qe2vLx7Rk3pZ0aB"})
            assert r.status_code == 201 and r.json()["routed"] == "none"
            frame = next(f for f in iter(ana.receive_json, None) if f["type"] == "chat")
            assert frame["message"]["author"] == "m_marco" and frame["message"]["kind"] == "chat"
            r = client.post("/villages/v_reyes/messages", json={"text": "@Village why Marco and not Lucía?"}, headers={"Authorization": "Bearer mt_ana_0000000000000000"})
            assert r.json()["routed"] == "ask"
            seen = []
            while not any(f["type"] == "chat" and f["message"]["kind"] == "answer" for f in seen):
                seen.append(ana.receive_json())
            answer = [f for f in seen if f["type"] == "chat" and f["message"]["kind"] == "answer"][0]["message"]
            assert answer["author"] == "village" and answer["refs"] and answer["reply_to"] == r.json()["message"]["id"]
            # elder cannot post; elder never got chat frames (next frame for carmen would be the counter-free socket; check history API instead)
            assert client.post("/villages/v_reyes/messages", json={"text": "hola"}, headers={"Authorization": "Bearer m_carmen"}).status_code == 403
            assert client.get("/villages/v_reyes/messages", headers={"Authorization": "Bearer m_carmen"}).status_code == 403
            rows = client.get("/villages/v_reyes/messages?after=msg_1016_1355_marco", headers={"Authorization": "Bearer m_ana"}).json()
            assert [m["kind"] for m in rows] == ["chat", "chat", "answer"]


async def test_denied_incident_posts_incident_message() -> None:
    await reset_demo("v_reyes")
    body = {"conversation_id": "conv_chat_inc", "caller_id": "+15555550101", "call_secs": 9, "utterance": "x", "tool_call_id": "t1", "claimed_member": "marco", "amount": 2000, "urgency": "now"}
    vid = (await services.handle_tool("report_money_request", body))["data"]["verification_id"]
    await services.answer_verification(vid, "no", via="app_prompt", member_id="m_marco")
    incident_msgs = [m for m in db.messages if m["kind"] == "incident"]
    assert len(incident_msgs) == 1
    refs = incident_msgs[0]["refs"]
    incident_event = next(ev for ev in db.events if ev["kind"] == "incident" and ev["payload"]["verification_id"] == vid)
    assert refs[0]["id"] == incident_event["id"] and refs[1] == {"kind": "verification", "id": vid, "label": "Marco answered"}
    assert "Nothing was sent" in incident_msgs[0]["text"]


async def test_rota_nudge_at_15() -> None:
    await reset_demo("v_reyes")
    saved = clock.offset
    try:
        clock.warp(to=datetime(2026, 10, 16, 15, 0, 5, tzinfo=ET))
        assert await services.rota_nudge_tick() == 1
        assert await services.rota_nudge_tick() == 0
        nudge = [m for m in db.messages if m["kind"] == "nudge" and m["source"]["ref"] == "scheduler"][-1]
        assert nudge["refs"][0]["id"] == "ev_1012_0900_shift_1016" and nudge["text"].startswith("Marco")
    finally:
        clock.offset = saved
