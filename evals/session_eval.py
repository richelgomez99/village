"""Session eval `session_possible_fraud`: label a call `possible_fraud` | `benign`.

A call is possible_fraud when someone asked for money (a money_request in the
session) AND the requester impersonated or spoke for someone (claimed family member,
third party, new number, changed voice, government/bank/company) or used a hard
scam method (gift cards, crypto, wire to a stranger, courier, bank details).

Model on: Haiku judges the session context in-process (forced tool call).
Model off (or model error): the deterministic rule above.
The result is logged as an EVALUATOR span (eval.session_possible_fraud.*) in the
call's session, sent to Arize with update_evaluations when the call root span id is
known, and mirrored to var/evals/sessions/<conversation_id>.json.

    uv run python -m evals.session_eval conv_seed_1009
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.obs.tracing import span
from evals.reyes import ROOT, seed_events

EVAL_NAME = "session_possible_fraud"
MIRROR = ROOT / "var" / "evals" / "sessions"
IMPERSONATION_FLAGS = {"claimed_family_member", "new_number", "voice_changed", "third_party_for_member", "secrecy",
                       "gov_impersonation", "bank_impersonation", "care_team_impersonation", "tech_support"}
HARD_FLAGS = {"gift_card", "crypto", "wire_to_stranger", "cash_courier", "bank_details", "payment_app_to_stranger",
              "safe_account", "jail_bail", "threat_arrest", "asks_village_to_pay"}


@dataclass
class SessionEval:
    conversation_id: str
    label: str
    score: float
    explanation: str
    judge: str
    ms: float
    trace_id: str | None = None
    span_id: str | None = None
    arize: dict[str, Any] | None = None
    event_ids: list[str] | None = None


def session_context(conversation_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [e for e in events if (e.get("source") or {}).get("ref") == conversation_id]
    money = [e for e in rows if e["kind"] == "money_request"]
    return {
        "conversation_id": conversation_id,
        "event_ids": [e["id"] for e in rows],
        "money_requests": [e["payload"] | {"secs": e["source"].get("secs"), "at": e.get("at")} for e in money],
        "decisions": sorted({e.get("decision_id") for e in rows if e.get("decision_id")}),
        "kinds": [e["kind"] for e in rows],
        "trace_ids": sorted({(e.get("am") or {}).get("trace_id") for e in rows if (e.get("am") or {}).get("trace_id")}),
    }


def judge_rules(ctx: dict[str, Any]) -> tuple[str, float, str]:
    if not ctx["money_requests"]:
        return "benign", 0.0, "no money request in this call"
    best = ("benign", 0.0, "money request without impersonation or scam method")
    for mr in ctx["money_requests"]:
        flags = set(mr.get("red_flags") or [])
        claimed = mr.get("claimed_member_id")
        impersonation = bool(claimed) or bool(flags & IMPERSONATION_FLAGS) or mr.get("claimed_identity") not in (None, "", "unknown")
        hard = flags & HARD_FLAGS | ({mr.get("method")} & HARD_FLAGS)
        who = f"claimed {claimed}" if claimed else f"claimed '{mr.get('claimed_identity', 'unknown')}'"
        amount = f"${mr['amount']:,.0f}" if isinstance(mr.get("amount"), (int, float)) else "money"
        if impersonation and hard:
            best = max(best, ("possible_fraud", 1.0, f"{who} asked for {amount} via {', '.join(sorted(hard))}"), key=lambda b: b[1])
        elif impersonation:
            best = max(best, ("possible_fraud", 0.8, f"{who} asked for {amount}; flags: {', '.join(sorted(flags)) or 'none'}"), key=lambda b: b[1])
    return best


JUDGE_SYSTEM = (
    "You review one phone call to an elder's safety line, given as structured events. Label it possible_fraud when "
    "someone asked her for money or account details AND the requester impersonated or spoke for someone (a family "
    "member, a third party for a family member, a government agency, bank, or company), especially with gift cards, "
    "crypto, wires, couriers, secrecy or urgency. Otherwise benign. Call the tool once."
)


def judge_model(ctx: dict[str, Any], client: Any, model: str) -> tuple[str, float, str]:
    msg = client.messages.create(
        model=model, max_tokens=300, system=JUDGE_SYSTEM,
        tools=[{"name": "label_session", "description": "Label the call.", "input_schema": {
            "type": "object", "required": ["label", "score", "explanation"],
            "properties": {"label": {"type": "string", "enum": ["possible_fraud", "benign"]},
                           "score": {"type": "number", "minimum": 0, "maximum": 1},
                           "explanation": {"type": "string"}}}}],
        tool_choice={"type": "tool", "name": "label_session"},
        messages=[{"role": "user", "content": json.dumps({k: ctx[k] for k in ("money_requests", "kinds")}, ensure_ascii=False, default=str)}],
        timeout=20,
    )
    block = next(b for b in msg.content if getattr(b, "type", "") == "tool_use")
    args = dict(block.input)
    label = args.get("label") if args.get("label") in {"possible_fraud", "benign"} else "benign"
    return label, float(args.get("score", 1.0 if label == "possible_fraud" else 0.0)), str(args.get("explanation", ""))[:500]


def evaluate_session(conversation_id: str, events: list[dict[str, Any]], *, village_id: str = "v_reyes",
                     root_span_id: str | None = None, use_model: bool = True, client: Any = None, model: str | None = None,
                     send_to_arize: bool = True, mirror_dir: Path | None = MIRROR) -> SessionEval:
    ctx = session_context(conversation_id, events)
    t0 = time.perf_counter()
    judge = "rules"
    with span("EVALUATOR", EVAL_NAME, village_id=village_id, node_id=f"eval:{EVAL_NAME}",
              parent_id=root_span_id or conversation_id, user_id="m_carmen",
              input={"conversation_id": conversation_id, "event_ids": ctx["event_ids"]}) as s:
        if use_model and client is None:
            from evals.extract import model_client

            client, model = model_client()
        label, score, why = judge_rules(ctx)
        if use_model and client is not None:
            try:
                label, score, why = judge_model(ctx, client, model or "")
                judge = f"model:{model}"
            except Exception as exc:
                judge = f"rules(judge_error:{type(exc).__name__})"
        s.set_eval(EVAL_NAME, label, score, why)
        s.set_attribute("conversation.id", conversation_id)
        s.set_output({"label": label, "score": score, "explanation": why})
        result = SessionEval(conversation_id, label, score, why, judge, round((time.perf_counter() - t0) * 1000, 1),
                             trace_id=s.trace_id, span_id=s.span_id, event_ids=ctx["event_ids"])
    if send_to_arize and root_span_id:
        from evals.arize_io import update_evaluations

        result.arize = update_evaluations([{"span_id": root_span_id, "name": EVAL_NAME, "label": label,
                                            "score": score, "explanation": why}])
    if mirror_dir is not None:
        mirror_dir.mkdir(parents=True, exist_ok=True)
        (mirror_dir / f"{conversation_id}.json").write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return result


def sessions_with_label(label: str = "possible_fraud", mirror_dir: Path = MIRROR) -> dict[str, dict[str, Any]]:
    out = {}
    if mirror_dir.exists():
        for p in mirror_dir.glob("*.json"):
            row = json.loads(p.read_text())
            if row.get("label") == label:
                out[row["conversation_id"]] = row
    return out


def main() -> None:
    import argparse

    from core.obs.tracing import flush, init_tracing
    from evals.env import load_env

    ap = argparse.ArgumentParser()
    ap.add_argument("conversation_id", nargs="?", default="conv_seed_1009")
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--root-span-id", default=None)
    args = ap.parse_args()
    load_env()
    init_tracing()
    root_id = args.root_span_id
    if root_id:
        res = evaluate_session(args.conversation_id, seed_events("v_reyes"), use_model=not args.rules, root_span_id=root_id)
    else:
        # Replay: a CHAIN root for the call session, the EVALUATOR span under it, then
        # update_evaluations on the root once it has been exported.
        with span("CHAIN", "call.session", village_id="v_reyes", node_id=args.conversation_id, user_id="m_carmen",
                  input={"conversation_id": args.conversation_id, "replay": True}) as root:
            root.set_attribute("conversation.id", args.conversation_id)
            res = evaluate_session(args.conversation_id, seed_events("v_reyes"), use_model=not args.rules,
                                   root_span_id=None)
            root.set_output({"label": res.label})
            root_id = root.span_id
        flush()
        if root_id:
            from evals.arize_io import update_evaluations

            time.sleep(20)  # let the root span land before attaching the eval
            res.arize = update_evaluations([{"span_id": root_id, "name": EVAL_NAME, "label": res.label,
                                             "score": res.score, "explanation": res.explanation}], timeout=30)
            res.span_id = root_id
            MIRROR.mkdir(parents=True, exist_ok=True)
            (MIRROR / f"{res.conversation_id}.json").write_text(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    flush()
    print(json.dumps(asdict(res), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
