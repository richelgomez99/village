"""The builder's DailyMed label check reaches memory through the outbox (fixtures, no network)."""
from core.builder.founding import BuilderRun, FoundingOptions, Ledger, check_medications
from core.builder.services_stub import MemoryServices
from core.memory.outbox import Outbox

VILLAGE, CARMEN = "v_reyes", "m_carmen"
LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=34ebeea1-6812-4697-84c4-b2ae4f39e55f"


async def _check(tmp_path, meds, dailymed="fixture", svc=None):
    svc = svc or MemoryServices(outbox=Outbox(tmp_path / "outbox.jsonl"))
    run = BuilderRun(VILLAGE, "tr_test")
    await check_medications(run, svc, FoundingOptions(dailymed=dailymed), meds, Ledger(svc, run), CARMEN)
    return svc, run


async def test_checked_lookup_enqueues_one_fact_with_url_provenance(tmp_path):
    svc, _ = await _check(tmp_path, ["lisinopril"])
    items = list(svc.outbox.items.values())
    assert len(items) == 1 and items[0]["kind"] == "fact" and items[0]["status"] == "queued"
    assert items[0]["id"] == f"dailymed:{VILLAGE}:{CARMEN}:lisinopril:34ebeea1-6812-4697-84c4-b2ae4f39e55f"
    a = items[0]["args"]
    assert a["entity"] == CARMEN and a["village"] == VILLAGE
    assert a["key"] == "med_label_lisinopril"
    assert a["value"] == "LISINOPRIL TABLET [BLUEPOINT LABORATORIES]"
    assert a["observed_at"].startswith("2026-10-09")  # the label's published date
    assert a["source"] == {"kind": "url", "ref": "dailymed", "url": LABEL_URL}
    assert a["agent"] == "builder" and a["extra_labels"] == {"src": "url:dailymed"}
    assert a["event_id"] is None and a["rule_id"] is None


async def test_second_run_enqueues_nothing_new(tmp_path):
    svc, _ = await _check(tmp_path, ["lisinopril", "metformin"])
    assert len(svc.outbox.items) == 2
    await _check(tmp_path, ["lisinopril", "metformin"], svc=svc)
    assert len(svc.outbox.items) == 2
    # a restart reads the same file: still nothing new
    fresh = MemoryServices(outbox=Outbox(tmp_path / "outbox.jsonl"))
    await _check(tmp_path, ["lisinopril", "metformin"], svc=fresh)
    assert len(fresh.outbox.items) == 2


async def test_no_center_falls_back_to_the_village(tmp_path):
    svc = MemoryServices(outbox=Outbox(tmp_path / "outbox.jsonl"))
    run = BuilderRun(VILLAGE, "tr_test")
    await check_medications(run, svc, FoundingOptions(dailymed="fixture"), ["lisinopril"], Ledger(svc, run), None)
    assert [i["args"]["entity"] for i in svc.outbox.items.values()] == ["village"]


async def test_unchecked_lookups_write_nothing_to_memory(tmp_path):
    svc, _ = await _check(tmp_path, ["lisinopril"], dailymed="off")
    assert not svc.outbox.items and not svc.decisions
    svc, run = await _check(tmp_path, ["nosuchdrug"])  # fixture has no label: a fallback row
    assert not svc.outbox.items and not svc.decisions
    assert any("fallback" in line for line in run.ledger)


async def test_ledger_decision_is_still_written(tmp_path):
    svc, run = await _check(tmp_path, ["lisinopril"])
    assert len(svc.decisions) == 1
    d = svc.decisions[0]
    assert d["source"] == {"kind": "url", "ref": "dailymed", "url": LABEL_URL}
    assert "Checked lisinopril on DailyMed" in str(d) and "Oct 09, 2026" in str(d)
    assert {"kind": "fact", "id": "med_label:lisinopril"} in d["refs"]
    assert len(run.facts) == 1


async def test_no_outbox_means_no_memory_write_and_no_error(tmp_path):
    svc, _ = await _check(tmp_path, ["lisinopril"], svc=MemoryServices())
    assert svc.outbox is None and len(svc.decisions) == 1
