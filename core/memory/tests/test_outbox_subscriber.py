import json
import time

from core.memory.ledger_subscriber import LedgerSubscriber, facts_from_event
from core.memory.outbox import Outbox
from core.settings import ROOT

SEED = json.loads((ROOT / "contracts/fixtures/events_reyes_seed.json").read_text())["events"]
MED = next(e for e in SEED if e["kind"] == "med_change")
RX = [{"med_id": "med_lisinopril_5", "dose": "5 mg", "valid_from": "2026-09-01",
       "source": {"kind": "system", "ref": "seed", "quote": "Prior bottle in cabinet"}}]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_med_change_two_triples_in_order():
    d = facts_from_event(MED, RX)
    assert [(x["key"], x["value"]) for x in d] == [("lisinopril_dose", "5 mg"), ("lisinopril_dose", "10 mg")]
    assert d[0]["observed_at"].startswith("2026-09-01") and d[1]["observed_at"].startswith("2026-10-03")
    assert d[1]["source"]["ref"] == "conv_setup_0003" and d[1]["event_id"] == "ev_1003_1740_med_change"
    assert "Dr. Elena Park" in d[1]["text"]


def test_every_seed_kind_maps():
    kinds = {}
    for e in SEED:
        kinds[e["kind"]] = facts_from_event(e, RX)
    for k in ("dose", "med_change", "money_request", "verification_pending", "verification_timeout", "incident", "consent", "shift"):
        assert kinds[k], k
    assert facts_from_event({"kind": "qa", "payload": {}}) == []
    assert facts_from_event({"id": "ev_x1", "kind": "call_failed", "village": "v_reyes",
                             "payload": {"conversation_id": "c1", "reason": "busy"}})[0]["key"] == "last_call_failed"


async def test_enqueue_is_fast_and_idempotent(tmp_path, client, fake):
    ob = Outbox(tmp_path / "o.jsonl", client)
    sub = LedgerSubscriber(ob, prescriptions=lambda v: RX, voice_dir=tmp_path / "none")
    t0 = time.perf_counter()
    n = sub.on_event(MED)
    assert (time.perf_counter() - t0) * 1000 < 5 and n == 2
    assert fake.requests == []  # no network on enqueue
    assert sub.on_event(MED) == 0  # duplicate event id enqueued once
    r = await ob.drain_once()
    assert r["sent"] == 2
    h = await client.fact_history("m_carmen", "lisinopril_dose", village="v_reyes")
    assert [x["value"] for x in h["history"]] == ["5 mg", "10 mg"] and h["history"][0]["supersededBy"]


async def test_backoff_then_drain_and_restart(tmp_path, client, fake):
    clk = Clock()
    ob = Outbox(tmp_path / "o.jsonl", client, clock=clk)
    LedgerSubscriber(ob, prescriptions=lambda v: RX).on_event(MED)
    fake.status_override = 503
    r = await ob.drain_once()
    assert r == {"sent": 0, "dead": 0, "failed": 1}
    assert ob.stats()["queued"] == 2 and ob.pending()[0]["attempts"] == 1
    fake.status_override = None
    assert (await ob.drain_once())["sent"] == 0  # still backing off
    # restart from disk keeps state
    ob2 = Outbox(tmp_path / "o.jsonl", client, clock=clk)
    assert ob2.pending()[0]["attempts"] == 1
    clk.t += 2
    assert (await ob2.drain_once())["sent"] == 2
    assert Outbox(tmp_path / "o.jsonl", client).stats()["sent"] == 2


async def test_4xx_dead(tmp_path, client, fake):
    ob = Outbox(tmp_path / "o.jsonl", client)
    ob.enqueue("x", "fact", {"entity": "m_carmen", "key": "k_a", "value": "1", "source": {"kind": "system", "ref": "t"}, "village": "v_reyes"})
    fake.status_override = 400
    assert (await ob.drain_once())["dead"] == 1
    assert ob.stats()["dead"] == 1


async def test_memory_down_outbox_grows(tmp_path, client, fake):
    fake.down = True
    ob = Outbox(tmp_path / "o.jsonl", client)
    sub = LedgerSubscriber(ob, prescriptions=lambda v: RX)
    for e in SEED:
        sub.on_event(e)
    await ob.drain_once()
    assert ob.stats()["queued"] > 5 and ob.stats()["last_error"] == "memory_unreachable"


async def test_voice_post_call_outbox(tmp_path, client, fake):
    vdir = tmp_path / "voice"
    vdir.mkdir()
    (vdir / "conv_1.json").write_text(json.dumps({
        "type": "post_call", "conversation_id": "conv_1", "village_id": "v_reyes", "member_id": "m_carmen",
        "data": {"transcript": [{"role": "agent", "message": "Hola Carmen"}, {"role": "user", "message": "Ya me tomé la pastilla azul."}],
                 "metadata": {"call_duration_secs": 42}, "analysis": {"transcript_summary": "Carmen logged her evening pills."}}}))
    ob = Outbox(tmp_path / "o.jsonl", client)
    sub = LedgerSubscriber(ob, voice_dir=vdir)
    assert sub.consume_voice_outbox() == 2
    assert sub.consume_voice_outbox() == 0  # consumed once
    await ob.drain_once()
    kinds = [b.get("infer") for m, p, b in fake.requests if p == "/facts"]
    assert kinds == ["full", "triples"]
    full = [b for m, p, b in fake.requests if p == "/facts"][0]
    assert full["session_id"] == "conv_1" and "src=call:conv_1" in full["labels"]


async def test_subscriber_live_from_db_publish(tmp_path, client):
    import asyncio
    from core.db import MemoryDB
    mdb = MemoryDB()
    ob = Outbox(tmp_path / "o.jsonl", client)
    sub = LedgerSubscriber(ob, prescriptions=lambda v: RX)
    sub.start(mdb)
    await asyncio.sleep(0)
    await mdb.create_event(MED)
    await asyncio.sleep(0.01)
    await sub.stop()
    assert ob.stats()["queued"] == 2
