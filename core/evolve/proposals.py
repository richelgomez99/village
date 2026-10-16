"""Evolve proposals (D15/D19): propose -> approve -> release pipeline -> apply (live patch) -> 10 s undo.

The wire Proposal validates against contracts/schemas/proposal.schema.json. Two things the contract has no
field for ride in a core-side sidecar on the stored record (never on the wire):
  * `options`: the consider_options weighing (also in the decision row);
  * `voice_ops`: spec ops outside views/printables. The receptionist flag lives in the spec as
    `policies[R-MONEY-UNKNOWN].params.receptionist_mode = true` (schema-valid; contract spec_ops only allow
    /printables/). See LANE-REPORT LD-1.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import os
import time
from typing import Any

from core import village as villages
from core.clock import clock
from core.db import db

log = logging.getLogger("village.evolve")

UNDO_WINDOW_S = 10.0
RECEPTIONIST_RULE = "R-MONEY-UNKNOWN"

# village_id -> proposal_id -> record {proposal, options, voice_ops, spec_before, ...}
STORE: dict[str, dict[str, dict[str, Any]]] = {}
TASKS: dict[str, asyncio.Task[Any]] = {}
TIMINGS: dict[str, dict[str, Any]] = {}
_SEQ: dict[str, int] = {}


class ProposalError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def reset(village_id: str | None = None) -> None:
    if village_id is None:
        STORE.clear()
        TIMINGS.clear()
    else:
        STORE.pop(village_id, None)
        TIMINGS.pop(village_id, None)


def _now() -> str:
    return clock.now().isoformat()


def _slug(village_id: str) -> str:
    return village_id.removeprefix("v_").replace("-", "_")


def _validator():  # type: ignore[no-untyped-def]
    from core.release.receipts import _validator as v

    return v("proposal.schema.json")


def validate(proposal: dict[str, Any]) -> list[str]:
    return [f"{'/'.join(map(str, e.path))}: {e.message}"[:300] for e in _validator().iter_errors(proposal)]


def _prune(village_id: str) -> None:
    """Forget proposals a demo reset made stale (spec back below their rev, or their evidence events gone)."""
    recs = STORE.get(village_id)
    if not recs:
        return
    rev = int(villages.spec(village_id).get("rev", 0))
    ids = {e.get("id") for e in db.events}
    dids = {d.get("id") for d in db.decisions}
    for pid in list(recs):
        r = recs[pid]
        p = r["proposal"]
        if p["status"] == "verifying":
            continue
        gone = any(e not in ids for e in (r.get("evidence_meta") or {}).get("event_ids") or [])
        reset = f"dc_{pid}_proposed" not in dids  # a demo reset clears the decision log
        if reset or p["base_rev"] > rev or (p["status"] == "applied" and int(p.get("target_rev", 0)) > rev) or gone:
            recs.pop(pid)


def list_proposals(village_id: str) -> list[dict[str, Any]]:
    _prune(village_id)
    return [copy.deepcopy(r["proposal"]) for r in STORE.get(village_id, {}).values()]


def get_record(village_id: str, pid: str) -> dict[str, Any]:
    rec = STORE.get(village_id, {}).get(pid)
    if rec is None:
        raise ProposalError(404, f"no proposal {pid}")
    return rec


def find_active(village_id: str, key: str) -> dict[str, Any] | None:
    """A proposal for this pattern key that is open, applied, or was declined (declined ones are remembered)."""
    _prune(village_id)
    for rec in STORE.get(village_id, {}).values():
        if rec.get("key") == key and rec["proposal"]["status"] != "failed":
            return rec
    return None


# ---- ops ------------------------------------------------------------------------------------------
def _role_of(spec: dict[str, Any], member_id: str | None) -> str | None:
    p = next((x for x in spec.get("blueprint", {}).get("people", []) if x.get("id") == member_id), None)
    return (p or {}).get("view")


def _need_id(spec: dict[str, Any]) -> str:
    return next((n["id"] for n in spec.get("blueprint", {}).get("needs", []) if n.get("domain") == "money"), "n_safety")


MAX_CHILDREN = 12  # village_spec.schema.json Screen children maxItems


def _insert_at(view: dict[str, Any]) -> int:
    kids = view["elements"].get(view.get("root", "s"), {}).get("children", [])
    return 1 if kids else 0


async def build_ops(village_id: str, spec: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Per-role view ops (via core.builder.patch), spec_ops (printables) and voice_ops (receptionist flag)."""
    from core.builder.patch import apply_to_copy

    recipient = evidence.get("subject") or villages.care_recipient_id(village_id)
    elder_role = _role_of(spec, recipient)
    need = _need_id(spec)
    rel_en = villages.relationship_word(village_id, recipient, "en") or "them"
    ops: dict[str, list[dict[str, Any]]] = {}
    needs_served: dict[str, dict[str, list[str]]] = {}
    highlight: dict[str, list[str]] = {}
    cand = copy.deepcopy(spec)
    for role, view in spec.get("views", {}).items():
        els = view.get("elements", {})
        if "receptionist" in els or "screened" in els:
            continue
        root = view.get("root", "s")
        kids = list(els.get(root, {}).get("children", []))

        def after(el_type: str) -> int | None:
            """Index right after the first root child of this catalog type (D35: the right place, in the app's structure)."""
            for i, eid in enumerate(kids):
                if els.get(eid, {}).get("type") == el_type:
                    return i + 1
            return None

        if len(kids) + 1 > MAX_CHILDREN:
            log.info("evolve: %s screen is full (%d); no element added", role, len(kids))
            continue
        if role == elder_role:
            # a quiet one-sentence status directly under TonightCard (her app stays 3 big buttons)
            at = after("TonightCard") or 1
            lang = view.get("lang", "es")
            text = ("Village contesta primero las llamadas de números desconocidos." if lang == "es"
                    else "Village answers calls from unknown numbers first.")
            eid, el = "receptionist", {"type": "Text", "props": {"text": text, "size": "m", "tone": "muted"}}
        elif after("LifeAreas") is not None:
            # leader: one card inside the Money area (LifeAreas money status says it too, via blueprint:life_areas)
            at = after("LifeAreas")
            eid, el = "screened", {"type": "ScreenedCalls", "props": {"title": "Calls Village screened", "bind": "calls:screened", "max_rows": 5}}
        elif after("HelperAnswer") is not None:
            at = after("HelperAnswer")
            eid, el = "receptionist", {"type": "ScreenedCalls", "props": {"title": "Calls Village checked with you", "bind": "calls:screened", "max_rows": 3}}
        else:
            continue
        role_ops = [{"op": "add", "path": f"/elements/{eid}", "value": el},
                    {"op": "add", "path": f"/elements/{root}/children/{at}", "value": eid}]
        served = {eid: [need]}
        nxt, errs = apply_to_copy(cand, role, {"ops": role_ops, "needs_served": served})
        if nxt is None:
            log.warning("evolve ops for %s invalid: %s", role, errs[:3])
            continue
        cand = nxt
        ops[role] = role_ops
        needs_served[role] = served
        highlight[role] = [o["path"].split("/")[2] for o in role_ops if o["path"].count("/") == 2]
    spec_ops = []
    for i, pr in enumerate(spec.get("printables", [])):
        if pr.get("kind") == "fridge_card" and pr.get("member_id") in (recipient, None) and not pr.get("family_word_first"):
            spec_ops.append({"op": "replace", "path": f"/printables/{i}/family_word_first", "value": True})
    voice_ops = []
    idx = next((i for i, p in enumerate(spec.get("policies", [])) if p.get("rule_id") == RECEPTIONIST_RULE), None)
    if idx is None:
        voice_ops.append({"op": "add", "path": "/policies/-", "value": {"rule_id": RECEPTIONIST_RULE, "params": {"receptionist_mode": True},
                                                                         **({"applies_to_member_ids": [recipient]} if recipient else {})}})
    else:
        if "params" not in spec["policies"][idx]:
            voice_ops.append({"op": "add", "path": f"/policies/{idx}/params", "value": {}})
        voice_ops.append({"op": "add", "path": f"/policies/{idx}/params/receptionist_mode", "value": True})
    return {"ops": ops, "needs_served": needs_served, "spec_ops": spec_ops, "voice_ops": voice_ops, "highlight": highlight}


