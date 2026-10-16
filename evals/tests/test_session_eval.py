import json

from evals import session_eval as sev
from evals.reyes import seed_events
from evals.tests.fakes import BoomClient, FakeClient


def test_seed_call_is_possible_fraud_rules(tmp_path):
    res = sev.evaluate_session("conv_seed_1009", seed_events("v_reyes"), use_model=False, mirror_dir=tmp_path)
    assert res.label == "possible_fraud" and res.score == 1.0 and "gift_card" in res.explanation
    assert res.judge == "rules"
    mirror = json.loads((tmp_path / "conv_seed_1009.json").read_text())
    assert mirror["label"] == "possible_fraud"
    assert sev.sessions_with_label(mirror_dir=tmp_path).keys() == {"conv_seed_1009"}


def test_call_without_money_is_benign(tmp_path):
    events = [{"id": "ev_a", "kind": "dose", "payload": {}, "source": {"kind": "call", "ref": "conv_b", "secs": 3}}]
    res = sev.evaluate_session("conv_b", events, use_model=False, mirror_dir=tmp_path)
    assert res.label == "benign" and res.score == 0.0


def test_money_without_impersonation_is_benign():
    ctx = {"money_requests": [{"claimed_member_id": None, "claimed_identity": "unknown", "red_flags": [], "method": "unknown"}]}
    assert sev.judge_rules(ctx)[0] == "benign"


def test_model_judge_and_fallback(tmp_path):
    fake = FakeClient(lambda kw: ("label_session", {"label": "possible_fraud", "score": 0.9, "explanation": "gift cards"}))
    res = sev.evaluate_session("conv_seed_1009", seed_events("v_reyes"), client=fake, model="fake", mirror_dir=tmp_path)
    assert res.judge == "model:fake" and res.score == 0.9
    res2 = sev.evaluate_session("conv_seed_1009", seed_events("v_reyes"), client=BoomClient(), model="x", mirror_dir=tmp_path)
    assert res2.judge.startswith("rules(judge_error") and res2.label == "possible_fraud"


def test_update_evaluations_called_with_root_span(monkeypatch, tmp_path):
    calls = []
    import evals.arize_io as aio

    monkeypatch.setattr(aio, "update_evaluations", lambda rows, **kw: calls.append(rows) or {"ok": True})
    res = sev.evaluate_session("conv_seed_1009", seed_events("v_reyes"), use_model=False, root_span_id="00f067aa0ba902b7",
                               mirror_dir=tmp_path)
    assert res.arize == {"ok": True}
    assert calls[0][0]["span_id"] == "00f067aa0ba902b7" and calls[0][0]["name"] == "session_possible_fraud"


def test_update_evaluations_never_raises_without_keys():
    from evals.arize_io import update_evaluations

    assert update_evaluations([{"span_id": "x", "name": "n", "label": "l"}]) == {"ok": False, "error": "no_arize_keys"}
