"""Fact views (contracts/schemas/facts.schema.json): Agent Memory first, ledger mirror on failure.

Every response carries `degraded`; on any memory failure the same shape is served from
the ledger mirror (facts_from_event over the ledger) in well under 2 s.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

from core import village as village_reg
from core.memory import conventions as cv
from core.memory.client import MemoryClient
from core.memory.ledger_subscriber import facts_from_event

# default-village coordinator (header default in memory/routes.py); resolve_view derives it per village
COORDINATOR = village_reg.coordinator_id(village_reg.default_village_id()) or ""


@dataclass
class MemoryDeps:
    client: MemoryClient
    events: Callable[[str], list[dict[str, Any]]]
    prescriptions: Callable[[str], list[dict[str, Any]]] = lambda v: []
    now: Callable[[], datetime] = lambda: datetime.now(cv.ET)
    write_decision: Callable[[dict[str, Any]], Awaitable[Any]] | None = None
    timeout_s: float = 6.0
    extra: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ mirror
def mirror(deps: MemoryDeps, village: str) -> list[dict[str, Any]]:
    """All fact drafts from the ledger, chain-annotated (superseded / valid_to / superseded_by)."""
    rx = deps.prescriptions(village)
    drafts = [d for e in deps.events(village) if (e.get("village") or e.get("village_id")) in (None, village)
              for d in facts_from_event(e, rx)]
    extra = deps.extra.get("drafts")
    if extra is not None:  # facts written outside the ledger (e.g. institution calls)
        drafts += [dict(d) for d in extra(village)]
    from core.memory.founding import founding_drafts

    drafts += founding_drafts(village)
    chains: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for d in drafts:
        chains.setdefault((d["entity"], d["key"]), []).append(d)
    out = []
    for chain in chains.values():
        chain.sort(key=lambda d: cv.to_dt(d["observed_at"]))
        dedup: list[dict[str, Any]] = []
        for d in chain:
            if dedup and dedup[-1]["value"] == d["value"]:
                continue
            dedup.append(dict(d))
        for i, d in enumerate(dedup):
            nxt = dedup[i + 1] if i + 1 < len(dedup) else None
            d["id"] = cv.fact_id(d["key"], d["entity"], d["observed_at"])
            d["superseded"] = nxt is not None
            d["valid_to"] = nxt["observed_at"] if nxt else None
            if nxt:
                d["superseded_by"] = cv.fact_id(nxt["key"], nxt["entity"], nxt["observed_at"])
        out += dedup
    return out


def _labels_out(lab: dict[str, str], village: str, agent: str) -> dict[str, str]:
    out = {"src": lab.get("src", "system:memory"), "village": lab.get("village", village), "agent": lab.get("agent", agent)}
    if lab.get("secs") and re.match(r"^[0-9]+(\.[0-9]+)?$", lab["secs"]):
        out["secs"] = lab["secs"]
    if lab.get("event"):
        out["event"] = lab["event"]
    return out


def _labels_from_draft(d: dict[str, Any]) -> dict[str, str]:
    s = d["source"]
    lab = {"src": f"{s.get('kind', 'system')}:{s.get('ref', 'ledger')}", "village": d["village"], "agent": d.get("agent", "memory")}
    if s.get("secs") is not None:
        lab["secs"] = cv._num(s["secs"])
    if d.get("event_id"):
        lab["event"] = d["event_id"]
    for k, v in (d.get("extra_labels") or {}).items():
        lab.setdefault(k, str(v))
    return lab


def _source_ok(s: dict[str, Any]) -> dict[str, Any]:
    src = {k: s[k] for k in ("kind", "ref", "secs", "url", "quote") if k in s and s[k] is not None}
    if src.get("kind") not in {"call", "app", "scan", "url", "system"}:
        src = {"kind": "system", "ref": str(s.get("ref", "memory"))}
    if src["kind"] == "call" and "secs" not in src:
        src["secs"] = 0
    return src


def card_from_draft(d: dict[str, Any]) -> dict[str, Any]:
    c = {"id": d["id"], "village": d["village"], "entity": d["entity"], "key": d["key"], "value": d["value"],
         "text": d["text"], "labels": _labels_from_draft(d), "observed_at": d["observed_at"],
         "recorded_at": d.get("recorded_at") or d["observed_at"], "valid_to": d.get("valid_to"),
         "superseded": bool(d.get("superseded")), "source": _source_ok(d["source"])}
    if d.get("superseded_by"):
        c["superseded_by"] = d["superseded_by"]
    if d.get("event_id"):
        c["event_id"] = d["event_id"]
    return c


def version_from_draft(d: dict[str, Any]) -> dict[str, Any]:
    c = card_from_draft(d)
    v = {k: c[k] for k in ("id", "value", "text", "observed_at", "recorded_at", "superseded", "source", "labels")}
    if c.get("event_id"):
        v["event_id"] = c["event_id"]
    return v


def _match(mir: list[dict[str, Any]], entity: str, key: str, value: str) -> dict[str, Any] | None:
    for d in mir:
        if d["entity"] == entity and d["key"] == key and d["value"] == value:
            return d
    return None


def card_from_am(row: dict[str, Any], village: str, entity: str, mir: list[dict[str, Any]],
                 id_map: dict[str, str] | None = None) -> dict[str, Any]:
    lab = cv.parse_labels(row.get("labels"))
    key = cv.norm_key(row.get("key", "fact_key"))
    value = str(row.get("value", ""))[:400]
    observed = cv.iso(row.get("createdAt") or row.get("validFrom"))
    m = _match(mir, entity, key, value)
    src = cv.source_from_labels(lab)
    if m and m["source"].get("quote") and "quote" not in src:
        src["quote"] = m["source"]["quote"][:600]
    card = {"id": cv.fact_id(key, entity, observed), "village": village, "entity": entity, "key": key, "value": value,
            "text": (m["text"] if m else (row.get("summary") or f"{key}: {value}"))[:300],
            "labels": _labels_out(lab, village, "memory"), "observed_at": observed,
            "recorded_at": (m or {}).get("recorded_at") or observed,
            "valid_to": cv.iso(row["validUntil"]) if row.get("validUntil") else None,
            "superseded": bool(row.get("validUntil") or row.get("supersededBy")), "source": _source_ok(src)}
    if row.get("supersededBy") and id_map and row["supersededBy"] in id_map:
        card["superseded_by"] = id_map[row["supersededBy"]]
    ev = lab.get("event") or (m or {}).get("event_id")
    if ev and re.match(r"^ev_[A-Za-z0-9_]{3,64}$", ev):
        card["event_id"] = ev
    if isinstance(row.get("confidence"), (int, float)):
        card["confidence"] = max(0.0, min(1.0, float(row["confidence"])))
    return card


def version_from_card(c: dict[str, Any]) -> dict[str, Any]:
    v = {k: c[k] for k in ("id", "value", "text", "observed_at", "recorded_at", "superseded", "source", "labels")}
    if c.get("event_id"):
        v["event_id"] = c["event_id"]
    return v


def _valid_at(c: dict[str, Any], at: datetime) -> bool:
    obs = cv.to_dt(c["observed_at"])
    to = cv.to_dt(c.get("valid_to"))
    return obs <= at and (to is None or to > at)


async def _guard(coro, deps: MemoryDeps, empty: dict[str, Any]) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(coro, timeout=deps.timeout_s)
    except asyncio.TimeoutError:
        return {**empty, "degraded": True, "degraded_reason": "memory_timeout"}
    except Exception:  # noqa: BLE001
        return {**empty, "degraded": True, "degraded_reason": "memory_unreachable"}


# ------------------------------------------------------------------ views
async def facts_view(deps: MemoryDeps, village: str, *, subject: str | None = None, as_of: Any = None) -> dict[str, Any]:
    at = cv.to_dt(as_of) or deps.now()
    mir = mirror(deps, village)
    if subject:
        mir_s = [d for d in mir if d["entity"] == subject]
    else:
        mir_s = mir
    resp: dict[str, Any] = {"village": village, "as_of": cv.iso(at), "facts": [], "degraded": False}
    if subject:
        resp["subject"] = subject
    keys = sorted({(d["entity"], d["key"]) for d in mir_s})
    if as_of is None:
        ents = sorted({e for e, _ in keys} | ({subject} if subject else set()))
        res = await _guard(deps.client.facts_for(village, ents), deps, {"facts": []})
        cards = [] if res.get("degraded") else [card_from_am(r, village, r["_entity"], mir) for r in res["facts"]]
    else:
        hs = await _guard(asyncio.gather(*(deps.client.fact_history(e, k, village=village) for e, k in keys)),
                          deps, {"history": []})
        if isinstance(hs, dict):
            res = hs
            cards = []
        else:
            res = {"degraded": any(h["degraded"] for h in hs)}
            if res["degraded"]:
                res["degraded_reason"] = next(h.get("degraded_reason") for h in hs if h["degraded"])
            cards = []
            for (e, k), h in zip(keys, hs):
                for row in h["history"]:
                    c = card_from_am(row, village, e, mir)
                    if _valid_at(c, at):
                        cards.append(c)
    if res.get("degraded"):
        resp.update(degraded=True, degraded_reason=res.get("degraded_reason") or "memory_unreachable")
        cards = [card_from_draft(d) for d in mir_s if _valid_at(card_from_draft(d), at)]
    elif not cards and mir_s:
        resp.update(degraded=True, degraded_reason="outbox_backlog")
        cards = [card_from_draft(d) for d in mir_s if _valid_at(card_from_draft(d), at)]
    if as_of is None and not resp["degraded"] and deps.extra.get("drafts") is not None:
        have = {(c["entity"], c["key"]) for c in cards}  # direct (non-ledger) facts AM hasn't surfaced yet
        cards += [card_from_draft(d) for d in mir_s if d.get("event_id") is None and not d["superseded"] and (d["entity"], d["key"]) not in have]
    if subject:
        cards = [c for c in cards if c["entity"] == subject]
    cards.sort(key=lambda c: c["observed_at"], reverse=True)
    resp["facts"] = cards[:500]
    return resp


async def history_view(deps: MemoryDeps, village: str, entity: str, key: str) -> dict[str, Any]:
    key = cv.norm_key(key)
    mir = mirror(deps, village)
    resp: dict[str, Any] = {"village": village, "entity": entity, "key": key, "versions": [], "degraded": False}
    h = await _guard(deps.client.fact_history(entity, key, village=village), deps, {"history": []})
    rows = h.get("history") or []
    rows = [r for r in rows if cv.parse_labels(r.get("labels")).get("village", village) == village]
    if h.get("degraded") or (not rows and any(d["entity"] == entity and d["key"] == key for d in mir)):
        resp.update(degraded=True, degraded_reason=h.get("degraded_reason") or "outbox_backlog")
        chain = [d for d in mir if d["entity"] == entity and d["key"] == key]
        resp["versions"] = [version_from_draft(d) for d in sorted(chain, key=lambda d: cv.to_dt(d["observed_at"]), reverse=True)]
        return resp
    id_map = {r["id"]: cv.fact_id(key, entity, cv.iso(r.get("createdAt"))) for r in rows if r.get("id")}
    cards = [card_from_am(r, village, entity, mir, id_map) for r in rows]
    cards.sort(key=lambda c: c["observed_at"], reverse=True)
    resp["versions"] = [version_from_card(c) for c in cards][:200]
    return resp


def _candidates_from_reason(reason: str, u: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    created = cv.iso(u.get("createdAt"))
    for i, (kind, val) in enumerate(re.findall(r"(\w+) fact = \"(.*?)\"", reason or "")):
        out.append({"id": f"fact:{cv.norm_key(u.get('key', 'k'))}:{kind}:{i}", "value": val[:400],
                    "text": f"{kind.capitalize()} says {val}."[:300], "observed_at": created, "recorded_at": created,
                    "superseded": False, "source": {"kind": "system", "ref": f"memory:{kind}"}})
    return out


async def uncertainties_view(deps: MemoryDeps, village: str) -> dict[str, Any]:
    resp: dict[str, Any] = {"village": village, "uncertainties": [], "degraded": False}
    r = await _guard(deps.client.uncertainties(village), deps, {"uncertainties": []})
    if r.get("degraded"):
        resp.update(degraded=True, degraded_reason=r.get("degraded_reason") or "memory_unreachable")
        return resp
    mir = mirror(deps, village)
    for u in r["uncertainties"][:100]:
        entity = cv.entity_from_am(u.get("entity"), village)
        key = cv.norm_key(u.get("key", "fact_key"))
        cands = []
        h = await _guard(deps.client.fact_history(entity, key, village=village), deps, {"history": []})
        for row in h.get("history") or []:
            if not row.get("validUntil") and not row.get("supersededBy"):
                cands.append(version_from_card(card_from_am(row, village, entity, mir)))
        if len(cands) < 2:
            seen = {c["value"] for c in cands}
            cands += [c for c in _candidates_from_reason(u.get("reason", ""), u) if c["value"] not in seen]
        if len(cands) < 2:
            continue
        name = cv.member_names().get(entity, entity).split()[0]
        item = {"id": "unc_" + re.sub(r"[^A-Za-z0-9_]", "_", str(u.get("id")))[:64], "village": village,
                "entity": entity, "key": key,
                "question": {"en": f"Two sources disagree about {name}'s {key.replace('_', ' ')}: "
                                   + " or ".join(c["value"] for c in cands[:3]) + "?",
                             "es": f"Dos fuentes no coinciden sobre {key.replace('_', ' ')} de {name}: "
                                   + " o ".join(c["value"] for c in cands[:3]) + "?"},
                "candidates": cands[:6], "status": "resolved" if u.get("resolved") else "open",
                "created_at": cv.iso(u.get("createdAt"))}
        if item["status"] == "resolved":
            item["status"] = "open"  # AM gives no resolver/timestamp in the list; only unresolved are listed
        resp["uncertainties"].append(item)
    return resp


async def resolve_view(deps: MemoryDeps, village: str, uid: str, req: dict[str, Any], by: str | None = None) -> tuple[int, dict[str, Any]]:
    """Returns (http_status, body). 404 unknown uid; 503 + degraded when memory is down."""
    by = by or village_reg.coordinator_id(village) or COORDINATOR
    listing = await uncertainties_view(deps, village)
    if listing["degraded"]:
        return 503, {"degraded": True, "degraded_reason": listing.get("degraded_reason", "memory_unreachable")}
    unc = next((u for u in listing["uncertainties"] if u["id"] == uid), None)
    if unc is None:
        return 404, {"detail": "unknown uncertainty", "degraded": False}
    value = req["accepted_value"]
    r = await _guard(deps.client.resolve_uncertainty(uid, value, by, note=req.get("note")), deps, {})
    if r.get("degraded"):
        return 503, {"degraded": True, "degraded_reason": r.get("degraded_reason") or "memory_unreachable"}
    now = deps.now()
    src = {"kind": "app", "ref": by}
    w = await deps.client.remember_fact(unc["entity"], unc["key"], value, source=src, village=village,
                                        agent="memory", observed_at=now, extra_labels={"resolves": uid})
    name = cv.member_names().get(by, by).split()[0]
    fact = {"id": cv.fact_id(unc["key"], unc["entity"], now), "village": village, "entity": unc["entity"], "key": unc["key"],
            "value": value, "text": f"{name} settled it: {unc['key'].replace('_', ' ')} is {value}."[:300],
            "labels": {"src": f"app:{by}", "village": village, "agent": "memory"},
            "observed_at": cv.iso(now), "recorded_at": cv.iso(now), "valid_to": None, "superseded": False, "source": src}
    resolved = {**unc, "status": "resolved", "resolved_at": cv.iso(now), "resolved_by": by, "accepted_value": value}
    if req.get("accepted_fact_id"):
        resolved["accepted_fact_id"] = req["accepted_fact_id"]
    if req.get("note"):
        resolved["note"] = req["note"][:300]
    body: dict[str, Any] = {"uncertainty": resolved, "fact": fact, "degraded": bool(w.get("degraded"))}
    if w.get("degraded"):
        body["degraded_reason"] = w.get("degraded_reason") or "memory_unreachable"
    if deps.write_decision:
        did = f"dc_unc_{re.sub(r'[^A-Za-z0-9_]', '_', uid)[:50]}"
        row = {"id": did, "village_id": village, "at": cv.iso(now), "actor": "evolve", "kind": "decision",
               "text": f"{name} settled {cv.member_names().get(unc['entity'], unc['entity']).split()[0]}'s "
                       f"{unc['key'].replace('_', ' ')}: {value}. The other values are kept as superseded."[:400],
               "refs": [{"kind": "fact", "id": fact["id"]}, {"kind": "member", "id": by}],
               "source": {"kind": "app", "ref": by}, "mode": "asked_human"}
        try:
            await deps.write_decision(row)
            body["decision_id"] = did
        except Exception:  # noqa: BLE001
            pass
    return 200, body
