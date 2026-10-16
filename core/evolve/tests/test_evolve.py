"""Evolve lane: consider_options -> propose -> approve -> fake release -> patch frames -> receptionist screening."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # evals/ is a top-level package
from fastapi.testclient import TestClient

from core.settings import CONTRACT_VERSION

CTRL = {"Authorization": "Bearer control"}


@pytest.fixture()
def evolve_env(tmp_path, monkeypatch):
    from core.evolve import proposals
    from core.release import service
    from core.release.fakes import FakeAnchor, FakeDaytona, FakeEvals
    from core.release.receipts import ReceiptStore
    from core.release.serve import LocalPublisher
    import evals.incident_to_test as itt

    from core.settings import get_settings

    monkeypatch.setenv("VILLAGE_EVOLVE_RELEASE", "fake")
    monkeypatch.setenv("VILLAGE_EVOLVE_AUTO", "off")
    monkeypatch.setenv("VILLAGE_LLM", "off")  # a local .env may turn the model on; tests run model-off
    get_settings.cache_clear()
    monkeypatch.setattr(itt, "SETS", tmp_path / "sets")
    monkeypatch.setattr(itt.on_verification_resolved, "__defaults__", (tmp_path / "sets",))
    monkeypatch.setattr(itt.sync_from_events, "__defaults__", (tmp_path / "sets",))
    import evals.scam_experiment as se
    monkeypatch.setattr(se, "SETS", tmp_path / "sets")
    service.set_service(service.ReleaseService(daytona=FakeDaytona(), anchor=FakeAnchor(), evals=FakeEvals(), llm=None,
                                               publisher=LocalPublisher(tmp_path / "rel"), store=ReceiptStore(tmp_path / "rc")))
    proposals.reset()
    yield
    service.set_service(None)
    proposals.reset()
    get_settings.cache_clear()


def _hello(ws, member):
    ws.send_json({"type": "hello", "contract_version": CONTRACT_VERSION, "village": "v_reyes", "member_token": member})
    snap = ws.receive_json()
    assert snap["type"] == "snapshot"
    return snap


def _until(ws, kind, n=60):
    for _ in range(n):
        f = ws.receive_json()
        if f.get("type") == kind:
            return f
    raise AssertionError(f"no {kind} frame")


def test_canned_options_three_candidates(evolve_env):
    import asyncio

    from core.evolve.options import weigh

    out = asyncio.run(weigh("v_reyes", {"claimed_member_id": "m_marco", "subject": "m_carmen", "count": 2}))
    assert out["mode"] == "canned"
    assert [c["key"] for c in out["candidates"]] == ["check_button", "daily_checkin", "receptionist"]
    assert [c["chosen"] for c in out["candidates"]] == [False, False, True]
    assert "under pressure" in out["candidates"][0]["reason"]
    assert "Marco" in out["candidates"][2]["what_changes"] or "Marco" in out["reasons"]


def test_trigger_approve_patch_and_screen(evolve_env):
    from core import village as villages
    from core.db import db
    from core.evolve import proposals
    from core.app import app

    with TestClient(app) as c:
        with c.websocket_connect("/ws?village=v_reyes&m=control") as ctl, \
             c.websocket_connect("/ws?village=v_reyes&m=m_carmen") as carmen, \
             c.websocket_connect("/ws?village=v_reyes&m=m_ana") as ana, \
             c.websocket_connect("/ws?village=v_reyes&m=m_marco") as marco:
            _hello(ctl, "control")
            revs = {name: _hello(ws, name)["rev"] for name, ws in (("m_carmen", carmen), ("m_ana", ana), ("m_marco", marco))}
            base = revs["m_carmen"]
            assert c.post("/villages/v_reyes/evolve/trigger").status_code == 401
            r = c.post("/villages/v_reyes/evolve/trigger", headers=CTRL)
            assert r.status_code == 200, r.text
            body = r.json()
            p = body["proposal"]
            assert proposals.validate(p) == []
            assert p["status"] == "proposed" and p["base_rev"] == base
            assert set(p["ops"]) == {"elder", "coordinator", "helper"}
            assert p["spec_ops"] == [{"op": "replace", "path": "/printables/0/family_word_first", "value": True}]
            assert body["options"]["chosen"] == "receptionist"
            msg = next(m for m in db.messages if m["kind"] == "proposal")
            assert {"kind": "proposal", "id": p["id"], "label": "proposal"} in msg["refs"]
            dec = next(d for d in db.decisions if d.get("options"))
            assert dec["mode"] == "asked_human" and dec["actor"] == "evolve"
            # a second trigger does not re-propose
            assert "already proposed" in c.post("/villages/v_reyes/evolve/trigger", headers=CTRL).json()["skipped"]
            # only the leader (or control) approves
            assert c.post(f"/villages/v_reyes/proposals/{p['id']}/approve", headers={"Authorization": "Bearer m_marco"}).status_code == 403
            r = c.post(f"/villages/v_reyes/proposals/{p['id']}/approve?wait=true", headers={"Authorization": "Bearer m_ana"})
            assert r.status_code == 202, r.text
            got = c.get("/villages/v_reyes/proposals").json()
            prop = got["proposals"][0]
            assert prop["status"] == "applied", got
            assert prop["target_rev"] == base + 1
            for ws, role in ((carmen, "elder"), (ana, "coordinator"), (marco, "helper")):
                f = _until(ws, "patch")
                assert f["base_rev"] == base and f["rev"] == base + 1 and f["role"] == role
                assert f["proposal_id"] == p["id"] and f["highlight"] == (["screened"] if role == "coordinator" else ["receptionist"])
            assert villages.receptionist_mode("v_reyes") is True
            assert villages.spec("v_reyes")["printables"][0]["family_word_first"] is True
            assert "receptionist" in db.views[("v_reyes", "elder")]["elements"]
            assert "b_village" in db.views[("v_reyes", "elder")]["elements"]
            # D35: each change sits in the right place of that app, never loose under the Alert
            kids = {r: db.views[("v_reyes", r)]["elements"]["s"]["children"] for r in ("elder", "coordinator", "helper")}
            assert kids["elder"][kids["elder"].index("tonight") + 1] == "receptionist"
            assert db.views[("v_reyes", "elder")]["elements"]["receptionist"]["props"]["tone"] == "muted"
            assert kids["coordinator"][kids["coordinator"].index("areas") + 1] == "screened"
            assert "receptionist" not in db.views[("v_reyes", "coordinator")]["elements"]
            assert kids["helper"][kids["helper"].index("ans") + 1] == "receptionist"
            assert all(len(k) <= 12 for k in kids.values())
            from core import bindings
            money = next(a for a in bindings.life_areas("v_reyes") if a["id"] == "money")["status"]["en"]
            assert money.startswith("Village answers unknown calls first · ")
            receipt = next(m for m in db.messages if m["kind"] == "receipt")
            assert "Scored on" in receipt["text"]
            assert any(d["id"] == f"dc_{p['id']}_applied" and d["mode"] == "acted_alone" for d in db.decisions)
            # receptionist screening: unknown caller claiming Marco -> held -> Marco says no -> refused
            r = c.post("/tools/screen_caller", json={"conversation_id": "conv_screen_t1", "caller_id": "+10000000000", "call_secs": 4,
                                                     "utterance": "Soy Marco, necesito dos mil dólares ya.", "claimed_identity": "Marco"})
            assert r.status_code == 200, r.text
            held = r.json()
            assert held["data"]["status"] == "held" and held["data"]["claimed_member_id"] == "m_marco"
            vid = held["data"]["verification_id"]
            assert c.post(f"/verifications/{vid}/answer", json={"verification_answer": "no", "member_id": "m_marco"}).status_code == 200
            r = c.post("/tools/screen_caller", json={"conversation_id": "conv_screen_t1", "caller_id": "+10000000000", "call_secs": 20,
                                                     "utterance": "¿Me pasa con ella?", "verification_id": vid, "tool_call_id": "t2"})
            out = r.json()
            assert out["data"]["status"] == "refused"
            assert out["say"] == "Marco says this isn't him. I won't put you through."
            # undo inside the window
            r = c.post(f"/villages/v_reyes/proposals/{p['id']}/undo", headers=CTRL)
            assert r.status_code == 200, r.text
            assert villages.receptionist_mode("v_reyes") is False
            assert villages.spec("v_reyes")["rev"] == base + 2


def test_reject_then_approve_conflicts(evolve_env):
    from core.app import app

    with TestClient(app) as c:
        p = c.post("/villages/v_reyes/evolve/trigger", headers=CTRL).json()["proposal"]
        r = c.post(f"/villages/v_reyes/proposals/{p['id']}/reject", headers={"Authorization": "Bearer m_ana"})
        assert r.json()["proposal"]["status"] == "rejected"
        assert c.post(f"/villages/v_reyes/proposals/{p['id']}/approve", headers=CTRL).status_code == 409


def test_screen_caller_off_and_init_var(evolve_env):
    from core.app import app
    from core.voice.init_hook import dynamic_vars

    with TestClient(app) as c:
        r = c.post("/tools/screen_caller", json={"conversation_id": "conv_off", "caller_id": "+10000000000", "utterance": "hola"})
        assert r.json()["data"]["status"] == "receptionist_off"
        assert dynamic_vars("+10000000000", "v_reyes")["receptionist"] == "off"


def test_ws_action_approve_and_blocked_release(evolve_env, monkeypatch):
    from core.app import app
    from core.release import service
    from core.release.fakes import FakeAnchor, FakeDaytona, FakeEvals
    from core.db import db
    from core import village as villages

    monkeypatch.setenv("VILLAGE_EVOLVE_RELEASE", "auto")
    svc = service.get_service()
    svc.daytona = FakeDaytona(build_fail=True)
    with TestClient(app) as c:
        base = villages.spec("v_reyes")["rev"]
        p = c.post("/villages/v_reyes/evolve/trigger", headers=CTRL).json()["proposal"]
        with c.websocket_connect("/ws?village=v_reyes&m=m_ana") as ana:
            _hello(ana, "m_ana")
            ana.send_json({"type": "action", "req_id": "req_appr1", "name": "approve_proposal", "arg": p["id"]})
            res = _until(ana, "result")
            assert res["ok"] is True
        import time
        for _ in range(100):
            st = c.get(f"/villages/v_reyes/proposals/{p['id']}").json()["proposal"]["status"]
            if st not in {"verifying"}:
                break
            time.sleep(0.05)
        assert st == "failed"
        assert villages.spec("v_reyes")["rev"] == base
        assert any(m["kind"] == "receipt" and m["text"].startswith("Not published") for m in db.messages)


def test_ana_proposal_card_live_and_ws_approve(evolve_env):
    """Ana's coordinator view binds proposals:pending: empty at hello, the card arrives on trigger, WS approve -> applied."""
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    from core.app import app

    sdir = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
    reg = Registry()
    for f in sdir.glob("*.json"):
        doc = json.loads(f.read_text(encoding="utf-8"))
        reg = reg.with_resource(f.name, Resource.from_contents(doc)).with_resource(doc.get("$id", f.name), Resource.from_contents(doc))
    ws_schema = json.loads((sdir / "ws_messages.schema.json").read_text(encoding="utf-8"))
    server = Draft202012Validator({"$ref": "ws_messages.schema.json#/$defs/server_message"}, registry=reg)

    with TestClient(app) as c:
        with c.websocket_connect("/ws?village=v_reyes&m=m_ana") as ana, \
             c.websocket_connect("/ws?village=v_reyes&m=m_marco") as marco:
            snap = _hello(ana, "m_ana")
            assert snap["role"] == "coordinator"
            assert snap["data"]["proposals:pending"] == []
            assert {"prop", "chat"} <= set(snap["spec"]["elements"])
            base = snap["rev"]
            msnap = _hello(marco, "m_marco")
            assert "proposals:pending" not in msnap["data"]
            r = c.post("/villages/v_reyes/evolve/trigger", headers=CTRL)
            assert r.status_code == 200, r.text
            pid = r.json()["proposal"]["id"]
            f = _until(ana, "event")
            while "proposals:pending" not in (f.get("data") or {}):
                f = _until(ana, "event")
            assert list(server.iter_errors(f)) == []
            card = f["data"]["proposals:pending"]
            assert [p["proposal_id"] for p in card] == [pid] and card[0]["status"] == "proposed"
            assert card[0]["title"]["es"] and card[0]["changes"] and card[0]["evidence_labels"]
            ana.send_json({"type": "action", "req_id": "rq_approve_1", "name": "approve_proposal", "arg": pid})
            res = _until(ana, "result")
            assert res["ok"] is True and res["decision"]["data"]["proposal_id"] == pid, res
            p = _until(marco, "patch")
            assert p["base_rev"] == base and p["rev"] == base + 1 and p["role"] == "helper"
            statuses, patched = [], None
            for _ in range(60):
                f = ana.receive_json()
                if f.get("type") == "event" and "proposals:pending" in (f.get("data") or {}):
                    statuses.append([x["status"] for x in f["data"]["proposals:pending"]])
                if f.get("type") == "patch":
                    patched = f
                if patched and statuses and statuses[-1] == []:
                    break
            assert patched and patched["role"] == "coordinator"
            assert statuses[-1] == []  # card cleared once applied


