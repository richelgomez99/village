"""Evolve detector: repeat money requests in one member's name -> Proposal evidence.

detect_patterns(village_id, events) finds >= 2 money_request rows claiming the same
member within 14 days and returns one pattern per (subject, claimed member) with
`evidence` rows shaped per contracts/schemas/proposal.schema.json#/$defs/evidence:
call_moment ('<conversation_id>@<secs>'), trace (32-hex Arize trace id, with the
session eval label when known) and fact ('fact:money_request:<subject>:<date>').
Pure: no network; session labels come from the caller (or the local mirror).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

WINDOW_DAYS = 14
TRACE_RE = re.compile(r"^[0-9a-f]{32}$")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _member_name(claimed: str | None) -> str:
    return (claimed or "unknown").removeprefix("m_").capitalize()


def _label(ev: dict[str, Any], today: str | None) -> str:
    p, src, at = ev["payload"], ev.get("source") or {}, _dt(ev["at"])
    day = "Today" if today and ev["at"][:10] == today else f"{MONTHS[at.month - 1]} {at.day}"
    secs = int(src.get("secs") or 0)
    amount = f"${p['amount']:,.0f}" if isinstance(p.get("amount"), (int, float)) else "money"
    method = {"gift_card": " in gift cards", "crypto": " in crypto", "wire_to_stranger": " by wire",
              "cash_courier": " by courier"}.get(p.get("method") or "", "")
    return f"{day} · call at {secs // 60}:{secs % 60:02d} · “{_member_name(p.get('claimed_member_id'))}” asked for {amount}{method}"[:160]


def evidence_for(ev: dict[str, Any], *, today: str | None = None,
                 session_labels: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    p, src = ev["payload"], ev.get("source") or {}
    rows: list[dict[str, Any]] = []
    if src.get("kind") == "call" and src.get("ref"):
        secs = src.get("secs") or 0
        secs_s = str(int(secs)) if float(secs).is_integer() else str(secs)
        row = {"kind": "call_moment", "ref": f"{src['ref']}@{secs_s}", "label": _label(ev, today), "at": ev["at"]}
        quote = src.get("quote") or p.get("utterance")
        if quote:
            row["quote"] = quote[:300]
        rows.append(row)
    trace_id = (ev.get("am") or {}).get("trace_id")
    if trace_id and TRACE_RE.match(trace_id):
        row = {"kind": "trace", "ref": trace_id, "label": f"Arize trace of the {ev['at'][:10]} call", "at": ev["at"]}
        lab = (session_labels or {}).get(src.get("ref", ""))
        if lab:
            row["eval"] = {"name": "session_possible_fraud", "label": lab["label"], "score": float(lab.get("score", 0))}
            row["label"] = f"Arize session eval {lab['label']} on the {ev['at'][:10]} call"
        rows.append(row)
    rows.append({
        "kind": "fact",
        "ref": f"fact:money_request:{p.get('subject', 'unknown')}:{ev['at'][:10]}",
        "label": (f"Fact: money_request claimed_member={p.get('claimed_member_id')} "
                  f"(src=call:{src.get('ref')}, secs={src.get('secs')})")[:160],
        "at": ev["at"],
    })
    return rows


def detect_patterns(village_id: str, events: list[dict[str, Any]], *, now: str | None = None,
                    window_days: int = WINDOW_DAYS,
                    session_labels: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    money = sorted((e for e in events if e.get("kind") == "money_request"
                    and e.get("village", village_id) == village_id
                    and (e.get("payload") or {}).get("claimed_member_id")
                    and not str((e.get("source") or {}).get("ref", "")).endswith("_qa")),
                   key=lambda e: e["at"])
    if not money:
        return []
    ref_now = _dt(now) if now else _dt(money[-1]["at"])
    today = (now or money[-1]["at"])[:10]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in money:
        if ref_now - _dt(e["at"]) <= timedelta(days=window_days) and _dt(e["at"]) <= ref_now + timedelta(minutes=5):
            p = e["payload"]
            groups.setdefault((p.get("subject", "unknown"), p["claimed_member_id"]), []).append(e)
    out = []
    for (subject, claimed), evs in groups.items():
        if len(evs) < 2:
            continue
        evidence: list[dict[str, Any]] = []
        for e in evs:
            evidence.extend(evidence_for(e, today=today, session_labels=session_labels))
        evidence = evidence[:12]  # proposal.schema.json maxItems
        name = _member_name(claimed)
        out.append({
            "pattern": "repeat_money_request",
            "village": village_id,
            "subject": subject,
            "claimed_member_id": claimed,
            "count": len(evs),
            "window_days": window_days,
            "event_ids": [e["id"] for e in evs],
            "trace_ids": [r["ref"] for r in evidence if r["kind"] == "trace"],
            "fact_ids": [r["ref"] for r in evidence if r["kind"] == "fact"],
            "call_moments": [r["ref"] for r in evidence if r["kind"] == "call_moment"],
            "detected_by": "arize_eval" if any("eval" in r for r in evidence) else "memory_pattern",
            "text": f"{len(evs)} money requests in {name}'s name in {window_days} days. Proposed a scam check; waiting for approval.",
            "evidence": evidence,
        })
    return out


def main() -> None:
    import json

    from evals.reyes import seed_events
    from evals.session_eval import sessions_with_label

    events = seed_events("v_reyes") + [_today_event()]
    print(json.dumps(detect_patterns("v_reyes", events, session_labels=sessions_with_label()), indent=2, ensure_ascii=False))


def _today_event() -> dict[str, Any]:
    import json

    from evals.reyes import ROOT

    ex = json.loads((ROOT / "contracts" / "schemas" / "event.schema.json").read_text())["examples"]
    return next(e for e in ex if e["id"] == "ev_1016_1402_money")


if __name__ == "__main__":
    main()
