"""Evolve routes: proposals (list / approve / reject / undo) and the demo Watcher trigger."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from core.auth import resolve_token
from core.evolve import proposals as props
from core.evolve import trigger

router = APIRouter(prefix="/villages/{village_id}", tags=["evolve"])


def _who(authorization: str | None, m: str | None) -> str | None:
    return resolve_token(authorization) or resolve_token(m)


def _err(exc: props.ProposalError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


@router.get("/proposals")
async def list_proposals(village_id: str) -> dict[str, Any]:
    return {"village": village_id, "proposals": props.list_proposals(village_id), "timings": props.TIMINGS.get(village_id, {}),
            "trigger_timings": trigger.LAST.get(village_id, {})}


@router.get("/proposals/{pid}")
async def get_proposal(village_id: str, pid: str) -> dict[str, Any]:
    try:
        rec = props.get_record(village_id, pid)
    except props.ProposalError as exc:
        raise _err(exc) from exc
    return {"proposal": rec["proposal"], "options": rec.get("options"), "voice_ops": rec.get("voice_ops"),
            "undone": rec.get("undone"), "sockets_patched": rec.get("sockets_patched")}


async def _act(village_id: str, pid: str, action: str, authorization: str | None, m: str | None, wait: bool = False) -> dict[str, Any]:
    try:
        actor = props.authorize(village_id, _who(authorization, m))
        if action == "approve":
            return {"proposal": await props.approve(village_id, pid, actor, wait=wait)}
        if action == "reject":
            return {"proposal": await props.reject(village_id, pid, actor)}
        return {"proposal": await props.undo(village_id, pid, actor)}
    except props.ProposalError as exc:
        raise _err(exc) from exc


@router.post("/proposals/{pid}/approve", status_code=202)
async def approve(village_id: str, pid: str, authorization: str | None = Header(default=None), m: str | None = Query(default=None),
                  wait: bool = Query(default=False)) -> dict[str, Any]:
    return await _act(village_id, pid, "approve", authorization, m, wait)


@router.post("/proposals/{pid}/reject")
async def reject(village_id: str, pid: str, authorization: str | None = Header(default=None), m: str | None = Query(default=None)) -> dict[str, Any]:
    return await _act(village_id, pid, "reject", authorization, m)


@router.post("/proposals/{pid}/undo")
async def undo(village_id: str, pid: str, authorization: str | None = Header(default=None), m: str | None = Query(default=None)) -> dict[str, Any]:
    return await _act(village_id, pid, "undo", authorization, m)


@router.post("/evolve/trigger")
async def evolve_trigger(village_id: str, authorization: str | None = Header(default=None), force: bool = Query(default=True)) -> dict[str, Any]:
    if resolve_token(authorization) != "control":
        raise HTTPException(status_code=401, detail="control token required")
    try:
        return await trigger.run(village_id, force=force, source="control")
    except props.ProposalError as exc:
        raise _err(exc) from exc
