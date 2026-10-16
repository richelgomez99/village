import sys
import types

import json
import pytest

from evals import arize_experiment as ae


class FakeDF:
    def __init__(self, rows):
        self.rows = rows
        self.columns = sorted({k for r in rows for k in r})

    def get(self, col, default=None):
        return [r.get(col) for r in self.rows] if col in self.columns else default

    def __len__(self):
        return len(self.rows)

    def __contains__(self, col):
        return col in self.columns

    def to_json(self, orient="records", default_handler=str):
        return json.dumps(self.rows, default=default_handler)


class _ER:
    def __init__(self, score=None, label=None, explanation=None):
        self.score, self.label, self.explanation = score, label, explanation


@pytest.fixture
def fake_arize(monkeypatch):
    """Minimal stand-in for arize.experimental.datasets (Arize mocked offline)."""
    types_mod = types.ModuleType("arize.experimental.datasets.experiments.types")
    types_mod.EvaluationResult = _ER
    const = types.ModuleType("arize.experimental.datasets.utils.constants")
    const.GENERATIVE = 1
    for name, mod in {"arize.experimental.datasets.experiments.types": types_mod,
                      "arize.experimental.datasets.utils.constants": const}.items():
        monkeypatch.setitem(sys.modules, name, mod)

    class Client:
        created = []

        def list_datasets(self, space_id):
            return None

        def create_dataset(self, space_id, dataset_name, dataset_type, data):
            self.data = [dict(r, is_scam=str(r["is_scam"])) for r in data]  # Arize returns strings
            Client.created.append((dataset_name, len(data)))
            return "ds_1"

        def get_dataset(self, space_id, dataset_id):
            return self.data

        def run_experiment(self, space_id, dataset_id, dataset_df, experiment_name, task, evaluators, **kw):
            rows = []
            for r in dataset_df:
                out = task(dict(r))
                row = {"result": out}
                for ev in evaluators:
                    res = ev(out, dict(r))
                    row[f"eval.{ev.__name__}.label"] = res.label
                rows.append(row)
            return "exp_1", FakeDF(rows)

    monkeypatch.setattr(ae, "_client", lambda: Client())
    monkeypatch.setattr(ae, "dataset_frame", lambda cases: [
        {"case_id": c["id"], "utterance": c["utterance"], "is_scam": bool(c["is_scam"]),
         "expected_decision": c["expected_decision"], "language": c["language"], "channel": c["channel"]} for c in cases])
    monkeypatch.setenv("ARIZE_SPACE_ID", "space")
    return Client


def test_logs_dataset_and_experiment(fake_arize, tmp_path, monkeypatch):
    monkeypatch.setattr(ae, "OUT", tmp_path)
    res = ae.log_experiment(mode="rules")
    assert "error" not in res, res
    assert fake_arize.created == [("village-scam-eval", 50)]
    assert res["experiment_id"] == "exp_1" and res["mode"] == "rules"
    assert res["headline"].endswith("/30 caught, 0/20 false alarms")
    assert (tmp_path / f"arize_experiment_{res['ts']}.json").exists()


def test_sdk_failure_is_recorded_not_raised(monkeypatch, tmp_path):
    monkeypatch.setattr(ae, "OUT", tmp_path)
    monkeypatch.setenv("ARIZE_SPACE_ID", "space")

    def boom():
        raise ConnectionError("flight down")

    monkeypatch.setattr(ae, "_client", boom)
    res = ae.log_experiment(mode="rules")
    assert res["error"].startswith("ConnectionError: flight down")
    assert list(tmp_path.glob("arize_experiment_*_error.json"))
