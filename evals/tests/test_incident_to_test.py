import json

from evals import incident_to_test as itt
from evals import scam_experiment as se
from evals.reyes import seed_events


def _resolution(events):
    return next(e for e in events if e["kind"] == "verification_timeout")


def test_one_resolved_verification_adds_exactly_one_row(tmp_path):
    events = seed_events("v_reyes")
    row = itt.on_verification_resolved("v_reyes", _resolution(events), events, sets_dir=tmp_path)
    lines = (tmp_path / "v_reyes.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0]) == row
    assert row["expected_decision"] == "verify_with_member" and row["outcome"] == "timeout"
    assert "tarjetas de regalo" in row["utterance"]
    # the same verification again: no duplicate
    assert itt.on_verification_resolved("v_reyes", _resolution(events), events, sets_dir=tmp_path) is None
    assert len((tmp_path / "v_reyes.jsonl").read_text().splitlines()) == 1


def test_denied_counts_confirmed_does_not(tmp_path):
    events = list(seed_events("v_reyes"))
    money = next(e for e in events if e["kind"] == "money_request")
    m2 = json.loads(json.dumps(money))
    m2["id"], m2["payload"]["verification_id"] = "ev_x_money", "ver_x"
    m2["payload"]["claimed_member_id"] = None
    events.append(m2)
    confirmed = {"id": "ev_c", "kind": "verification_confirmed", "payload": {"verification_id": "ver_x"}}
    assert itt.on_verification_resolved("v_reyes", confirmed, events, sets_dir=tmp_path) is None
    denied = {"id": "ev_d", "kind": "verification_denied", "payload": {"verification_id": "ver_x"}, "at": "2026-10-16T14:03:00-04:00"}
    row = itt.on_verification_resolved("v_reyes", denied, events, sets_dir=tmp_path)
    assert row["outcome"] == "denied" and row["expected_decision"] == "advise_do_not_send"


def test_experiment_reports_base_plus_village(tmp_path, monkeypatch):
    events = seed_events("v_reyes")
    itt.sync_from_events("v_reyes", events, sets_dir=tmp_path)
    monkeypatch.setattr(se, "SETS", tmp_path)
    report = se.run("rules", "v_reyes", out_dir=tmp_path, write=False)
    s = report["summary"]
    assert (s["n_base"], s["n_village"], s["n"]) == (50, 1, 51)
    village_row = next(r for r in report["rows"] if r["set"] == "v_reyes")
    assert village_row["got"] == "verify_with_member" and village_row["caught"]
