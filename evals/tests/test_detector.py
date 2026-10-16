import json

from evals.detector import detect_patterns
from evals.reyes import ROOT, seed_events
from evals.tests.schema_util import errors


def _today():
    ex = json.loads((ROOT / "contracts/schemas/event.schema.json").read_text())["examples"]
    return next(e for e in ex if e["id"] == "ev_1016_1402_money")


def test_seed_plus_today_gives_one_pattern_with_schema_valid_evidence():
    pats = detect_patterns("v_reyes", seed_events("v_reyes") + [_today()])
    assert len(pats) == 1
    p = pats[0]
    assert p["claimed_member_id"] == "m_marco" and p["count"] == 2
    assert p["event_ids"] == ["ev_1009_1921_money", "ev_1016_1402_money"]
    assert p["call_moments"] == ["conv_seed_1009@21", "conv_demo_1016_scam@9"]
    assert p["trace_ids"] == ["5a0c9e3b7d214f6c8e1f2a3b4c5d6e7f"]
    assert {e["kind"] for e in p["evidence"]} == {"call_moment", "trace", "fact"}
    assert 3 <= len(p["evidence"]) <= 12
    for ev in p["evidence"]:
        assert not errors("proposal.schema.json", "/$defs/evidence", ev), ev
    assert p["detected_by"] == "memory_pattern"


def test_session_label_attaches_eval_and_switches_detected_by():
    labels = {"conv_seed_1009": {"label": "possible_fraud", "score": 1.0}}
    p = detect_patterns("v_reyes", seed_events("v_reyes") + [_today()], session_labels=labels)[0]
    trace = next(e for e in p["evidence"] if e["kind"] == "trace")
    assert trace["eval"] == {"name": "session_possible_fraud", "label": "possible_fraud", "score": 1.0}
    assert p["detected_by"] == "arize_eval"
    assert not errors("proposal.schema.json", "/$defs/evidence", trace)


def test_single_request_or_outside_window_is_not_a_pattern():
    assert detect_patterns("v_reyes", seed_events("v_reyes")) == []
    late = json.loads(json.dumps(_today()))
    late["at"] = "2026-10-17T14:02:09-04:00"  # 8 days after Oct 9
    assert detect_patterns("v_reyes", seed_events("v_reyes") + [late]) == []


def test_different_members_do_not_group():
    other = json.loads(json.dumps(_today()))
    other["payload"]["claimed_member_id"] = "m_ana"
    assert detect_patterns("v_reyes", seed_events("v_reyes") + [other]) == []


def test_qa_sessions_ignored():
    qa = json.loads(json.dumps(_today()))
    qa["source"]["ref"] = "conv_x_qa"
    assert detect_patterns("v_reyes", seed_events("v_reyes") + [qa]) == []
