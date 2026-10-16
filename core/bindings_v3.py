"""Contract 1.3.4 binds (core-glue 3), resolved generically from the bind strings a view uses:

plan:<id>                               bv_plan        evolve/builder proposal record plan data (empty items if none)
calls:screened                          bv_screened_calls  receptionist screen_caller verifications + cached tool answers
facts:history?subject=<m>&key=<k>       bv_fact_history    core.memory history (async, cached) else the ledger
Village-agnostic: nothing here names a village or a member."""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import parse_qs

from core import village as villages
from core.db import db

# ---- plan:<id> ------------------------------------------------------------------------------------

PLANS: dict[tuple[str, str], dict[str, Any]] = {}  # (village, plan_id) -> bv_plan held by core (claims update it)


def _text(value: Any) -> Any:
    return value if isinstance(value, (str, dict)) else str(value or "")


def _items_from(plan: Any) -> list[dict[str, Any]]:
    items = plan.get("items") if isinstance(plan, dict) else plan
    out = []
    for it in items or []:
        if isinstance(it, dict) and it.get("text"):
            row = {k: v for k, v in it.items() if v is not None}
            row.setdefault("status", "open")
            out.append(row)
        elif isinstance(it, (str, dict)) and it:
            out.append({"text": _text(it), "status": "open"})
    return out


def _proposal_plan(village_id: str, plan_id: str) -> dict[str, Any] | None:
    try:
        from core.evolve.proposals import STORE
    except Exception:
        return None
    for pid, rec in (STORE.get(village_id) or {}).items():
        proposal = rec.get("proposal") or {}
        ids = {pid, proposal.get("plan_id"), rec.get("plan_id"), str(rec.get("key", "")).split(":", 1)[-1]}
        if plan_id not in ids and not pid.endswith(f"_{plan_id}") and f"_{plan_id}_" not in pid:
            continue
        plan = rec.get("plan") or proposal.get("plan")
        if plan is None:
            return {"title": proposal.get("title"), "items": []}
        out = {"items": _items_from(plan)}
        for key in ("title", "date"):
            if isinstance(plan, dict) and plan.get(key):
                out[key] = plan[key]
        out.setdefault("title", proposal.get("title"))
        return out
    return None


def plan(village_id: str, plan_id: str) -> dict[str, Any]:
    held = PLANS.get((village_id, plan_id))
    if held is not None:
        return held
    found = None
    try:  # the builder keeps chat-request plans (who brings what, pickups) next to the proposal record
        from core.builder.chat_intent import plan_data

        got = plan_data(village_id, plan_id)
        if got:
            found = {"items": _items_from(got), **{k: got[k] for k in ("title", "date") if isinstance(got, dict) and got.get(k)}}
    except Exception:
        found = None
    if found is None:
        found = _proposal_plan(village_id, plan_id)
    if found is None:
        return {"items": []}
    return {k: v for k, v in found.items() if v is not None}


async def set_plan_item(village_id: str, plan_id: str, index: int, *, status: str | None = None, owner: str | None = None) -> dict[str, Any]:
    """Change one plan item (claim / done) and push fresh data to every socket that binds plan:<id>."""
    current = plan(village_id, plan_id)
    items = [dict(i) for i in current.get("items", [])]
    if not 0 <= index < len(items):
        raise IndexError("no such plan item")
    if status:
        items[index]["status"] = status
    if owner:
        items[index]["owner"] = owner
    PLANS[(village_id, plan_id)] = {**current, "items": items}
    from core.ws_hub import hub

    await hub.push_binds(village_id, {f"plan:{plan_id}"})
    return PLANS[(village_id, plan_id)]


# ---- calls:screened -------------------------------------------------------------------------------

_OUTCOME = {"pending": "held", "default_spoken": "held", "confirmed": "passed_through", "late_confirmed": "passed_through",
            "denied": "refused", "late_denied": "refused", "timed_out": "refused", "unreachable": "refused", "unsure": "held"}


