import json

from evals import scam_experiment as se
from evals.extract import extract, extract_with_rules, to_tool_request
from evals.tests.fakes import BoomClient, FakeClient
from evals.tests.schema_util import errors


def _gate_vocab():
    return json.loads((se.ROOT / "contracts/schemas/common.schema.json").read_text())["$defs"]["gate_decision"]["enum"]


def test_decision_map_covers_gate_vocabulary_and_dataset_values():
    assert set(se.DECISION_MAP) == set(_gate_vocab())
    cases, _, _ = se.load_cases()
    assert {c["expected_decision"] for c in cases} <= set(se.DECISION_MAP.values())


def test_rules_run_offline_scores_all_50(tmp_path):
    report = se.run("rules", out_dir=tmp_path)
    s = report["summary"]
    assert (s["n"], s["scams"], s["benign"], s["errors"]) == (50, 30, 20, 0)
    assert s["blocked_benign"] == 0  # benign rows are never blocked outright
    assert report["headline"] == f"{s['caught']}/30 caught, {s['false_alarms']}/20 false alarms"
    assert len(list(tmp_path.glob("scam_experiment_*.json"))) == 1
    md = next(tmp_path.glob("*.md")).read_text()
    assert "| se_s02 |" in md and "caught" in md


def test_headline_case_goes_to_verify_with_member():
    case = next(c for c in se.load_cases()[0] if c["id"] == "se_s02")
    row = se.run_case(case, "rules")
    assert row["got"] == "verify_with_member" and row["rule_id"] == "R-MONEY-VERIFY" and row["caught"]
    assert "R-MONEY-PATTERN" in row["rules_fired"]  # the Oct 9 seed request is in recent_money_requests


def test_gate_input_is_contract_valid():
    case = next(c for c in se.load_cases()[0] if c["id"] == "se_s05")
    req = to_tool_request(extract_with_rules(case["utterance"]), case["utterance"], case["id"])
    assert not errors("voice_tools.schema.json", "/$defs/req_report_money_request", req)
    inp = se.gate_input(case, req)
    assert not errors("gate.schema.json", "/$defs/gate_input", inp)
    assert inp["event"]["payload"]["claimed_member_id"] is None  # IRS -> unknown


def test_unknown_claimant_and_village_pay():
    cases = {c["id"]: c for c in se.load_cases()[0]}
    assert se.run_case(cases["se_s01"], "rules")["got"] == "advise_do_not_send"
    assert se.run_case(cases["se_s29"], "rules")["got"] == "deny"
    assert se.run_case(cases["se_b05"], "rules")["got"] == "record"


def test_model_path_uses_tool_call():
    def fn(kw):
        assert kw["tool_choice"] == {"type": "any"}
        return "report_money_request", {"claimed_member": "lucia", "urgency": "now", "claimed_identity": "Lucía",
                                        "method": "payment_app_to_stranger", "red_flags": ["payment_app_to_stranger", "bogus"]}

    client = FakeClient(fn)
    case = next(c for c in se.load_cases()[0] if c["id"] == "se_s21")
    row = se.run_case(case, "model", client, "fake-haiku")
    assert row["extractor"] == "model:fake-haiku" and row["claimed_member_id"] == "m_lucia"
    assert row["got"] == "verify_with_member" and row["red_flags"] == ["payment_app_to_stranger"]


def test_model_not_a_request_records():
    client = FakeClient(lambda kw: ("not_a_money_request", {"reason": "info"}))
    case = next(c for c in se.load_cases()[0] if c["id"] == "se_b03")
    row = se.run_case(case, "model", client, "fake-haiku")
    assert row["got"] == "record" and row["rule_id"] == "no_tool_call" and not row["false_alarm"]


def test_model_error_falls_back_and_is_flagged():
    ex = extract("Marco needs two thousand dollars right now", mode="model", client=BoomClient(), model="x")
    assert ex.extractor == "rules(model_error)" and ex.error.startswith("model_error:TimeoutError")
    assert ex.request["claimed_member"] == "marco"


def test_scoring_definitions():
    assert se.score({"expected_decision": "record", "is_scam": False}, "verify_with_member")["false_alarm"]
    assert not se.score({"expected_decision": "verify_with_member", "is_scam": False}, "verify_with_member")["false_alarm"]
    assert se.score({"expected_decision": "record", "is_scam": False}, "deny")["false_alarm"]
    assert se.score({"expected_decision": "advise_do_not_send", "is_scam": True}, "verify_with_member")["caught"]
    assert not se.score({"expected_decision": "advise_do_not_send", "is_scam": True}, "record")["caught"]


def test_auto_mode_without_model_uses_rules(tmp_path):
    report = se.run("auto", out_dir=tmp_path, write=False)
    assert report["mode"] == "rules" and report["model"] is None
