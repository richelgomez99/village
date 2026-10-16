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
    from core.builder.patch import apply_to_copy, patch

    recipient = evidence.get("subject") or villages.care_recipient_id(village_id)
    elder_role = _role_of(spec, recipient)
    need = _need_id(spec)
    rel_en = villages.relationship_word(village_id, recipient, "en") or "them"
    ops: dict[str, list[dict[str, Any]]] = {}
    needs_served: dict[str, dict[str, list[str]]] = {}
    highlight: dict[str, list[str]] = {}
    cand = copy.deepcopy(spec)
    for role, view in spec.get("views", {}).items():
        if "receptionist" in view.get("elements", {}):
            continue
        at = _insert_at(view)
        if role == elder_role:
            lang = view.get("lang", "es")
            text = ("Village contesta primero las llamadas desconocidas. Su familia entra directo." if lang == "es"
                    else "Village answers unknown calls first. Your family rings straight through.")
            role_ops = [
                {"op": "add", "path": "/elements/receptionist", "value": {"type": "Text", "props": {"text": text, "size": "l", "tone": "ok"}}},
                {"op": "add", "path": f"/elements/s/children/{at}", "value": "receptionist"},
            ]
            served = {"receptionist": [need]}
        else:
            res = await patch(cand, role, "receptionist: Village answers unknown callers first", llm=None)
            if res.status not in {"valid", "repaired"} or not res.ops:
                log.warning("builder patch for %s: %s %s", role, res.status, res.errors[:2])
                continue
            role_ops = [dict(o) for o in res.ops]
            role_ops[0] = {"op": "add", "path": "/elements/receptionist", "value": {"type": "Text", "props": {
                "text": f"Village answers unknown calls for {rel_en} first and checks with the real person before putting them through.",
                "size": "m", "tone": "info"}}}
            served = {"receptionist": [need]}
            kids = view["elements"].get(view.get("root", "s"), {}).get("children", [])
            if len(kids) + 2 <= MAX_CHILDREN:  # a full screen (e.g. Ana's, with Proposal + chat) keeps only the card
                role_ops.append({"op": "add", "path": "/elements/screened", "value": {"type": "Timeline", "props": {
                    "title": "Calls Village screened", "bind": f"timeline:subject={recipient}", "subject": recipient,
                    "event_kinds": ["money_request", "verification", "incident"], "show_provenance": True, "limit": 5}}})
                role_ops.append({"op": "add", "path": f"/elements/s/children/{at + 1}", "value": "screened"})
                served["screened"] = [need]
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
    count = evidence.get("count", 2)
    changes = [{"en": f"+ Village answers unknown callers on {rel_en}'s line first; family rings straight through",
                "es": f"+ Village contesta primero a desconocidos en la línea de {rel_es}; la familia entra directo"}]
    for role in built["ops"]:
        if role != _role_of(spec, recipient):
            changes.append({"en": f"+ “Village answers unknown calls first” card for the {role}"})
    if built["spec_ops"]:
        changes.append({"en": "+ New fridge card: family word first", "es": "+ Tarjeta nueva: la palabra de la familia primero"})
    proposal: dict[str, Any] = {
        "id": pid, "village": village_id,
        "detected_by": evidence.get("detected_by") if evidence.get("detected_by") in {"arize_eval", "memory_pattern"} else "memory_pattern",
        "title": {"en": f"Village answers unknown callers for {rel_en}", "es": f"Village contesta a desconocidos por {rel_es}"},
        "rationale": {
            "en": f"{count} calls asked {rel_en} for money in {claimed}'s name. Village will answer unknown callers first and check with the real {claimed} before the call reaches {rel_en}.",
            "es": f"{count} llamadas le pidieron dinero a {rel_es} en nombre de {claimed}. Village contestará primero a desconocidos y confirmará con {claimed} antes de pasarle la llamada.",
        },
        "changes": changes[:6],
        "evidence": list(evidence.get("evidence") or [])[:12],
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
           "evidence_meta": {k: evidence.get(k) for k in ("pattern", "count", "event_ids", "text")}}
    STORE.setdefault(village_id, {})[pid] = rec
    chosen = next((c for c in (options or {}).get("candidates", []) if c.get("chosen")), None)
    losers = [c for c in (options or {}).get("candidates", []) if not c.get("chosen")]
    why_not = " ".join(f"Not {c['name']}: {c['reason'].split(': ', 1)[-1]}" for c in losers)
    text = (f"Village proposes a change · needs your yes. {proposal['title']['en']}. {proposal['rationale']['en']} "
            + (f"{why_not} " if why_not else "") + "Nothing changes until you say yes.")
    msg = await services.post_message(
        village_id, author="village", kind="proposal", text=text[:2000],
        refs=[{"kind": "proposal", "id": pid, "label": "proposal"}] + [{"kind": "event", "id": e} for e in (evidence.get("event_ids") or [])[:3]],
        source={"kind": "system", "ref": "evolve"},
        text_i18n={"en": text[:600], "es": f"Village propone un cambio · necesita su sí. {proposal['title']['es']}. {proposal['rationale']['es']}"[:600]},
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


def _chosen_name(options: dict[str, Any] | None) -> str:
    return next((c["name"] for c in (options or {}).get("candidates", []) if c.get("chosen")), "receptionist")


async def _announce(village_id: str, rec: dict[str, Any]) -> None:
    from core import services

    await services.control(village_id, "proposal", {"proposal": copy.deepcopy(rec["proposal"])})


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
