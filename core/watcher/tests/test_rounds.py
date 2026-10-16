import json
from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.clock import FakeClock
from core.settings import ROOT, get_settings
from core.watcher import rounds as R
from core.watcher import routes as W

SEED = json.loads((ROOT / "contracts/fixtures/events_reyes_seed.json").read_text())["events"]
CLOCK = FakeClock(datetime.fromisoformat("2026-10-16T14:00:00-04:00"))
CARER = "Ana has taken 9 of the last 12 nights. Ask Lucía to take the Sunday call?"


def ports():
    decisions, frames = [], []

    async def wd(row):
        decisions.append(row)

    async def bc(v, kind, payload):
        frames.append((kind, payload))

    return R.Ports(dialer=R.RecordingDialer(), chat=R.RecordingChat(), write_decision=wd, broadcast=bc), decisions, frames


async def test_seeded_round_counts_and_carer_load():
    p, decisions, frames = ports()
    res = await R.run_round("v_reyes", CLOCK, R.Services(events=lambda v: SEED), None, R.Budget(3), p)
    assert res["counts"] == {"acted_alone": 3, "asked_human": 1, "refused": 1}
    carer = [r for r in res["rows"] if r["step"] == "carer_load"]
    assert carer and carer[0]["text"] == CARER and carer[0]["mode"] == "asked_human"
    refused = [r for r in res["rows"] if r["mode"] == "refused"][0]
    assert refused["rule_id"] == "P-QH-01" and refused["source"]["ref"] == "welcome_call"
    assert "Blocked by code: Carmen's rule, no calls after 9:30 PM" in refused["text"]
    assert len(decisions) == 5 and all(d["mode"] in ("acted_alone", "asked_human", "refused") for d in decisions)
    assert [k for k, _ in frames] == ["reasoning"] * 5
    assert p.dialer.calls == []  # refused: no call placed
    assert {m["to"] for m in p.chat.messages} == {"m_marco", "m_lucia"}


async def test_decision_rows_and_frames_validate():
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    s = {q.name: json.loads(q.read_text()) for q in (ROOT / "contracts/schemas").glob("*.schema.json")}
    reg = Registry().with_resources((x["$id"], Resource.from_contents(x)) for x in s.values())
    dec = json.loads(json.dumps(s["decision.schema.json"]))
    dec["properties"]["mode"] = {"enum": ["acted_alone", "asked_human", "refused"]}  # LD: contract lacks `mode`
    vd = Draft202012Validator(dec, registry=reg)
    vc = Draft202012Validator({"$ref": "https://village.contracts/v1/ws_messages.schema.json#/$defs/control"}, registry=reg)
    p, decisions, frames = ports()
    await R.run_round("v_reyes", CLOCK, R.Services(events=lambda v: SEED), None, R.Budget(3), p)
    for d in decisions:
        assert not list(vd.iter_errors(d)), [e.message for e in vd.iter_errors(d)]
    for kind, payload in frames:
        msg = {"type": "control", "kind": kind, "payload": payload, "at": "2026-10-16T21:40:00-04:00"}
        assert not list(vc.iter_errors(msg)), [e.message for e in vc.iter_errors(msg)]


def test_nights_counted_from_rota_and_shifts():
    v = R.load_village("v_reyes")
    counts, covered = R.nights_by_member(R.history_events("v_reyes") + SEED, R.rota_days(v), date(2026, 10, 16))
    assert dict(counts) == {"m_ana": 9, "m_marco": 3} and len(covered) == 12
    assert "2026-10-08" not in covered  # nobody went last Thursday


def test_no_carer_row_when_balanced():
    v = R.load_village("v_reyes")
    assert R.carer_load(v, SEED, date(2026, 10, 16)) is None  # rota alone: Ana 2, Marco 2


async def test_before_quiet_hours_call_is_placed():
    p, decisions, _ = ports()
    at = datetime.fromisoformat("2026-10-16T20:30:00-04:00")
    res = await R.run_round("v_reyes", CLOCK, R.Services(events=lambda v: SEED), None, R.Budget(5), p, at=at)
    assert res["counts"]["refused"] == 0 and p.dialer.calls[0]["member_id"] == "m_carmen"


