"""Send one real trace to Arize project `village`: CHAIN > AGENT(extract) > GUARDRAIL(gate).

    VILLAGE_LLM=on uv run --with boto3 python -m evals.trace_smoke
"""

from __future__ import annotations

import json

from core.gate import decide
from core.obs.tracing import flush, init_tracing, span
from evals.env import load_env
from evals.extract import extract, to_tool_request
from evals.reyes import DATASETS
from evals.scam_experiment import gate_input


def main(case_id: str = "se_s02") -> dict:
    load_env()
    mode = init_tracing()
    case = next(json.loads(l) for l in (DATASETS / "scam_eval_set.jsonl").read_text().splitlines() if case_id in l)
    with span("CHAIN", "scam_eval.case", village_id="v_reyes", node_id="scam_eval", user_id="m_carmen",
              input=case["utterance"]) as root:
        with span("AGENT", "mom_line.extract", village_id="v_reyes", node_id="extract", parent_id="scam_eval",
                  user_id="m_carmen", input=case["utterance"]) as a:
            ex = extract(case["utterance"])
            a.set_attribute("extractor", ex.extractor)
            a.set_output(ex.request)
        req = to_tool_request(ex, case["utterance"], case["id"])
        with span("GUARDRAIL", "gate.decide", village_id="v_reyes", node_id="gate", parent_id="extract",
                  user_id="m_carmen", input=req) as g:
            d = decide(gate_input(case, req)) if req else None
            g.set_attribute("gate.rule_id", (d or {}).get("rule_id", "no_tool_call"))
            g.set_attribute("gate.decision", (d or {}).get("decision", "record"))
            g.set_output(d)
        root.set_output({"decision": (d or {}).get("decision"), "expected": case["expected_decision"]})
        trace_id = root.trace_id
    ok = flush()
    out = {"mode": mode, "trace_id": trace_id, "flushed": ok, "decision": (d or {}).get("decision"), "extractor": ex.extractor}
    print(json.dumps(out))
    return out


if __name__ == "__main__":
    main()