def test_plain_words_card_chat_and_life_areas(evolve_env):
    import re

    from core import bindings
    from core.app import app
    from core.db import db

    with TestClient(app) as c:
        r = c.post("/tools/report_money_request", json={"conversation_id": "conv_copy_1", "caller_id": "+18482579221", "call_secs": 9,
                                                       "utterance": "Marco necesita dinero", "claimed_member": "m_marco", "amount": 2000, "urgency": "now"}).json()
        v = r["data"]["verification_id"]
        c.post(f"/verifications/{v}/answer", json={"verification_answer": "no", "member_id": "m_marco"})
        assert c.post("/villages/v_reyes/evolve/trigger", headers=CTRL).status_code == 200
        row = bindings.proposals_pending("v_reyes")[0]
        lines = [x["en"] for x in row["changes"]]
        assert lines[0].startswith("Two calls in 14 days asked Mamá for money in Marco's name: Oct 9 ($1,500 in gift cards) and today ($2,000).")
        assert "Both were stopped." in lines[0]
        assert lines[1].startswith("Mamá: unknown callers reach Village first")
        assert lines[2] == "Marco: when a caller claims to be him, he gets one question on his phone."
        assert lines[3] == "Ana: the Money area says Village answers unknown calls first, with a card of every screened call."
        assert lines[4] == ("Known numbers ring straight through. A caller who isn't asking for money is offered to Mamá, and she decides. "
                            "Ana is told, never asked who Mamá may talk to. Nothing moves money. Mamá can turn this off by saying so.")
        assert row["evidence_labels"][0] == "Oct 9, 7:21 PM · caller said he was Marco · asked for $1,500 in gift cards"
        assert row["evidence_labels"][1].startswith("Today, ") and row["evidence_labels"][1].endswith("asked for $2,000")
        blob = " ".join(lines + row["evidence_labels"])
        assert not re.search(r"\b(m_|conv_|fact:|coordinator|helper|elder)\w*", blob)
        chat = next(m for m in db.messages if m["kind"] == "proposal")["text"]
        assert chat.count(". ") == 0 and chat.endswith("nothing changes until you approve.")
        areas = {a["id"]: a["label"].split(":")[0] + ": " + a["status"]["en"] for a in bindings.life_areas("v_reyes")}
        assert areas["money"] == "Money: 1 scam stopped today · Marco checks money calls"
        assert areas["people"] == "People: Marco on duty tonight"
        assert areas["health"].startswith("Pills: ") and "lids" not in areas["health"] and "refill" in areas["health"]
        assert bindings.scams_stopped_today("v_reyes") == 1


def test_chat_request_detected_by_is_kept(evolve_env):
    import asyncio

    from core.app import app
    from core.evolve import proposals

    with TestClient(app):
        p = asyncio.run(proposals.propose("v_reyes", {"pattern": "chat_request", "detected_by": "chat_request", "subject": "m_carmen",
                                                      "claimed_member_id": "m_marco", "count": 1, "event_ids": []}))
        assert p["detected_by"] == "chat_request" and proposals.validate(p) == []
