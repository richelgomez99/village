"""Institution check calls (BLOCK-VOICE): Village calls the places on a village's official list
(`institutions` in the village data) to ask whether they have power, are open, and can take someone.

Village-agnostic (D30): every name/url comes from village data. Live calls need an institution
script on the Caller agent (agents are frozen), so today every run uses each place's scripted
`demo_result` and is labeled demo. Each answer becomes Agent Memory facts (entity = institution id,
keys has_power/open_until/takes_oxygen, source kind=call) plus one Village chat row per place.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from core import village as village_reg
from core.db import db
from core.memory import conventions as cv

router = APIRouter(tags=["voice"])

KEYS = ("has_power", "open_until", "takes_oxygen")
MAX_WAIT_S = 4.0
DRAFT_PREFIX = "instfact:"


def institutions(village_id: str) -> list[dict[str, Any]]:
    try:
        return list(village_reg.village_data(village_id).get("institutions") or [])
    except Exception:
        return []


def fact_drafts(village_id: str) -> list[dict[str, Any]]:
    """Ledger-mirror drafts for institution facts (read by core.memory.views.mirror)."""
    return [row["draft"] for key, row in list(db.idem.items())
            if key.startswith(DRAFT_PREFIX) and row.get("draft", {}).get("village") == village_id]


def _clock_label(at: Any) -> str:
    dt = cv.to_dt(at)
    try:
        dt = dt.astimezone(cv.ET)
    except Exception:
        pass
    return dt.strftime("%-I:%M %p")


def _yn(v: Any) -> str:
    return str(v if v not in (None, "") else "unknown")


def chat_text(inst: dict[str, Any], result: dict[str, Any], at_label: str, *, demo: bool) -> str:
    name = inst.get("name") or inst.get("id")
    if result.get("no_answer"):
        line = f"No answer at {name} ({at_label}). I'll try again in 20 minutes."
    else:
        open_until = _yn(result.get("open_until"))
        open_part = "closed" if open_until.lower() == "closed" else ("open until unknown" if open_until == "unknown" else f"open until {open_until}")
        line = f"{name}: power {_yn(result.get('has_power'))} · {open_part} · takes oxygen: {_yn(result.get('takes_oxygen'))} (called {at_label})"
    return f"[demo] {line} · demo" if demo else line


async def _remember(village_id: str, draft: dict[str, Any]) -> None:
    """Best-effort write-through to Agent Memory; the ledger mirror serves the fact either way."""
    try:
        from core.memory.client import get_client

        await asyncio.wait_for(get_client().remember_fact(
            draft["entity"], draft["key"], draft["value"], source=draft["source"], village=village_id,
            observed_at=draft["observed_at"], extra_labels={"src": "call", "purpose": "institution_check"}), timeout=3)
    except Exception:
        pass


async def _record(village_id: str, inst: dict[str, Any], result: dict[str, Any], *, ref: str, secs: float, demo: bool) -> dict[str, Any]:
    from core.clock import clock
    from core.services import post_message

    at = cv.iso(clock.now())
    label_at = _clock_label(at)
    source = {"kind": "call", "ref": ref, "secs": round(secs, 1)}
    facts = []
    for key in KEYS:
        value = f"no answer at {label_at}" if result.get("no_answer") else _yn(result.get(key))
        draft = {"village": village_id, "entity": inst["id"], "key": cv.norm_key(key), "value": value[:400],
                 "text": f"{inst.get('name')}: {key.replace('_', ' ')} = {value}"[:300],
                 "observed_at": at, "recorded_at": at, "source": source, "event_id": None,
                 "agent": "village", "rule_id": None, "extra_labels": {"src": "call", "demo": "true" if demo else "false"}}
        await db.put_idem(f"{DRAFT_PREFIX}{village_id}:{inst['id']}:{key}:{ref}", {"draft": draft})
        facts.append(draft)
        asyncio.ensure_future(_remember(village_id, draft))
    text = chat_text(inst, result, label_at, demo=demo)
    refs = [{"kind": "fact", "id": f"{inst['id']}:has_power", "label": f"call to {inst.get('name')}, {label_at}"[:80]}]
    if demo:
        refs.append({"kind": "fact", "id": "demo", "label": "demo"})
    msg = await post_message(village_id, author="village", kind="nudge", text=text, refs=refs,
                             source={"kind": "call", "ref": ref, "secs": round(secs, 1)})
    return {"institution": inst["id"], "facts": len(facts), "message_id": msg["id"], "text": text}


async def _one(village_id: str, inst: dict[str, Any], run_id: str) -> dict[str, Any]:
    key = f"instcall:{village_id}:{inst['id']}:{run_id}"
    done = await db.get_idem(key)
    if done:
        return {**done, "replayed": True}
    demo = inst.get("demo_result") or {}
    wait = min(float(demo.get("duration_s") or 0), MAX_WAIT_S)
    if wait > 0:
        await asyncio.sleep(wait)
    out = await _record(village_id, inst, demo, ref=f"demo:{inst['id']}", secs=wait, demo=True)
    out["mode"] = "fixture"
    await db.put_idem(key, out)
    return out


async def run_calls(village_id: str, run_id: str | None = None) -> dict[str, Any]:
    """Call every institution in the village data (fixture mode today). Idempotent per run id."""
    insts = institutions(village_id)
    run_id = run_id or uuid.uuid4().hex[:10]
    if not insts:
        return {"village": village_id, "run_id": run_id, "mode": "none", "results": []}
    results = await asyncio.gather(*(_one(village_id, inst, run_id) for inst in insts))
    return {"village": village_id, "run_id": run_id, "mode": "fixture", "results": list(results)}


def intro_text(village_id: str) -> str:
    names = ", ".join(str(i.get("name")) for i in institutions(village_id))
    return f"I'll call the places on the block's official list now: {names}. One line per place as they answer."


@router.post("/villages/{village_id}/calls/institutions")
async def post_institution_calls(village_id: str, body: dict[str, Any] = Body(default={}),
                                 authorization: str | None = Header(default=None)) -> dict[str, Any]:
    from core.auth import resolve_token

    who = resolve_token(authorization)
    if who != "control" and who != village_reg.coordinator_id(village_id):
        raise HTTPException(status_code=401, detail="coordinator or control token required")
    if village_id not in village_reg.village_ids():
        raise HTTPException(status_code=404, detail="unknown village")
    return await run_calls(village_id, (body or {}).get("run_id"))
