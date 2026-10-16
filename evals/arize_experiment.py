"""Log the scam experiment to Arize: dataset `village-scam-eval` + run_experiment.

    VILLAGE_LLM=on uv run --with boto3 --with 'arize[Datasets]<8' python -m evals.arize_experiment

The experiment task runs the same pipeline as evals.scam_experiment (extraction ->
pure gate) per example inside Arize's runner; code evaluators `caught` and
`false_alarm` score it. A local mirror of every run goes to evals/out/. On any SDK
failure the exact error is returned and recorded; the local result stays the number.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from evals.reyes import ROOT

DATASET_NAME = "village-scam-eval"
OUT = ROOT / "evals" / "out"


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _client():
    from arize.experimental.datasets import ArizeDatasetsClient

    return ArizeDatasetsClient(api_key=os.environ["ARIZE_API_KEY"])


def dataset_frame(cases: list[dict[str, Any]]):
    import pandas as pd

    rows = []
    for c in cases:
        rows.append({
            "case_id": c["id"], "language": c["language"], "channel": c["channel"], "utterance": c["utterance"],
            "claimed_identity": c["claimed_identity"], "is_scam": bool(c["is_scam"]),
            "red_flags": json.dumps(c.get("red_flags", [])), "expected_decision": c["expected_decision"],
            "rationale": c.get("rationale", ""),
        })
    return pd.DataFrame(rows)


def ensure_dataset(client, space_id: str, cases: list[dict[str, Any]]) -> tuple[str, bool]:
    """Return (dataset_id, created)."""
    from arize.experimental.datasets.utils.constants import GENERATIVE

    try:
        listing = client.list_datasets(space_id)
        hit = listing[listing["dataset_name"] == DATASET_NAME] if listing is not None and len(listing) else []
        if len(hit):
            return str(hit.iloc[0]["dataset_id"]), False
    except Exception:
        pass
    dataset_id = client.create_dataset(space_id=space_id, dataset_name=DATASET_NAME, dataset_type=GENERATIVE,
                                       data=dataset_frame(cases))
    return str(dataset_id), True


def make_task(mode: str):
    from evals.extract import model_client
    from evals.scam_experiment import run_case

    client, model = (None, None) if mode == "rules" else model_client()
    used = "model" if client is not None else "rules"

    def task(dataset_row) -> dict[str, Any]:
        row = dict(dataset_row)
        case = {
            "id": row["case_id"], "utterance": row["utterance"], "is_scam": _truthy(row["is_scam"]),
            "expected_decision": row["expected_decision"], "language": row.get("language"), "channel": row.get("channel"),
        }
        return run_case(case, used, client, model)

    return task, used, model


def caught(output, dataset_row):
    from arize.experimental.datasets.experiments.types import EvaluationResult

    if not _truthy(dataset_row.get("is_scam")):
        return EvaluationResult(score=0.0, label="n/a", explanation="benign case")
    ok = bool((output or {}).get("caught"))
    return EvaluationResult(score=1.0 if ok else 0.0, label="caught" if ok else "missed",
                            explanation=f"got {(output or {}).get('got')} via {(output or {}).get('rule_id')}")


def false_alarm(output, dataset_row):
    from arize.experimental.datasets.experiments.types import EvaluationResult

    if _truthy(dataset_row.get("is_scam")):
        return EvaluationResult(score=0.0, label="n/a", explanation="scam case")
    bad = bool((output or {}).get("false_alarm"))
    return EvaluationResult(score=1.0 if bad else 0.0, label="false_alarm" if bad else "ok",
                            explanation=f"expected {dataset_row.get('expected_decision')}, got {(output or {}).get('got')}")


def decision_match(output, dataset_row):
    from arize.experimental.datasets.experiments.types import EvaluationResult

    ok = (output or {}).get("got") == dataset_row.get("expected_decision")
    return EvaluationResult(score=1.0 if ok else 0.0, label="match" if ok else "mismatch",
                            explanation=f"expected {dataset_row.get('expected_decision')}, got {(output or {}).get('got')}")


def log_experiment(local_report: dict[str, Any] | None = None, mode: str = "auto") -> dict[str, Any]:
    from evals.scam_experiment import load_cases

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result: dict[str, Any] = {"ts": ts, "dataset": DATASET_NAME, "project": os.environ.get("ARIZE_PROJECT_NAME", "village")}
    if local_report:
        result["local_headline"] = local_report.get("headline")
    try:
        space_id = os.environ["ARIZE_SPACE_ID"]
        client = _client()
        cases, _, _ = load_cases(None)
        dataset_id, created = ensure_dataset(client, space_id, cases)
        result.update(dataset_id=dataset_id, dataset_created=created, n_examples=len(cases))
        task, used, model = make_task(mode)
        name = f"scam-{used}-{ts}"
        dataset_df = None
        for attempt in range(5):  # a freshly created dataset is not downloadable for a few seconds
            try:
                dataset_df = client.get_dataset(space_id=space_id, dataset_id=dataset_id)
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        if dataset_df is None:
            raise RuntimeError(f"dataset {dataset_id} not downloadable after retries")
        out = client.run_experiment(space_id=space_id, dataset_id=dataset_id, dataset_df=dataset_df,
                                    experiment_name=name, task=task,
                                    evaluators=[caught, false_alarm, decision_match], concurrency=3, timeout=120)
        if out is None:
            raise RuntimeError("run_experiment returned None")
        experiment_id, df = out
        result.update(experiment_id=str(experiment_id), experiment_name=name, mode=used, model=model)
        labels_c = list(df.get("eval.caught.label", []))
        labels_f = list(df.get("eval.false_alarm.label", []))
        n_scam = sum(lbl in {"caught", "missed"} for lbl in labels_c)
        n_benign = sum(lbl in {"false_alarm", "ok"} for lbl in labels_f)
        result["headline"] = (f"{labels_c.count('caught')}/{n_scam} caught, "
                              f"{labels_f.count('false_alarm')}/{n_benign} false alarms")
        result["decision_match"] = f"{list(df.get('eval.decision_match.label', [])).count('match')}/{len(df)}"
        result["columns"] = list(df.columns)
        mirror = OUT / f"arize_experiment_{ts}.json"
        OUT.mkdir(parents=True, exist_ok=True)
        mirror.write_text(json.dumps({**result, "runs": json.loads(df.to_json(orient="records", default_handler=str))},
                                     indent=2, ensure_ascii=False))
        result["mirror"] = str(mirror)
    except Exception as exc:
        chain, cur = [], exc
        while cur is not None and len(chain) < 6:
            chain.append(f"{type(cur).__name__}: {str(cur)[:400]}")
            cur = cur.__cause__ or cur.__context__
        result["error"] = " <- ".join(chain)
        result["traceback"] = traceback.format_exc()[-1500:]
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"arize_experiment_{ts}_error.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    import argparse

    from evals.env import load_env

    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "rules"], default="auto")
    args = ap.parse_args()
    load_env()
    res = log_experiment(mode=args.mode)
    res.pop("traceback", None) if "error" not in res else None
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
