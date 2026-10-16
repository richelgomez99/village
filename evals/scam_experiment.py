"""Scam experiment: extraction (Haiku tool call | rules) -> pure gate -> score.

    uv run python -m evals.scam_experiment                 # model if VILLAGE_LLM!=off, else rules
    VILLAGE_LLM=on uv run python -m evals.scam_experiment --mode model
    uv run python -m evals.scam_experiment --mode rules
    uv run python -m evals.scam_experiment --village v_reyes   # base set + evals/sets/v_reyes.jsonl

Outputs evals/out/scam_experiment_<ts>.{json,md}. Numbers come only from this run.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.gate import decide
from evals.extract import Extraction, extract, model_client, to_tool_request
from evals.reyes import DATASETS, EVAL_NOW, ROOT, resolve_member, village_state

OUT = ROOT / "evals" / "out"
SETS = ROOT / "evals" / "sets"
BASE_SET = DATASETS / "scam_eval_set.jsonl"

# Gate decision vocabulary (common.schema.json#/$defs/gate_decision) -> dataset
# expected_decision vocabulary (record | verify_with_member | advise_do_not_send | deny).
# Written out for every gate value so nothing is mapped implicitly.
DECISION_MAP: dict[str, str] = {
    "record": "record",
    "allow": "record",  # nothing blocked: same outcome for Carmen as record
    "remind": "record",
    "report_already_logged": "record",
    "mark_unverified": "record",
    "verify_with_member": "verify_with_member",
    "verify_with_source": "verify_with_member",  # a check before acting
    "require_approval": "verify_with_member",
    "advise_talk_to_coordinator": "verify_with_member",
    "escalate_family": "verify_with_member",
    "advise_do_not_send": "advise_do_not_send",
    "refuse_medical_advice": "advise_do_not_send",
    "advise_911": "advise_do_not_send",
    "deny": "deny",
}
# No report_money_request tool call -> the voice agent records the remark; the gate's money
# rules are never consulted, nothing is blocked.
NO_TOOL_DECISION = "record"

PROTECTIVE = {"verify_with_member", "advise_do_not_send", "deny"}  # stops or checks before money moves
BLOCKING = {"advise_do_not_send", "deny"}


def load_cases(village_id: str | None = None) -> tuple[list[dict[str, Any]], int, int]:
    base = [json.loads(line) for line in BASE_SET.read_text().splitlines() if line.strip()]
    village_rows: list[dict[str, Any]] = []
    if village_id:
        path = SETS / f"{village_id}.jsonl"
        if path.exists():
            for i, line in enumerate(path.read_text().splitlines()):
                if not line.strip():
                    continue
                row = json.loads(line)
                row.setdefault("id", f"{village_id}_{i + 1:03d}")
                row.setdefault("is_scam", row.get("expected_decision") in BLOCKING | {"verify_with_member"})
                row.setdefault("language", "es")
                row.setdefault("channel", "call")
                row["set"] = village_id
                village_rows.append(row)
    for row in base:
        row["set"] = "base"
    return base + village_rows, len(base), len(village_rows)


def gate_input(case: dict[str, Any], tool_req: dict[str, Any], village_id: str = "v_reyes") -> dict[str, Any]:
    """Build the GateInput exactly as Core would for a report_money_request tool call."""
    state = village_state(village_id, EVAL_NOW)
    flags = list(tool_req.get("red_flags", []))
    slug = case["id"].replace("-", "_")
    alloc = {"decision_id": f"dc_eval_{slug}", "verification_id": f"ver_eval_{slug}", "incident_id": f"inc_eval_{slug}"}
    source = {"kind": "call", "ref": tool_req["conversation_id"], "secs": tool_req["call_secs"], "quote": case["utterance"][:600]}
    if "asks_village_to_pay" in flags:
        event = {
            "village": village_id, "kind": "money_transfer_request",
            "payload": {"utterance": case["utterance"], "caller_known": True},
            "actor": "m_carmen", "source": source, "at": EVAL_NOW,
        }
    else:
        claimed_id = resolve_member(tool_req.get("claimed_member"), village_id)
        event = {
            "village": village_id, "kind": "money_request",
            "payload": {
                "subject": "m_carmen",
                "claimed_member_id": claimed_id,  # None == "unknown" -> R-MONEY-UNKNOWN
                "claimed_identity": tool_req.get("claimed_identity", "unknown"),
                "amount": tool_req.get("amount"),
                "currency": tool_req.get("currency", "USD"),
                "method": tool_req.get("method", "unknown"),
                "urgency": tool_req.get("urgency", "unspecified"),
                "red_flags": flags,
                "utterance": case["utterance"],
                "verification_id": None,
            },
            "actor": "m_carmen", "source": source, "at": EVAL_NOW,
        }
    return {"village_state": state, "event": event, "alloc": alloc,
            "idempotency_key": f"{tool_req['conversation_id']}:{tool_req['tool_call_id']}"}


def score(case: dict[str, Any], got: str) -> dict[str, Any]:
    expected = case["expected_decision"]
    is_scam = bool(case["is_scam"])
    caught = is_scam and got in PROTECTIVE
    # False alarm: a benign call got more friction than the family expects:
    # blocked outright, or a verification ping where the expected outcome is just record.
    false_alarm = (not is_scam) and (got in BLOCKING or (got == "verify_with_member" and expected == "record"))
    return {
        "match": got == expected,
        "caught": caught,
        "false_alarm": false_alarm,
        "pass": caught if is_scam else not false_alarm,
    }


def run_case(case: dict[str, Any], mode: str, client: Any = None, model: str | None = None,
             village_id: str = "v_reyes") -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        ex: Extraction = extract(case["utterance"], mode=mode, client=client, model=model)
    except Exception as exc:
        ex = Extraction("error", None, mode, (time.perf_counter() - t0) * 1000, error=f"{type(exc).__name__}: {str(exc)[:200]}")
    tool_req = to_tool_request(ex, case["utterance"], case["id"], village_id)
    g0 = time.perf_counter()
    decision: dict[str, Any] | None = None
    if ex.tool == "error":
        gate_decision, rule = "error", "error"
    elif tool_req is None:
        gate_decision, rule = None, "no_tool_call"
    else:
        decision = decide(gate_input(case, tool_req, village_id))
        gate_decision, rule = decision["decision"], decision["rule_id"]
    gate_ms = (time.perf_counter() - g0) * 1000
    got = "error" if gate_decision == "error" else (NO_TOOL_DECISION if gate_decision is None else DECISION_MAP[gate_decision])
    row = {
        "id": case["id"], "set": case.get("set", "base"), "language": case.get("language"), "channel": case.get("channel"),
        "is_scam": bool(case["is_scam"]), "expected": case["expected_decision"], "got": got,
        "gate_decision": gate_decision, "rule_id": rule,
        "rules_fired": (decision or {}).get("rules_fired", []),
        "tool": ex.tool, "extractor": ex.extractor, "extraction_error": ex.error,
        "claimed_member": (tool_req or {}).get("claimed_member"),
        "claimed_member_id": resolve_member((tool_req or {}).get("claimed_member"), village_id) if tool_req else None,
        "method": (tool_req or {}).get("method"), "amount": (tool_req or {}).get("amount"),
        "red_flags": (tool_req or {}).get("red_flags", []),
        "extract_ms": round(ex.ms, 1), "gate_ms": round(gate_ms, 3),
        "total_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    row.update(score(case, got) if got != "error" else {"match": False, "caught": False, "false_alarm": False, "pass": False})
    return row


def summarize(rows: list[dict[str, Any]], n_base: int, n_village: int) -> dict[str, Any]:
    scams = [r for r in rows if r["is_scam"]]
    benign = [r for r in rows if not r["is_scam"]]
    ext = sorted(r["extract_ms"] for r in rows)
    return {
        "n": len(rows), "n_base": n_base, "n_village": n_village,
        "scams": len(scams), "benign": len(benign),
        "caught": sum(r["caught"] for r in scams),
        "false_alarms": sum(r["false_alarm"] for r in benign),
        "blocked_benign": sum(r["got"] in BLOCKING for r in benign),
        "exact_match": sum(r["match"] for r in rows),
        "errors": sum(r["got"] == "error" for r in rows),
        "extraction_errors": sum(bool(r["extraction_error"]) for r in rows),
        "extract_ms_p50": ext[len(ext) // 2] if ext else None,
        "extract_ms_p95": ext[min(len(ext) - 1, int(len(ext) * 0.95))] if ext else None,
        "gate_ms_max": max((r["gate_ms"] for r in rows), default=None),
    }


def run(mode: str = "auto", village_id: str | None = None, out_dir: Path = OUT, write: bool = True) -> dict[str, Any]:
    cases, n_base, n_village = load_cases(village_id)
    client, model = (None, None)
    if mode in {"auto", "model"}:
        client, model = model_client()
        if client is None:
            if mode == "model":
                raise SystemExit(f"--mode model but the model is unavailable ({model}); set VILLAGE_LLM=on")
            mode_used = "rules"
        else:
            mode_used = "model"
    else:
        mode_used = "rules"
    t0 = time.perf_counter()
    rows = [run_case(c, mode_used, client, model, village_id or "v_reyes") for c in cases]
    wall = time.perf_counter() - t0
    summary = summarize(rows, n_base, n_village)
    summary["model_extractions"] = sum(r["extractor"].startswith("model:") for r in rows)
    if mode_used == "model" and summary["model_extractions"] < len(rows):
        mode_used = f"model(rules fallback on {len(rows) - summary['model_extractions']})"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "name": "village-scam-eval", "ts": ts, "mode": mode_used,
        "model": model if mode_used == "model" else None,
        "village": village_id, "eval_clock": EVAL_NOW, "wall_s": round(wall, 2),
        "headline": f"{summary['caught']}/{summary['scams']} caught, {summary['false_alarms']}/{summary['benign']} false alarms",
        "summary": summary,
        "definitions": {
            "caught": "scam case whose mapped decision is verify_with_member, advise_do_not_send or deny",
            "false_alarm": "benign case mapped to advise_do_not_send/deny, or to verify_with_member when expected is record",
            "decision_map": DECISION_MAP, "no_tool_call": NO_TOOL_DECISION,
        },
        "rows": rows,
    }
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"scam_experiment_{ts}_{mode_used}" + (f"_{village_id}" if village_id else "")
        (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        (out_dir / f"{stem}.md").write_text(to_markdown(report))
        report["paths"] = [str(out_dir / f"{stem}.json"), str(out_dir / f"{stem}.md")]
    return report


def to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# Scam experiment {report['ts']}",
        "",
        f"**{report['headline']}** (mode `{report['mode']}`, model `{report['model']}`, cases n_base {s['n_base']} + n_village {s['n_village']} = {s['n']})",
        "",
        f"- exact decision match: {s['exact_match']}/{s['n']}; benign blocked outright: {s['blocked_benign']}/{s['benign']}; errors: {s['errors']}; extraction errors: {s['extraction_errors']}",
        f"- extraction p50 {s['extract_ms_p50']} ms, p95 {s['extract_ms_p95']} ms; gate max {s['gate_ms_max']} ms; wall {report['wall_s']} s",
        f"- caught = {report['definitions']['caught']}; false alarm = {report['definitions']['false_alarm']}",
        "",
        "| id | set | scam | expected | got | rule | claimed | extractor | pass | extract ms |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        lines.append(
            f"| {r['id']} | {r['set']} | {'Y' if r['is_scam'] else 'N'} | {r['expected']} | {r['got']} | {r['rule_id']} | "
            f"{r['claimed_member_id'] or '-'} | {r['extractor']} | {'PASS' if r['pass'] else 'FAIL'} | {r['extract_ms']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "model", "rules"], default="auto")
    ap.add_argument("--village", default=None, help="also score evals/sets/<village>.jsonl")
    ap.add_argument("--arize", action="store_true", help="log the run to Arize as an experiment (needs arize SDK)")
    args = ap.parse_args()
    _load_env()
    report = run(args.mode, args.village)
    s = report["summary"]
    print(report["headline"], f"| mode={report['mode']} model={report['model']} n_base={s['n_base']} n_village={s['n_village']}")
    print(f"exact {s['exact_match']}/{s['n']} errors {s['errors']} p50 {s['extract_ms_p50']}ms wall {report['wall_s']}s")
    for path in report.get("paths", []):
        print(path)
    if args.arize:
        from evals.arize_experiment import log_experiment

        print(json.dumps(log_experiment(report), indent=2))


def _load_env() -> None:
    from evals.env import load_env

    load_env()


if __name__ == "__main__":
    main()
