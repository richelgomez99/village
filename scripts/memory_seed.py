"""Seed the Reyes facts into SurrealDB Agent Memory for real, measure, and print the Fact view.

    uv run python scripts/memory_seed.py            # forget village/v_reyes, re-seed, measure
    uv run python scripts/memory_seed.py --keep     # do not forget first

Writes go through the real path: LedgerSubscriber -> Outbox (var/memory/seed_outbox.jsonl)
-> MemoryClient (infer:triples, provenance labels). Facts come from
contracts/fixtures/events_reyes_seed.json + data/villages/reyes_family.json.
Never prints keys. Report saved to var/memory/seed_report.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.memory import conventions as cv  # noqa: E402
from core.memory.client import MemoryClient  # noqa: E402
from core.memory.ledger_subscriber import LedgerSubscriber  # noqa: E402
from core.memory.outbox import Outbox  # noqa: E402
from core.memory.views import MemoryDeps, facts_view, history_view  # noqa: E402
from core.settings import ROOT  # noqa: E402

VILLAGE = "v_reyes"
# Same prior prescription core.fixtures.reset_demo loads into db.prescriptions.
RX = [{"med_id": "med_lisinopril_5", "name": "lisinopril", "dose": "5 mg", "valid_from": "2026-09-01",
       "valid_until": "2026-10-03", "source": {"kind": "system", "ref": "seed", "quote": "Prior bottle in cabinet"}}]


def family_facts(family: dict) -> list[dict]:
    """Village data -> fact args (current meds, refills, Carmen's rule)."""
    out = []
    seed = {"kind": "system", "ref": "seed"}
    for med in family.get("medications", []):
        if med.get("status") == "superseded" or med.get("name") == "lisinopril":
            continue  # lisinopril comes from the med_change event (supersession chain)
        out.append({"entity": "m_carmen", "key": f"{med['name']}_dose", "value": med["dose"], "source": seed,
                    "observed_at": med.get("valid_from")})
        if (med.get("refill") or {}).get("next_due"):
            out.append({"entity": "m_carmen", "key": f"{med['name']}_refill_due", "value": med["refill"]["next_due"],
                        "source": seed, "observed_at": med["refill"].get("last_filled")})
    for rule in family.get("rules_from_members", []):
        q = rule.get("params", {}).get("quiet_hours")
        if q:
            out.append({"entity": rule["member_id"], "key": "quiet_hours", "value": q,
                        "source": {**rule["source"], "quote": rule.get("words", "")}, "observed_at": "2026-10-10T18:00:00-04:00"})
    for day in family.get("care_rota", {}).get("week_of_2026-10-12", []):
        out.append({"entity": "village", "key": f"rota_{day['date'].replace('-', '_')}", "value": day["on_duty"],
                    "source": seed, "observed_at": "2026-10-11T20:00:00-04:00"})
    return out


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))])


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    events = json.loads((ROOT / "contracts/fixtures/events_reyes_seed.json").read_text())["events"]
    family = json.loads((ROOT / "data/villages/reyes_family.json").read_text())
    client = MemoryClient()
    if not client.configured:
        print("SURREAL_MEMORY_* not set; nothing to do")
        return 2
    print(f"Agent Memory: {client.base_url} context {client.context[:6]}…")
    if not args.keep:
        r = await client.forget_scope(cv.village_scope(VILLAGE))
        print(f"forget {cv.village_scope(VILLAGE)}: HTTP {r['status']}")
    obp = ROOT / "var/memory/seed_outbox.jsonl"
    obp.unlink(missing_ok=True)
    ob = Outbox(obp, client)
    sub = LedgerSubscriber(ob, prescriptions=lambda v: RX, voice_dir=ROOT / "var/memory/none")
    for f in family_facts(family):
        ob.enqueue(f"family:{f['entity']}:{f['key']}", "fact", {**f, "village": VILLAGE, "agent": "memory",
                                                                 "event_id": None, "rule_id": None})
    n = sum(sub.on_event(e) for e in events)
    print(f"enqueued: {len(ob.pending())} facts ({n} from {len(events)} ledger events)")
    t0 = time.perf_counter()
    while ob.pending():
        r = await ob.drain_once()
        if r["failed"]:
            print("drain failed:", ob.last_error, "- retrying in 2 s")
            await asyncio.sleep(2)
    print(f"drained in {time.perf_counter() - t0:.1f} s; outbox {ob.stats()}")

    deps = MemoryDeps(client=client, events=lambda v: events, prescriptions=lambda v: RX,
                      now=lambda: cv.to_dt("2026-10-16T14:00:00-04:00"), timeout_s=30)
    hist_ms = []
    for _ in range(3):
        t = time.perf_counter()
        h = await history_view(deps, VILLAGE, "m_carmen", "lisinopril_dose")
        hist_ms.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    fv = await facts_view(deps, VILLAGE, subject="m_carmen")
    facts_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    fv_asof = await facts_view(deps, VILLAGE, subject="m_carmen", as_of="2026-10-02T12:00:00-04:00")
    facts_asof_ms = (time.perf_counter() - t) * 1000
    q_now = await client.query("What dose of lisinopril does Carmen Reyes take?", village=VILLAGE)
    q_old = await client.query("What dose of lisinopril does Carmen Reyes take?", as_of="2026-09-15T00:00:00Z", village=VILLAGE)

    writes = [ms for label, ms, st in client.timings if label == "remember_fact" and st and st < 300]
    report = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "facts_written": len(writes),
        "write_ms": {"p50": pct(writes, 50), "p90": pct(writes, 90), "max": round(max(writes)) if writes else None},
        "history_ms": {"p50": pct(hist_ms, 50), "runs": [round(x) for x in hist_ms]},
        "facts_view_ms": round(facts_ms), "facts_view_as_of_ms": round(facts_asof_ms),
        "query_ms": {"now": round(q_now.get("ms", 0)), "as_of": round(q_old.get("ms", 0)),
                     "now_tier": q_now.get("tier"), "as_of_tier": q_old.get("tier")},
        "query_top": {"now": [x.get("text") for x in q_now.get("hits", [])[:2]],
                      "as_of_2026_09_15": [x.get("text") for x in q_old.get("hits", [])[:2]]},
        "history": h, "facts_degraded": fv["degraded"],
        "as_of_2026_10_02_lisinopril": [f["value"] for f in fv_asof["facts"] if f["key"] == "lisinopril_dose"],
    }
    (ROOT / "var/memory").mkdir(parents=True, exist_ok=True)
    (ROOT / "var/memory/seed_report.json").write_text(json.dumps(report, indent=2, default=str))

    print("\n== Fact view: Carmen · lisinopril_dose" + (" (DEGRADED)" if h["degraded"] else ""))
    for v in h["versions"]:
        s = v["source"]
        where = f"{s['kind']}:{s['ref']}" + (f" @{s['secs']}s" if "secs" in s else "")
        state = "superseded" if v["superseded"] else "CURRENT"
        print(f"  {state:10} {v['value']:6} since {v['observed_at'][:10]}  source {where}"
              + (f"  \"{s['quote'][:70]}\"" if s.get("quote") else "") + (f"  event {v['event_id']}" if v.get("event_id") else ""))
    print(f"  as_of 2026-10-02 -> {report['as_of_2026_10_02_lisinopril']}")
    print(f"\nfacts view (m_carmen): {len(fv['facts'])} facts, degraded={fv['degraded']}")
    print(f"latency: write p50 {report['write_ms']['p50']} ms (p90 {report['write_ms']['p90']}, n={len(writes)}); "
          f"history p50 {report['history_ms']['p50']} ms; facts view {report['facts_view_ms']} ms; "
          f"facts as_of {report['facts_view_as_of_ms']} ms; query now {report['query_ms']['now']} ms, as_of {report['query_ms']['as_of']} ms")
    print(f"query top now: {report['query_top']['now'][:1]} | asOf 09-15: {report['query_top']['as_of_2026_09_15'][:1]}")
    await client.aclose()
    ok = (not h["degraded"] and [v["value"] for v in h["versions"]][:2] == ["10 mg", "5 mg"])
    print("\nSEED", "OK" if ok else "CHECK OUTPUT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