async def test_budget_overflow_asks_instead():
    p, _, _ = ports()
    res = await R.run_round("v_reyes", CLOCK, R.Services(events=lambda v: SEED), None, R.Budget(1), p)
    assert res["counts"] == {"acted_alone": 1, "asked_human": 3, "refused": 1}
    assert any("Over tonight's budget" in r["text"] for r in res["rows"])


async def test_evening_logged_skips_checkin_and_nudge():
    ev = {"id": "ev_1016_1935_dose_evening", "village": "v_reyes", "kind": "dose", "at": "2026-10-16T19:35:00-04:00",
          "payload": {"subject": "m_carmen", "slot": "evening", "taken_at": "2026-10-16T19:35:00-04:00", "confidence": "confirmed", "via": "lid_qr"}}
    p, _, _ = ports()
    res = await R.run_round("v_reyes", CLOCK, R.Services(events=lambda v: SEED + [ev]), None, R.Budget(3), p)
    steps = [r["step"] for r in res["rows"]]
    assert "checkin_call" not in steps and "missed_dose_nudge" not in steps


async def test_evals_and_patterns_and_uncertainties():
    class Ev:
        async def rerun_scam_set(self, v):
            return {"caught": 29, "total": 30}

        async def detect_patterns(self, v, events):
            return [{"claimed_member_id": "m_marco", "event_ids": ["ev_1009_1921_money"], "count": 2}]

    class Mem:
        async def uncertainties(self, v):
            return {"degraded": False, "uncertainties": [{"key": "lisinopril_dose"}]}

    p, _, _ = ports()
    p.evals = Ev()
    res = await R.run_round("v_reyes", CLOCK, R.Services(events=lambda v: SEED), Mem(), R.Budget(4), p)
    assert res["counts"] == {"acted_alone": 4, "asked_human": 3, "refused": 1}
    assert any("29/30" in r["text"] for r in res["rows"])


def test_local_pattern_fallback():
    m2 = dict(SEED[[e["kind"] for e in SEED].index("money_request")], id="ev_1016_1402_money", at="2026-10-16T14:02:00-04:00")
    pats = R.local_patterns(SEED + [m2], datetime.fromisoformat("2026-10-16T21:40:00-04:00"))
    assert pats and pats[0]["count"] == 2


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "VAR", tmp_path)
    W.LATEST.clear()
    p, decisions, _ = ports()
    deps = {"clock": CLOCK, "services": R.Services(events=lambda v: SEED), "memory": None, "ports": p, "budget": R.Budget(3)}
    app = FastAPI()
    app.include_router(W.router)
    app.include_router(W.admin_router)
    app.dependency_overrides[W.get_rounds_deps] = lambda: deps
    return TestClient(app), decisions


def test_routes(api):
    tc, decisions = api
    key = get_settings().admin_key
    assert tc.post("/villages/v_reyes/rounds/run", headers={"x-admin-key": "nope"}).status_code == 403
    assert tc.get("/villages/v_reyes/rounds/latest").status_code == 404
    r = tc.post("/villages/v_reyes/rounds/run", headers={"x-admin-key": key}).json()
    assert r["counts"] == {"acted_alone": 3, "asked_human": 1, "refused": 1} and len(r["rows"]) == 5
    assert tc.get("/villages/v_reyes/rounds/latest").json()["counts"] == r["counts"]
    r2 = tc.post("/admin/rounds/run", headers={"x-admin-key": key}, json={"village": "v_reyes"}).json()
    assert r2["counts"] == r["counts"]


async def test_scheduler_ticks_once(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "VAR", tmp_path)
    p, _, _ = ports()
    clk = FakeClock(datetime.fromisoformat("2026-10-16T21:00:00-04:00"))
    deps = {"clock": clk, "services": R.Services(events=lambda v: SEED), "memory": None, "ports": p, "budget": R.Budget(3)}
    s = W.RoundsScheduler(["v_reyes"], deps_factory=lambda: deps)
    assert await s.tick() == []
    clk.set(datetime.fromisoformat("2026-10-16T21:41:00-04:00"))
    assert len(await s.tick()) == 1
    assert await s.tick() == []