def candidate_spec(spec: dict[str, Any], rec: dict[str, Any], rev: int) -> dict[str, Any]:
    """The whole spec with every op of the proposal applied (views, printables, voice flag), as `rev`."""
    from core.builder.patch import apply_ops, apply_to_copy

    p = rec["proposal"]
    cand = copy.deepcopy(spec)
    for role, role_ops in p["ops"].items():
        nxt, errs = apply_to_copy(cand, role, {"ops": role_ops, "needs_served": (p.get("needs_served") or {}).get(role, {})})
        if nxt is None:
            raise ProposalError(409, f"ops for {role} no longer apply: {errs[:1]}")
        cand = nxt
    cand = apply_ops(cand, list(p.get("spec_ops", [])) + list(rec.get("voice_ops", [])))
    cand["rev"] = rev
    return cand


# ---- propose --------------------------------------------------------------------------------------
async def propose(village_id: str, evidence: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build, validate, store and announce one proposal (chat post with Approve + control{proposal})."""
    from core import services

    spec = copy.deepcopy(villages.spec(village_id))
    built = await build_ops(village_id, spec, evidence)
    if not built["ops"]:
        raise ProposalError(409, "nothing to change: receptionist already on every view")
    recipient = evidence.get("subject") or villages.care_recipient_id(village_id)
    claimed = villages.first_name(village_id, evidence.get("claimed_member_id"), "a family member")
    rel_en = villages.relationship_word(village_id, recipient, "en") or "them"
    rel_es = villages.relationship_word(village_id, recipient, "es") or rel_en
    coord = villages.coordinator_id(village_id)
    coord_name = villages.first_name(village_id, coord, "the coordinator")
    _SEQ[village_id] = _SEQ.get(village_id, 0) + 1
    pid = f"prop_{_slug(village_id)}_receptionist_{_SEQ[village_id]}"
    copy_ = plain_copy(village_id, spec, evidence)
    proposal: dict[str, Any] = {
        "id": pid, "village": village_id,
        "detected_by": evidence.get("detected_by") if evidence.get("detected_by") in {"arize_eval", "memory_pattern"} else "memory_pattern",
        "title": {"en": f"Village answers unknown callers for {rel_en}", "es": f"Village contesta a desconocidos por {rel_es}"},
        "rationale": copy_["rationale"],
        "changes": copy_["changes"][:6],
        "evidence": [e for e in (evidence.get("evidence") or []) if _evidence_ok(e)][:12],
        "ops": built["ops"], "needs_served": built["needs_served"], "spec_ops": built["spec_ops"],
        "status": "proposed", "base_rev": int(spec.get("rev", 0)), "created_at": _now(),
    }
    if not proposal["evidence"]:
        proposal["evidence"] = [{"kind": "fact", "ref": f"pattern:{evidence.get('pattern', 'manual')}", "label": "Manual trigger (Control Room)"}]
    errs = validate(proposal)
    if errs:
        raise ProposalError(500, f"proposal invalid: {errs[:2]}")
    await db.create_decision({
        "id": f"dc_{pid}_proposed", "village_id": village_id, "at": _now(), "actor": "evolve", "kind": "decision",
        "text": f"Proposed: {proposal['title']['en']} ({_chosen_name(options)}). Waiting for {coord_name}."[:400],
        "rule_id": "R-SPEC", "mode": "asked_human", "rev": proposal["base_rev"],
        "refs": [{"kind": "event", "id": e} for e in (evidence.get("event_ids") or [])[:4]] + ([{"kind": "member", "id": coord}] if coord else []),
        "source": {"kind": "system", "ref": "evolve"},
    })
    rec = {"proposal": proposal, "options": options, "voice_ops": built["voice_ops"], "highlight": built["highlight"],
           "key": f"{evidence.get('pattern', 'manual')}:{evidence.get('subject')}:{evidence.get('claimed_member_id')}",
           "evidence_meta": {k: evidence.get(k) for k in ("pattern", "count", "event_ids", "text")},
           "evidence_labels": copy_["evidence_labels"], "what_happened": copy_["rationale"],
           "stays_the_same": copy_["stays_the_same"], "checked": copy_["checked"]}
    STORE.setdefault(village_id, {})[pid] = rec
    text = copy_["chat"]["en"]
    msg = await services.post_message(
        village_id, author="village", kind="proposal", text=text[:2000],
        refs=[{"kind": "proposal", "id": pid, "label": "proposal"}] + [{"kind": "event", "id": e} for e in (evidence.get("event_ids") or [])[:3]],
        source={"kind": "system", "ref": "evolve"},
        text_i18n={"en": copy_["chat"]["en"][:600], "es": copy_["chat"]["es"][:600]},
    )
    proposal["message_id"] = msg["id"]
    await _announce(village_id, rec)
    await services.ledger(village_id, f"prop:{pid}", "queued", f"Proposal · {proposal['title']['en']}", result="waiting for approval",
                          decision_id=f"dc_{pid}_proposed", role="Watcher")
    await services.reasoning(village_id, f"Asked {coord_name}: {proposal['title']['en']}. Nothing changes until {coord_name} says yes.",
                             source="evolve", kind="decision", mode="asked_human")
    try:
        await db.upsert_record("proposal", pid, copy.deepcopy(proposal))
    except Exception:  # noqa: BLE001
        log.exception("proposal persist failed")
    return copy.deepcopy(proposal)


# ---- plain words (Ana's card, the chat post) -----------------------------------------------------------
_NUM_EN = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}
_NUM_ES = {1: "Una", 2: "Dos", 3: "Tres", 4: "Cuatro", 5: "Cinco"}
_METHOD_EN = {"gift_card": " in gift cards", "crypto": " in crypto", "wire_to_stranger": " by wire", "cash_courier": " in cash by courier"}
_METHOD_ES = {"gift_card": " en tarjetas de regalo", "crypto": " en cripto", "wire_to_stranger": " por giro", "cash_courier": " en efectivo"}
_MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _local(at: str, village_id: str):  # type: ignore[no-untyped-def]
    from datetime import datetime
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
    try:
        return dt.astimezone(ZoneInfo(villages.timezone(village_id)))
    except Exception:  # noqa: BLE001
        return dt


def _amount(p: dict[str, Any], lang: str) -> str:
    amt = p.get("amount")
    money = f"${amt:,.0f}" if isinstance(amt, (int, float)) and amt else ("money" if lang == "en" else "dinero")
    return money + (_METHOD_EN if lang == "en" else _METHOD_ES).get(p.get("method") or "", "")


def _join(names: list[str], word: str) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" {word} " + names[-1]


def latest_scam_eval() -> dict[str, Any] | None:
    """Most recent base-set scam experiment on disk (evals/out), model runs preferred; None if absent."""
    import glob
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "evals" / "out"
    rows = []
    for f in sorted(glob.glob(str(root / "scam_experiment_*.json"))):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:  # noqa: BLE001
            continue
        sm = d.get("summary") or {}
        if sm.get("n_village") == 0 and sm.get("scams") and sm.get("benign") is not None:
            rows.append((str(d.get("mode", "")).startswith("model"), f, sm))
    if not rows:
        return None
    return max(rows)[2]


def plain_copy(village_id: str, spec: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """What happened / what changes per person / what stays the same / what was checked, in plain words (no ids)."""
    recipient = evidence.get("subject") or villages.care_recipient_id(village_id)
    claimed_id = evidence.get("claimed_member_id")
    claimed = villages.first_name(village_id, claimed_id, "a family member")
    rel_en = villages.relationship_word(village_id, recipient, "en") or "them"
    rel_es = villages.relationship_word(village_id, recipient, "es") or rel_en
    pr = villages.pronoun(villages.person(village_id, recipient))
    her = {"she": "her", "he": "his"}.get(pr, "their")
    her_obj = {"she": "her", "he": "him"}.get(pr, "them")
    cpr = villages.pronoun(villages.person(village_id, claimed_id))
    him, he = {"she": "her", "he": "him"}.get(cpr, "them"), cpr if cpr in {"he", "she"} else "they"
    he_gets = f"{he} {'gets' if he != 'they' else 'get'}"
    ids = set(evidence.get("event_ids") or [])
    evs = sorted((e for e in db.events if e.get("id") in ids and e.get("kind") == "money_request"), key=lambda e: e["at"])
    today = clock.now().date()
    n = len(evs) or int(evidence.get("count") or 0) or 2
    days = int(evidence.get("window_days") or 7)
    when_en, when_es, labels = [], [], []
    for e in evs:
        loc = _local(e["at"], village_id)
        is_today = loc.date() == today
        day_en = "today" if is_today else f"{loc:%b} {loc.day}"
        day_es = "hoy" if is_today else f"{loc.day} {_MONTHS_ES[loc.month - 1]}"
        when_en.append(f"{day_en} ({_amount(e['payload'], 'en')})")
        when_es.append(f"{day_es} ({_amount(e['payload'], 'es')})")
        clock_s = f"{loc:%I:%M %p}".lstrip("0")
        said = f"caller said {'she' if cpr == 'she' else 'he' if cpr == 'he' else 'they'} was {claimed}"
        labels.append(f"{'Today' if is_today else day_en}, {clock_s} · {said} · asked for {_amount(e['payload'], 'en')}"[:160])
    calls_en = f"{_NUM_EN.get(n, str(n))} call{'s' if n != 1 else ''}"
    calls_es = f"{_NUM_ES.get(n, str(n))} llamada{'s' if n != 1 else ''}"
    stopped_en = "It was stopped." if n == 1 else ("Both were stopped." if n == 2 else f"All {n} were stopped.")
    stopped_es = "La detuvimos." if n == 1 else ("Las dos se detuvieron." if n == 2 else f"Las {n} se detuvieron.")
    if when_en:
        when_en[0] = when_en[0][:1].upper() + when_en[0][1:]
        when_es[0] = when_es[0][:1].upper() + when_es[0][1:]
    what_en = (f"{calls_en} in {days} days asked {rel_en} for money in {claimed}'s name"
               + (f": {_join(when_en, 'and')}" if when_en else "") + f". {stopped_en} The next one could reach {her_obj} first.")
    what_es = (f"{calls_es} en {days} días le pidieron dinero a {rel_es} en nombre de {claimed}"
               + (f": {_join(when_es, 'y')}" if when_es else "") + f". {stopped_es} La próxima podría llegarle a {'ella' if pr == 'she' else 'él'} primero.")
    changes: list[dict[str, str]] = [
        {"en": f"{rel_en}: unknown callers reach Village first; family still rings straight through; {her} number does not change.",
         "es": f"{rel_es}: los desconocidos hablan primero con Village; la familia sigue entrando directo; su número no cambia."},
    ]
    if claimed_id and claimed_id != recipient:
        changes.append({"en": f"{claimed}: when a caller claims to be {him}, {he_gets} one question on {'her' if cpr == 'she' else 'his' if cpr == 'he' else 'their'} phone.",
                        "es": f"{claimed}: cuando alguien dice ser {claimed}, le llega una pregunta a su teléfono."})
    views = spec.get("views", {})
    leaders = [villages.first_name(village_id, p["id"]) for p in spec.get("blueprint", {}).get("people", [])
               if p.get("view") in views and p["id"] not in {recipient, claimed_id}
               and any(e.get("type") == "LifeAreas" for e in views[p["view"]].get("elements", {}).values())]
    if leaders:
        changes.append({"en": f"{_join(leaders, 'and')}: the Money area says Village answers unknown calls first, with a card of every screened call.",
                        "es": f"{_join(leaders, 'y')}: el área de Dinero dice que Village contesta primero a desconocidos, con una tarjeta de cada llamada revisada."})
    stays = {"en": f"Nothing moves money. {rel_en} can turn this off by saying so. {her[:1].upper() + her[1:]} rules still apply.",
             "es": f"Nada mueve dinero. {rel_es} puede apagarlo con solo decirlo. Sus reglas siguen igual."}
    changes.append(stays)
    checked = None
    ev = latest_scam_eval()
    if ev:
        checked = {"en": f"Tested against {ev['scams']} scam and {ev['benign']} real family calls: {ev['caught']} caught, "
                         f"{ev['false_alarms']} false alarm{'s' if ev['false_alarms'] != 1 else ''}.",
                   "es": f"Probado con {ev['scams']} llamadas de estafa y {ev['benign']} llamadas reales de la familia: "
                         f"{ev['caught']} detectadas, {ev['false_alarms']} falsas alarmas."}
        changes.append(checked)
    chat_en = (f"After {calls_en.lower()} asked {rel_en} for money in {claimed}'s name, Village proposes answering unknown callers "
               f"for {her_obj} first; nothing changes until you approve.")
    chat_es = (f"Después de {calls_es.lower()} pidiendo dinero a {rel_es} en nombre de {claimed}, Village propone contestar "
               f"primero a los desconocidos; nada cambia hasta que usted lo apruebe.")
    return {"rationale": {"en": what_en[:600], "es": what_es[:600]}, "changes": changes, "stays_the_same": stays,
            "checked": checked, "evidence_labels": labels, "chat": {"en": chat_en, "es": chat_es}}


def bv_row(village_id: str, p: dict[str, Any]) -> dict[str, Any]:
    """proposals:pending row (bv_proposal) in plain words: what happened first, then per person, stays, checked."""
    rec = STORE.get(village_id, {}).get(p["id"], {})
    what = rec.get("what_happened") or p.get("rationale")
    changes = ([what] if what else []) + [c for c in p.get("changes", []) if isinstance(c, dict) and c]
    labels = rec.get("evidence_labels") or [str(e.get("label") or e.get("kind")) for e in p.get("evidence", [])
                                            if isinstance(e, dict) and e.get("kind") == "call_moment"]
    row: dict[str, Any] = {"proposal_id": p["id"], "title": p.get("title") or {"en": "A change for the village"},
                           "changes": changes, "evidence_labels": labels, "status": p["status"]}
    if p.get("release_id"):
        row["release_id"] = p["release_id"]
    return row


_CALL_MOMENT = __import__("re").compile(r"^[A-Za-z0-9_-]{3,128}@[0-9]+(\.[0-9]+)?$")


def _evidence_ok(e: dict[str, Any]) -> bool:
    """Drop rows the contract would reject (e.g. a too-short conversation id) instead of failing the proposal."""
    return isinstance(e, dict) and (e.get("kind") != "call_moment" or bool(_CALL_MOMENT.match(str(e.get("ref", "")))))


def _chosen_name(options: dict[str, Any] | None) -> str:
    return next((c["name"] for c in (options or {}).get("candidates", []) if c.get("chosen")), "receptionist")


async def _announce(village_id: str, rec: dict[str, Any]) -> None:
    from core import services

    await services.control(village_id, "proposal", {"proposal": copy.deepcopy(rec["proposal"])})
    try:  # Ana's Proposal card (proposals:pending) appears / updates live
        await services.hub.push_proposals(village_id, copy.deepcopy(rec["proposal"]))
    except Exception:  # noqa: BLE001 - a card refresh must never break the proposal pipeline
        log.exception("push proposals:pending failed")


async def _decision(village_id: str, pid: str, step: str, text: str, mode: str, rev: int | None = None,
                    refs: list[dict[str, Any]] | None = None) -> str:
    did = f"dc_{pid}_{step}"
    row: dict[str, Any] = {"id": did, "village_id": village_id, "at": _now(), "actor": "evolve" if step != "release" else "release",
                           "kind": "decision", "text": text[:400], "rule_id": "R-SPEC", "mode": mode, "refs": refs or [],
                           "source": {"kind": "system", "ref": "evolve" if step != "release" else "release"}}
    if rev is not None:
        row["rev"] = rev
    await db.create_decision(row)
    return did


# ---- approve / reject -----------------------------------------------------------------------------
def authorize(village_id: str, who: str | None) -> str:
    """Leader (coordinator) member token or the control token. Returns the actor id."""
    if who == "control":
        return villages.coordinator_id(village_id) or "control"
    if who and who == villages.coordinator_id(village_id):
        return who
    raise ProposalError(403, "only the village leader (or the Control Room) can approve")


async def approve(village_id: str, pid: str, actor: str, *, wait: bool = False) -> dict[str, Any]:
    from core import services
    from core.release.pipeline import release_id

    rec = get_record(village_id, pid)
    p = rec["proposal"]
    if p["status"] not in {"proposed", "ready"}:
        raise ProposalError(409, f"proposal is {p['status']}")
    t0 = time.perf_counter()
    live = villages.spec(village_id)
    base_rev = int(live.get("rev", p["base_rev"]))
    target = base_rev + 1
    cand = candidate_spec(live, rec, target)  # raises 409 if the ops no longer apply
    actor_id = actor if actor.startswith(("m_", "b_")) or "_" in actor else (villages.coordinator_id(village_id) or "m_unknown")
    p.update(status="verifying", target_rev=target, release_id=release_id(village_id, target), approved_by=actor_id, approved_at=_now())
    rec["spec_before"] = copy.deepcopy(live)
    rec["t_approve"] = t0
    TIMINGS[village_id] = {"proposal_id": pid, "approved_at": p["approved_at"]}
    name = villages.first_name(village_id, actor_id, "The leader")
    await _decision(village_id, pid, "approved", f"{name} approved “{p['title']['en']}”. Testing rev {target} before anything changes.",
                    "asked_human", target, [{"kind": "member", "id": actor_id}])
    await _announce(village_id, rec)
    await services.ledger(village_id, f"prop:{pid}", "running", f"Proposal · {p['title']['en']}", result=f"approved by {name}; testing rev {target}",
                          role="Watcher")
    task = asyncio.create_task(_verify_and_apply(village_id, pid, cand))
    TASKS[pid] = task
    if wait:
        await task
    return copy.deepcopy(p)


async def reject(village_id: str, pid: str, actor: str) -> dict[str, Any]:
    from core import services

    rec = get_record(village_id, pid)
    p = rec["proposal"]
    if p["status"] not in {"proposed", "verifying", "ready"}:
        raise ProposalError(409, f"proposal is {p['status']}")
    actor_id = actor if "_" in actor else (villages.coordinator_id(village_id) or "m_unknown")
    p.update(status="rejected", rejected_by=actor_id, rejected_at=_now())
    task = TASKS.get(pid)
    if task and not task.done():
        task.cancel()
    name = villages.first_name(village_id, actor_id, "The leader")
    await _decision(village_id, pid, "rejected", f"{name} said not now to “{p['title']['en']}”. Remembered; Village won't propose it again.",
                    "asked_human", p.get("base_rev"), [{"kind": "member", "id": actor_id}])
    await _announce(village_id, rec)
    await services.ledger(village_id, f"prop:{pid}", "refused", f"Proposal · {p['title']['en']}", result=f"not now ({name})", role="Watcher")
    return copy.deepcopy(p)


# ---- release + apply ------------------------------------------------------------------------------
def scored_on(village_id: str) -> tuple[int, int, int]:
    """D24 #11: sync resolved incidents into evals/sets/<village>.jsonl, then n_base + n_village."""
    try:
        from evals import incident_to_test
        from evals.scam_experiment import load_cases

        incident_to_test.sync_from_events(village_id, list(db.events))
        _, n_base, n_village = load_cases(village_id)
        return n_base + n_village, n_base, n_village
    except Exception:  # noqa: BLE001
        log.exception("incident_to_test count failed")
        return 0, 0, 0


def _ports() -> dict[str, Any]:
    """Release adapters: the shared ReleaseService's (real Daytona/Anchor/evals when configured), else fakes."""
    from core.release.service import get_service

    svc = get_service()
    mode = os.environ.get("VILLAGE_EVOLVE_RELEASE", "auto").lower()
    if mode == "fake" or svc.daytona is None:
        from core.release.fakes import FakeAnchor, FakeDaytona, FakeEvals

        return {"daytona": FakeDaytona(), "anchor": FakeAnchor(), "evals": FakeEvals(), "llm": None,
                "publisher": svc.publisher, "store": svc.store, "broadcast": svc.broadcast, "mode": "fake"}
    return {"daytona": svc.daytona, "anchor": svc.anchor, "evals": svc.evals, "llm": svc.llm, "publisher": svc.publisher,
            "store": svc.store, "broadcast": svc.broadcast, "mode": "real"}


async def _verify_and_apply(village_id: str, pid: str, cand: dict[str, Any]) -> None:
    from core import services
    from core.release.pipeline import run_release

    rec = get_record(village_id, pid)
    p = rec["proposal"]
    n_total, n_base, n_village = scored_on(village_id)
    scored = f"Scored on {n_total} calls (last night's included)" if n_village else f"Scored on {n_total} calls"
    ports = _ports()
    inner = ports["broadcast"]

    async def broadcast(vid: str, kind: str, payload: dict[str, Any]) -> None:
        if kind == "release":
            payload = copy.deepcopy(payload)
            for st in payload.get("receipt", {}).get("stages", []):
                if st.get("name") == "tests" and st.get("status") == "passed":
                    base = st.setdefault("details", {}).get("summary", "")
                    st["details"]["summary"] = f"{scored} · {base}"[:200] if base else scored
        await inner(vid, kind, payload)

    t_rel = time.perf_counter()
    try:
        receipt = await run_release(village_id, cand, cand["rev"], broadcast=broadcast, llm=ports["llm"], daytona=ports["daytona"],
                                    anchor=ports["anchor"], evals=ports["evals"], publisher=ports["publisher"], store=ports["store"],
                                    trigger="proposal", proposal_id=pid, publish=True)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("evolve release crashed")
        receipt = {"result": "blocked", "id": p.get("release_id"), "rev": cand["rev"], "stages": [],
                   "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    release_ms = int((time.perf_counter() - t_rel) * 1000)
    TIMINGS.setdefault(village_id, {}).update(release_ms=release_ms, release_mode=ports["mode"], scored_on=n_total,
                                              n_base=n_base, n_village=n_village)
    if p["status"] == "rejected":
        return
    if receipt.get("result") != "released":
        await _failed(village_id, rec, receipt)
        return
    new_rev = int(receipt.get("live_rev") or receipt.get("rev") or cand["rev"])
    if new_rev != cand["rev"]:  # the Builder repaired its own build (theme) and released rev+1
        cand = dict(cand, rev=new_rev)
    p.update(target_rev=new_rev, release_id=receipt.get("id") or p["release_id"])
    p["status"] = "approved"
    await apply_spec(village_id, rec, cand)
    p["status"] = "applied"
    ms = int((time.perf_counter() - rec["t_approve"]) * 1000)
    TIMINGS[village_id].update(approve_to_patched_ms=ms, apply_ms=rec.get("apply_ms"), applied_rev=new_rev)
    rec["applied_at"] = time.monotonic()
    await _announce(village_id, rec)
    await _decision(village_id, pid, "applied", f"Released rev {new_rev} and patched every phone: {p['title']['en']}. {scored}. Undo open for {int(UNDO_WINDOW_S)} s.",
                    "acted_alone", new_rev)
    await services.ledger(village_id, f"prop:{pid}", "done", f"Proposal · {p['title']['en']}", result=f"live as rev {new_rev} ({ms} ms)", role="Builder")
    chosen = next((c for c in (rec.get("options") or {}).get("candidates", []) if c.get("chosen")), None)
    rel_en = villages.relationship_word(village_id, villages.care_recipient_id(village_id), "en") or "them"
    text = (f"Done. {p['title']['en']} (rev {new_rev}). Built in a sandbox, tested, clicked through on a phone; {scored}. "
            f"Every phone updated. {rel_en[:1].upper() + rel_en[1:]} will be told tonight. Undo within {int(UNDO_WINDOW_S)} s.")
    await services.post_message(village_id, author="village", kind="receipt", text=text[:2000],
                                refs=[{"kind": "release", "id": p["release_id"], "label": "receipt"}, {"kind": "proposal", "id": pid}],
                                source={"kind": "system", "ref": "release"})
    if chosen:
        await services.ledger(village_id, f"opt:{(rec.get('options') or {}).get('decision_id')}:{chosen['key']}", "done",
                              f"Option · {chosen['name']}", result="passed the release gate", role="Watcher")


async def _failed(village_id: str, rec: dict[str, Any], receipt: dict[str, Any]) -> None:
    from core import services

    p = rec["proposal"]
    p["status"] = "failed"
    stage = next((s for s in receipt.get("stages", []) if s.get("status") == "failed"), {})
    why = (stage.get("details") or {}).get("summary") or receipt.get("error") or "a release check failed"
    live = villages.spec(village_id).get("rev")
    await _announce(village_id, rec)
    await _decision(village_id, p["id"], "failed", f"Release blocked at {stage.get('name', 'release')}: {why}. Rev {live} stays live; nothing changed.",
                    "refused", live)
    await services.ledger(village_id, f"prop:{p['id']}", "refused", f"Proposal · {p['title']['en']}", result=f"blocked: {why}"[:400], role="Builder")
    await services.post_message(village_id, author="village", kind="receipt",
                                text=f"Not published: {why}. Rev {live} stays live; nothing changed on anyone's phone."[:2000],
                                refs=[{"kind": "release", "id": receipt.get("id") or p.get("release_id") or "rel_unknown"}, {"kind": "proposal", "id": p["id"]}],
                                source={"kind": "system", "ref": "release"})


async def apply_spec(village_id: str, rec: dict[str, Any], cand: dict[str, Any]) -> None:
    """Store the new spec + views (rev bump), then push `patch` frames to every member socket (snapshot to control)."""
    t0 = time.perf_counter()
    p = rec["proposal"]
    old_rev = int(villages.spec(village_id).get("rev", p["base_rev"]))
    new_rev = int(cand["rev"])
    slug = _slug(village_id)
    await db.upsert_record("spec_rev", f"{slug}_r{new_rev}", {"id": f"spec_{slug}_r{new_rev}", "village": village_id, "rev": new_rev, "spec": cand})
    db.specs[village_id] = cand
    for role, view in cand.get("views", {}).items():
        await db.upsert_record("view", f"{slug}_{role}", {"id": f"view_{slug}_{role}", "village": village_id, "role": role, "rev": new_rev, "spec": view})
    sent = await push(village_id, old_rev, new_rev, p["ops"], pid=p["id"], highlight=rec.get("highlight") or {})
    rec["apply_ms"] = int((time.perf_counter() - t0) * 1000)
    rec["sockets_patched"] = sent


async def push(village_id: str, old_rev: int, new_rev: int, ops: dict[str, list[dict[str, Any]]], *, pid: str | None = None,
               highlight: dict[str, list[str]] | None = None) -> dict[str, int]:
    """patch{base_rev, ops} to every socket of each role with ops; a fresh snapshot to the rest (control, other roles)."""
    from core.ws_hub import hub, snapshot

    sent = {"patch": 0, "snapshot": 0}
    for client in list(hub.clients):
        if client.village != village_id:
            continue
        role_ops = ops.get(client.role) if client.role != "control" else None
        try:
            if role_ops:
                frame: dict[str, Any] = {"type": "patch", "rev": new_rev, "base_rev": old_rev, "role": client.role, "ops": role_ops}
                if pid:
                    frame["proposal_id"] = pid
                if highlight and highlight.get(client.role):
                    frame["highlight"] = highlight[client.role]
                await client.ws.send_json(frame)
                sent["patch"] += 1
            else:
                await client.ws.send_json(snapshot(village_id, client.role, client.member_id, view_as=client.view_as))
                sent["snapshot"] += 1
        except Exception:  # noqa: BLE001
            hub.disconnect(client.ws)
    return sent


async def undo(village_id: str, pid: str, actor: str) -> dict[str, Any]:
    """Within UNDO_WINDOW_S of applying: put rev N's spec back (published as a new monotonic rev) and resnapshot phones."""
    from core import services

    rec = get_record(village_id, pid)
    p = rec["proposal"]
    if p["status"] != "applied" or "applied_at" not in rec:
        raise ProposalError(409, f"proposal is {p['status']}")
    if time.monotonic() - rec["applied_at"] > UNDO_WINDOW_S:
        raise ProposalError(409, "undo window closed")
    before = copy.deepcopy(rec["spec_before"])
    cur = int(villages.spec(village_id).get("rev", 0))
    restored_from = int(before.get("rev", p["base_rev"]))
    before["rev"] = cur + 1
    slug = _slug(village_id)
    await db.upsert_record("spec_rev", f"{slug}_r{cur + 1}", {"id": f"spec_{slug}_r{cur + 1}", "village": village_id, "rev": cur + 1, "spec": before})
    db.specs[village_id] = before
    for role, view in before.get("views", {}).items():
        await db.upsert_record("view", f"{slug}_{role}", {"id": f"view_{slug}_{role}", "village": village_id, "role": role, "rev": cur + 1, "spec": view})
    try:
        from core.release.service import get_service

        pub = get_service().publisher
        if (pub.dist_dir(village_id, restored_from)).exists():
            await pub.publish(village_id, restored_from)
    except Exception:  # noqa: BLE001
        log.info("undo: no published bundle for rev %s to repoint", restored_from)
    await push(village_id, cur, cur + 1, {}, pid=pid)
    actor_id = actor if "_" in actor else (villages.coordinator_id(village_id) or "m_unknown")
    p.update(status="rejected", rejected_by=actor_id, rejected_at=_now())
    rec["undone"] = {"at": _now(), "restored_rev": restored_from, "as_rev": cur + 1}
    await _announce(village_id, rec)
    name = villages.first_name(village_id, actor_id, "The leader")
    await _decision(village_id, pid, "undone", f"{name} tapped Undo: rev {restored_from}'s app is back (as rev {cur + 1}).", "asked_human", cur + 1,
                    [{"kind": "member", "id": actor_id}])
    await services.ledger(village_id, f"prop:{pid}", "refused", f"Proposal · {p['title']['en']}", result=f"undone by {name}", role="Builder")
    return {**copy.deepcopy(p), "undone": rec["undone"]}


# ---- WS / app action seam (services.handle_action -> here) -----------------------------------------
async def handle_action(village_id: str, name: str, request: dict[str, Any]) -> dict[str, Any]:
    req_id = request.get("req_id")
    pid = request.get("arg") or (request.get("payload") or {}).get("proposal_id")
    try:
        actor = authorize(village_id, request.get("member_id"))
        p = await (approve(village_id, pid, actor) if name == "approve_proposal" else reject(village_id, pid, actor))
        return {"type": "result", "req_id": req_id, "ok": True, "decision": {"decision": "allow", "data": {"proposal_id": pid, "status": p["status"]}}}
    except ProposalError as exc:
        return {"type": "result", "req_id": req_id, "ok": False, "error": exc.detail}