def screened_calls(village_id: str, limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    says: dict[str, Any] = {}
    seen_convs: set[str] = set()
    for key, cached in db.idem.items():
        resp = (cached or {}).get("response") or {}
        if not str(key).endswith((":screen", ":screen:await")) or not isinstance(resp, dict):
            continue
        data = resp.get("data") or {}
        if data.get("verification_id"):
            says[data["verification_id"]] = resp.get("say")
            continue
        status = (data.get("status") or "").replace("pass_through", "passed_through")
        if status in {"passed_through", "refused"} and (resp.get("village_id", village_id) == village_id):
            conv = str(key).split(":", 1)[0]
            seen_convs.add(conv)
            row = {"at": cached.get("at"), "outcome": status, "say": resp.get("say")}
            if data.get("member_id"):
                row["claimed"] = villages.first_name(village_id, data["member_id"])
                row["verified_by"] = "caller id + family word"
            rows.append(row)
    for v in db.verifications.values():
        if v.get("village", village_id) != village_id or v.get("origin") != "screen_caller":
            continue
        claimed_id = v.get("claimed_member_id")
        row = {"at": v.get("resolved_at") or v.get("created_at"), "outcome": _OUTCOME.get(v.get("state"), "unknown"),
               "claimed": v.get("claimed_identity") or villages.first_name(village_id, claimed_id), "verification_id": v["id"]}
        if claimed_id and v.get("state") not in {"pending", "default_spoken"}:
            row["verified_by"] = villages.first_name(village_id, claimed_id)
        if says.get(v["id"]):
            row["say"] = says[v["id"]]
        rows.append(row)
    try:  # voice: every receptionist call (message_taken | passed_through | held | refused | hung_up), no money claim needed
        from core.voice import screened

        rows.extend(screened.rows(village_id))
    except ImportError:
        pass
    rows = [{k: val for k, val in r.items() if val is not None} for r in rows if r.get("at")]
    rows.sort(key=lambda r: str(r["at"]), reverse=True)
    return rows[:limit]


# ---- facts:history?subject=&key= ------------------------------------------------------------------

HISTORY_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}


def parse_history_bind(bind: str) -> tuple[str, str] | None:
    if not bind.startswith("facts:history?"):
        return None
    q = parse_qs(bind.split("?", 1)[1])
    subject, key = (q.get("subject") or [""])[0], (q.get("key") or [""])[0]
    return (subject, key) if subject and key else None


def _ledger_history(village_id: str, subject: str, key: str) -> list[dict[str, Any]]:
    k = key.lower()
    out = []
    for ev in db.events:
        if ev.get("village", village_id) != village_id:
            continue
        p = ev.get("payload") or {}
        about = p.get("subject") or p.get("member_id") or ev.get("actor")
        if about != subject:
            continue
        text = " ".join(str(v) for v in p.values() if isinstance(v, (str, int, float))).lower()
        if ev["kind"] != k and p.get("key") != k and k not in text:
            continue
        value = p.get("value") or p.get("to") or p.get("dose") or p.get("slot") or ev["kind"]
        out.append({"value": value, "observed_at": ev.get("at"), "recorded_at": ev.get("at"), "source": ev.get("source"), "event_id": ev.get("id")})
    for rx in db.prescriptions.get(village_id, []):
        name = str(rx.get("name", "")).lower()
        if name and (k in name or name in k or k in str(rx.get("med_id", "")).lower()):  # "lisinopril_dose" ~ lisinopril
            out.append({"value": f"{rx.get('name')} {rx.get('dose')}", "observed_at": rx.get("valid_from"), "valid_until": rx.get("valid_until"),
                        "source": rx.get("source"), "superseded": rx.get("valid_until") is not None})
    out.sort(key=lambda r: str(r.get("observed_at") or ""), reverse=True)
    return out[:50]


def fact_history(village_id: str, subject: str, key: str) -> dict[str, Any]:
    cached = HISTORY_CACHE.get((village_id, subject, key))
    if cached is not None:
        return cached
    return {"entity": subject, "key": key, "versions": _ledger_history(village_id, subject, key), "degraded": True}


async def refresh_history(village_id: str, subject: str, key: str, timeout_s: float = 4.0) -> bool:
    """Fetch core.memory's history; cache it when it has versions. True when the cached value changed."""
    try:
        from core.memory.routes import get_memory_deps
        from core.memory.views import history_view

        got = await asyncio.wait_for(history_view(get_memory_deps(), village_id, subject, key), timeout_s)
    except Exception:
        return False
    if not got.get("versions"):
        return False
    value = {"entity": subject, "key": got.get("key", key), "versions": got["versions"], "degraded": bool(got.get("degraded"))}
    if HISTORY_CACHE.get((village_id, subject, key)) == value:
        return False
    HISTORY_CACHE[(village_id, subject, key)] = value
    return True


# ---- resolver used by snapshot_data / changed ---------------------------------------------------

def resolve(bind: str, village_id: str) -> tuple[bool, Any]:
    if bind.startswith("plan:"):
        return True, plan(village_id, bind[5:])
    if bind == "calls:screened":
        return True, screened_calls(village_id)
    hist = parse_history_bind(bind)
    if hist:
        return True, fact_history(village_id, *hist)
    from core.block_data import resolve as group_resolve

    return group_resolve(bind, village_id)


def resolve_all(binds: set[str], village_id: str) -> dict[str, Any]:
    out = {}
    for bind in binds:
        ok, value = resolve(bind, village_id)
        if ok:
            out[bind] = value
    return out
