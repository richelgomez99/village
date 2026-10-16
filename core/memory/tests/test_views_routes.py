import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from core.memory.client import MemoryClient
from core.memory.fake import FakeAgentMemory
from core.memory.ledger_subscriber import LedgerSubscriber
from core.memory.outbox import Outbox
from core.memory.routes import get_memory_deps, router
from core.memory.views import MemoryDeps, mirror
from core.memory import conventions as cv
from core.settings import ROOT

SCHEMAS = ROOT / "contracts" / "schemas"
_s = {p.name: json.loads(p.read_text()) for p in SCHEMAS.glob("*.schema.json")}
REG = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _s.values())
SEED = json.loads((ROOT / "contracts/fixtures/events_reyes_seed.json").read_text())["events"]
RX = [{"med_id": "med_lisinopril_5", "dose": "5 mg", "valid_from": "2026-09-01",
       "source": {"kind": "system", "ref": "seed", "quote": "Prior bottle in cabinet"}}]
NOW = cv.to_dt("2026-10-16T14:00:00-04:00")


def valid(defn, inst):
    v = Draft202012Validator({"$ref": f"https://village.contracts/v1/facts.schema.json#/$defs/{defn}"}, registry=REG,
                             format_checker=FormatChecker())
    errs = sorted(v.iter_errors(inst), key=str)
    assert not errs, [f"{list(e.path)}: {e.message}" for e in errs[:5]]


@pytest.fixture
def setup(tmp_path):
    fake = FakeAgentMemory()
    client = MemoryClient("https://am.test", "ctx", "sp", transport=fake.transport())
    decisions = []

    async def wd(row):
        decisions.append(row)

    deps = MemoryDeps(client=client, events=lambda v: SEED, prescriptions=lambda v: RX, now=lambda: NOW, write_decision=wd)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_memory_deps] = lambda: deps
    return fake, client, deps, TestClient(app), decisions, tmp_path


async def _seed(client, tmp_path):
    ob = Outbox(tmp_path / "o.jsonl", client)
    sub = LedgerSubscriber(ob, prescriptions=lambda v: RX)
    for e in SEED:
        sub.on_event(e)
    r = await ob.drain_once()
    assert r["failed"] == 0 and r["dead"] == 0


async def test_facts_lisinopril_current_with_source(setup):
    fake, client, deps, tc, _, tmp = setup
    await _seed(client, tmp)
    body = tc.get("/villages/v_reyes/facts", params={"subject": "m_carmen"}).json()
    valid("facts_response", body)
    assert body["degraded"] is False
    lis = [f for f in body["facts"] if f["key"] == "lisinopril_dose"]
    assert len(lis) == 1 and lis[0]["value"] == "10 mg" and lis[0]["source"]["ref"] == "conv_setup_0003"
    assert lis[0]["event_id"] == "ev_1003_1740_med_change" and lis[0]["labels"]["secs"] == "88"


async def test_facts_as_of_before_change(setup):
    fake, client, deps, tc, _, tmp = setup
    await _seed(client, tmp)
    body = tc.get("/villages/v_reyes/facts", params={"subject": "m_carmen", "as_of": "2026-10-02T12:00:00-04:00"}).json()
    valid("facts_response", body)
    lis = [f for f in body["facts"] if f["key"] == "lisinopril_dose"]
    assert [f["value"] for f in lis] == ["5 mg"]


async def test_history_chain(setup):
    fake, client, deps, tc, _, tmp = setup
    await _seed(client, tmp)
    body = tc.get("/villages/v_reyes/facts/m_carmen/lisinopril_dose/history").json()
    valid("history_response", body)
    assert [(v["value"], v["superseded"]) for v in body["versions"]] == [("10 mg", False), ("5 mg", True)]
    assert body["versions"][1]["source"]["ref"] == "seed"


def test_degraded_from_ledger_mirror(setup):
    fake, client, deps, tc, _, tmp = setup
    fake.down = True
    import time
    t0 = time.perf_counter()
    body = tc.get("/villages/v_reyes/facts", params={"subject": "m_carmen"}).json()
    assert time.perf_counter() - t0 < 2
    valid("facts_response", body)
    assert body["degraded"] is True and body["degraded_reason"] == "memory_unreachable"
    assert [f["value"] for f in body["facts"] if f["key"] == "lisinopril_dose"] == ["10 mg"]
    h = tc.get("/villages/v_reyes/facts/m_carmen/lisinopril_dose/history").json()
    valid("history_response", h)
    assert h["degraded"] and [v["value"] for v in h["versions"]] == ["10 mg", "5 mg"]
    u = tc.get("/villages/v_reyes/uncertainties").json()
    valid("uncertainties_response", u)
    assert u["degraded"]
    r = tc.post("/villages/v_reyes/uncertainties/unc_x/resolve", json={"accepted_value": "10 mg"})
    assert r.status_code == 503 and r.json()["degraded"]


def test_backlog_is_degraded(setup):
    fake, client, deps, tc, _, tmp = setup
    body = tc.get("/villages/v_reyes/facts").json()
    valid("facts_response", body)
    assert body["degraded"] and body["degraded_reason"] == "outbox_backlog" and body["facts"]


async def test_uncertainty_list_and_resolve(setup):
    fake, client, deps, tc, decisions, tmp = setup
    await _seed(client, tmp)
    uid = fake.add_uncertainty("entity:person/carmen_reyes_(m_carmen)", "lisinopril_dose", "10 mg", "20 mg tablet",
                               "village/v_reyes/m_carmen")
    u = tc.get("/villages/v_reyes/uncertainties").json()
    valid("uncertainties_response", u)
    assert u["uncertainties"][0]["id"] == "unc_" + uid and u["uncertainties"][0]["entity"] == "m_carmen"
    assert {c["value"] for c in u["uncertainties"][0]["candidates"]} >= {"10 mg", "20 mg tablet"}
    r = tc.post(f"/villages/v_reyes/uncertainties/unc_{uid}/resolve", json={"accepted_value": "10 mg", "note": "Dr. Park"},
                headers={"x-member-id": "m_ana"})
    assert r.status_code == 200, r.text
    body = r.json()
    valid("resolve_response", body)
    assert body["uncertainty"]["status"] == "resolved" and body["fact"]["value"] == "10 mg"
    assert decisions and decisions[0]["mode"] == "asked_human" and body["decision_id"] == decisions[0]["id"]
    assert tc.post("/villages/v_reyes/uncertainties/unc_nope/resolve", json={"accepted_value": "x"}).status_code == 404


def test_mirror_chain():
    deps = MemoryDeps(client=None, events=lambda v: SEED, prescriptions=lambda v: RX)
    chain = [d for d in mirror(deps, "v_reyes") if d["key"] == "lisinopril_dose"]
    assert [(d["value"], d["superseded"]) for d in chain] == [("5 mg", True), ("10 mg", False)]
    assert chain[0]["superseded_by"] == "fact:lisinopril_dose:m_carmen:2026-10-03"
