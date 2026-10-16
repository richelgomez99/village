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


def _live_number() -> str | None:
    """Calls go ONLY to the operator's demo number (DEMO_INSTITUTION_NUMBER, E.164); never to a real institution."""
    import os

    return village_reg.e164((os.environ.get("DEMO_INSTITUTION_NUMBER") or "").strip())


def live_mode() -> bool:
    try:
        from core.dialer import mode

        return bool(_live_number()) and mode() == "real"
    except Exception:
        return False


def _live_payload(village_id: str, inst: dict[str, Any], to_number: str) -> dict[str, Any]:
    import os

    questions = inst.get("questions") or ["Do you have power right now?", "Are you open, until when?", "Can you take someone on home oxygen?"]
    lang = str(village_reg.spec(village_id).get("village", {}).get("lang") or "en")
    coord = village_reg.coordinator_id(village_id)
    return {
        "agent_id": os.getenv("ELEVENLABS_AGENT_CALLER_ID", ""),
        "agent_phone_number_id": os.getenv("ELEVENLABS_PHONE_NUMBER_ID", ""),
        "to_number": to_number,
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "purpose": "institution_check",
                "place_name": str(inst.get("name") or inst.get("id")),
                "questions": " ".join(str(q) for q in questions),
                "language": lang,
                "village_id": village_id,
                "institution_id": str(inst["id"]),
                # every variable the frozen Caller prompt references has a value (D31 #5)
                "recipient_name": str(inst.get("name") or inst.get("id")),
                "family_label": village_reg.village_name(village_id),
                "family_word": village_reg.family_word(village_id) or "",
                "care_recipient_rel": "a neighbor",
                "amount_spoken": "",
                "method_spoken": "",
                "coordinator_name": village_reg.first_name(village_id, coord),
                "verification_id": "",
                "member_id": "",
            }
        },
        "telephony_call_config": {"ringing_timeout_secs": 30},
    }


def _result_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map the post-call data_collection_results (or an initiation failure) to {has_power, open_until, takes_oxygen}."""
    if payload.get("type") == "call_initiation_failure" or payload.get("no_answer"):
        return {"no_answer": True}
    results = payload.get("data_collection_results") or {}
    out: dict[str, Any] = {}
    for key in KEYS:
        v = results.get(key)
        if isinstance(v, dict):
            v = v.get("value", v.get("result"))
        out[key] = v if v not in (None, "") else "unknown"
    if all(out[k] == "unknown" for k in KEYS) and not (payload.get("transcript") or payload.get("summary")):
        out["no_answer"] = True
    return out


async def apply_post_call(payload: dict[str, Any]) -> bool:
    """Post-call webhook → institution facts + chat line, when the conversation was one of our institution calls."""
    conv = str(payload.get("conversation_id") or "")
    rec = await db.get_idem(f"instconv:{conv}") if conv else None
    if not rec:
        return False
    village_id, inst_id, run_id = rec["village"], rec["institution"], rec["run_id"]
    inst = next((i for i in institutions(village_id) if i.get("id") == inst_id), None)
    if not inst:
        return False
    key = f"instcall:{village_id}:{inst_id}:{run_id}"
    if await db.get_idem(key):
        return True
    result = _result_from_payload(payload)
    secs = float(payload.get("duration_secs") or payload.get("call_duration_secs") or 0)
    out = await _record(village_id, inst, result, ref=conv, secs=secs, demo=False)
    out["mode"] = "live_no_answer" if result.get("no_answer") else "live"
    await db.put_idem(key, out)
    return True


async def _one(village_id: str, inst: dict[str, Any], run_id: str) -> dict[str, Any]:
    key = f"instcall:{village_id}:{inst['id']}:{run_id}"
    done = await db.get_idem(key)
    if done:
        return {**done, "replayed": True}
    number = _live_number()
    if number and live_mode():
        import os
        import time

        from core.dialer import get_dialer

        t0 = time.monotonic()
        try:
            result = await get_dialer().outbound_call(_live_payload(village_id, inst, number))
            conv = str(result.get("conversation_id") or "")
        except Exception as exc:  # the call could not be placed: say so, never pretend
            result, conv = {"error": type(exc).__name__}, ""
        if conv:
            await db.put_idem(f"instconv:{conv}", {"village": village_id, "institution": inst["id"], "run_id": run_id, "placed_at": time.time()})
            deadline = t0 + float(os.environ.get("INSTITUTION_CALL_WAIT_S", "90"))
            while time.monotonic() < deadline:
                await asyncio.sleep(1.0)
                done = await db.get_idem(key)
                if done:
                    return {**done, "placed_in_s": round(time.monotonic() - t0, 1)}
        out = await _record(village_id, inst, {"no_answer": True}, ref=conv or f"unplaced:{inst['id']}", secs=round(time.monotonic() - t0, 1), demo=False)
        out["mode"] = "live_no_answer" if conv else "live_unplaced"
        await db.put_idem(key, out)
        return out
    demo = inst.get("demo_result") or {}
    wait = min(float(demo.get("duration_s") or 0), MAX_WAIT_S)
    if wait > 0:
        await asyncio.sleep(wait)
    out = await _record(village_id, inst, demo, ref=f"demo:{inst['id']}", secs=wait, demo=True)
    out["mode"] = "fixture"
    await db.put_idem(key, out)
    return out


def places_text(village_id: str) -> str:
    """'Nearest hospitals and routes', from the village data only: names, official pages, a maps link. No times, no capacity."""
    rows = []
    for i in institutions(village_id):
        bits = [str(i.get("name") or i.get("id"))]
        if i.get("address"):
            bits.append(str(i["address"]))
        if i.get("maps_url"):
            bits.append(f"map: {i['maps_url']}")
        elif i.get("url"):
            bits.append(str(i["url"]))
        rows.append(" · ".join(bits))
    if not rows:
        return "I don't have any places on this village's official list yet."
    return "From the block's official list (nothing here is live-verified until a call confirms it): " + " | ".join(rows) + ". Say the word and I'll call them about power and whether they can take someone on oxygen."


async def run_calls(village_id: str, run_id: str | None = None) -> dict[str, Any]:
    """Call every institution in the village data (fixture mode today). Idempotent per run id."""
    insts = institutions(village_id)
    run_id = run_id or uuid.uuid4().hex[:10]
    if not insts:
        return {"village": village_id, "run_id": run_id, "mode": "none", "results": []}
    results = await asyncio.gather(*(_one(village_id, inst, run_id) for inst in insts))
    return {"village": village_id, "run_id": run_id, "mode": "live" if live_mode() else "fixture", "results": list(results)}


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
