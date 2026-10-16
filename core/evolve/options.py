"""consider_options (D20, AGENT.md §4 "Options before proposals").

The Watcher weighs 2-3 candidate fixes for a detected pattern before it proposes anything. One is chosen
with reasons; the losers keep a one-line reason each (the Options card shows them). Model path:
`llm("watcher")` with a forced `consider_options` tool call; model off / error / slow -> canned options
(same shape, names from the village spec, never hardcoded: D30).

Emits `control{kind: reasoning}` + one `control{kind: ledger}` row per candidate (losers `refused` with
their reason, the winner `running` / "testing") and writes one decision row (mode asked_human).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db

log = logging.getLogger("village.evolve")

KEYS = ("check_button", "daily_checkin", "receptionist")
CHOSEN = "receptionist"
MODEL_TIMEOUT_S = 12.0

TOOL = {
    "name": "consider_options",
    "description": "Weigh 2-3 candidate software changes for the detected pattern before proposing one. "
                   "Each candidate gets tradeoffs; choose exactly one and say why in plain words.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates", "chosen", "reasons"],
        "properties": {
            "candidates": {
                "type": "array", "minItems": 2, "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "name", "what_changes", "addresses_pattern", "cost_to_person", "risk", "reason"],
                    "properties": {
                        "key": {"enum": list(KEYS)},
                        "name": {"type": "string", "maxLength": 80},
                        "what_changes": {"type": "string", "maxLength": 200},
                        "addresses_pattern": {"type": "string", "maxLength": 200},
                        "cost_to_person": {"type": "string", "maxLength": 160},
                        "risk": {"type": "string", "maxLength": 160},
                        "reason": {"type": "string", "maxLength": 160, "description": "One line: why chosen or why not."},
                    },
                },
            },
            "chosen": {"enum": list(KEYS)},
            "reasons": {"type": "string", "maxLength": 300},
        },
    },
}


def _names(village_id: str, evidence: dict[str, Any]) -> dict[str, str]:
    claimed = evidence.get("claimed_member_id") or villages.default_verifier(village_id)
    recipient = evidence.get("subject") or villages.care_recipient_id(village_id)
    return {
        "claimed": villages.first_name(village_id, claimed, "the family member"),
        "recipient": villages.first_name(village_id, recipient, "them"),
        "rel_en": villages.relationship_word(village_id, recipient, "en") or "them",
        "rel_es": villages.relationship_word(village_id, recipient, "es") or "ella",
        "count": str(evidence.get("count", 2)),
    }


def canned(village_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    n = _names(village_id, evidence)
    cands = [
        {"key": "check_button", "name": "“¿Es de verdad?” button",
         "what_changes": f"A big check button on {n['rel_en']}'s app that starts a verification with {n['claimed']}.",
         "addresses_pattern": "Only if she remembers to press it mid-call.",
         "cost_to_person": "She has to remember it under pressure.", "risk": "Scammers keep her on the line; the button never gets pressed.",
         "reason": "Rejected: relies on her remembering under pressure.", "chosen": False},
        {"key": "daily_checkin", "name": "Daily check-in call",
         "what_changes": f"Village calls {n['rel_en']} every evening and asks about the day, including any money asks.",
         "addresses_pattern": "Catches attempts afterwards and keeps the family informed.",
         "cost_to_person": "One short call a day; she can decline.", "risk": "The scam call still reaches her first.",
         "reason": "Helps, but doesn't stop the call.", "chosen": False},
        {"key": "receptionist", "name": f"Receptionist on {n['rel_en']}'s line",
         "what_changes": f"Village answers unknown callers first; known family (caller id + family word) rings through; "
                         f"anyone claiming to be family is checked with the real person on their own phone.",
         "addresses_pattern": f"Both calls claimed to be {n['claimed']}; the check happens before the call reaches her.",
         "cost_to_person": "Nothing to remember; her number and her family's calls are unchanged.",
         "risk": "A real unknown caller waits a few seconds; she can turn it off.",
         "reason": "Chosen: stops the call before it reaches her.", "chosen": True},
    ]
    return {"candidates": cands, "chosen": CHOSEN, "mode": "canned",
            "reasons": f"{n['count']} money requests in {n['claimed']}'s name. A button relies on her memory and a check-in "
                       f"comes after the call; only the receptionist checks with the real {n['claimed']} before she hears the caller."}


def _model_options(village_id: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
    from core.llm import LLMOff, llm

    client = llm("watcher")
    if getattr(client, "provider", None) == "off":
        return None
    n = _names(village_id, evidence)
    user = json.dumps({
        "pattern": evidence.get("pattern", "repeat_money_request"),
        "text": evidence.get("text"),
        "count": evidence.get("count"), "window_days": evidence.get("window_days"),
        "evidence": [e.get("label") for e in (evidence.get("evidence") or [])][:6],
        "care_recipient": n["recipient"], "claimed_member": n["claimed"],
        "candidates_to_weigh": {
            "check_button": "a big '¿Es de verdad?' check button on her app",
            "daily_checkin": "a daily evening check-in call from Village",
            "receptionist": "Village answers unknown callers on her line first and verifies family claims with the real member before putting the call through",
        },
    }, ensure_ascii=False)
    try:
        msg = client.messages.create(
            model=client.village_model, max_tokens=900,
            system="You are Village's Watcher. A scam pattern was detected against an older person. Weigh the three "
                   "candidate fixes with honest tradeoffs (what it changes, whether it addresses the pattern, cost to her, risk), "
                   "choose one, and give one plain line per candidate. Money never moves; Village never dials money actions.",
            messages=[{"role": "user", "content": user}],
            tools=[TOOL], tool_choice={"type": "tool", "name": "consider_options"},
        )
    except LLMOff:
        return None
    block = next((b for b in getattr(msg, "content", []) if getattr(b, "type", "") == "tool_use"), None)
    if block is None:
        return None
    out = dict(block.input)
    cands = [c for c in out.get("candidates", []) if c.get("key") in KEYS]
    if len(cands) < 2 or out.get("chosen") != CHOSEN or not any(c["key"] == CHOSEN for c in cands):
        log.info("consider_options: model chose %s; keeping the canned weighing", out.get("chosen"))
        return None
    for c in cands:
        c["chosen"] = c["key"] == CHOSEN
    return {"candidates": cands, "chosen": CHOSEN, "reasons": str(out.get("reasons", ""))[:300], "mode": "model",
            "model": getattr(client, "village_model", "")}


async def weigh(village_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """The weighing itself (no side effects)."""
    t0 = time.perf_counter()
    try:
        out = await asyncio.wait_for(asyncio.to_thread(_model_options, village_id, evidence), MODEL_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 - model trouble never blocks a proposal
        log.warning("consider_options model failed: %s", exc)
        out = None
    out = out or canned(village_id, evidence)
    out["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return out


def _decision_id() -> str:
    return f"dc_evolve_{clock.now():%H%M%S}_{len(db.decisions) + 1:03d}"


async def consider_options(village_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Weigh, record (decision row, mode asked_human) and show (reasoning + ledger frames). Returns Options."""
    from core import services

    opts = await weigh(village_id, evidence)
    chosen = next(c for c in opts["candidates"] if c["chosen"])
    losers = [c for c in opts["candidates"] if not c["chosen"]]
    did = _decision_id()
    opts["decision_id"] = did
    text = (f"Weighed {len(opts['candidates'])} fixes: " + "; ".join(f"{c['name']}: {c['reason']}" for c in losers)
            + f"; chose {chosen['name']}.")[:400]
    refs = [{"kind": "event", "id": e} for e in (evidence.get("event_ids") or [])[:4]]
    coord = villages.coordinator_id(village_id)
    if coord:
        refs.append({"kind": "member", "id": coord})
    refs.append({"kind": "policy", "id": "R-SPEC"})
    await db.create_decision({
        "id": did, "village_id": village_id, "at": clock.now().isoformat(), "actor": "evolve", "kind": "decision",
        "text": text, "rule_id": "R-SPEC", "mode": "asked_human", "refs": refs,
        "source": {"kind": "system", "ref": "evolve"}, "options": opts,
    })
    await services.reasoning(village_id, f"Pattern: {evidence.get('text') or 'repeat money requests'}", source="watcher", kind="note")
    for c in losers:
        await services.ledger(village_id, f"opt:{did}:{c['key']}", "refused", f"Option · {c['name']}", result=c["reason"],
                              decision_id=did, role="Watcher")
    await services.ledger(village_id, f"opt:{did}:{chosen['key']}", "running", f"Option · {chosen['name']}", result="testing",
                          decision_id=did, role="Watcher")
    await services.reasoning(village_id, text, source="evolve", kind="decision", mode="asked_human")
    return opts
