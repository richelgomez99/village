"""FastAPI router for the Fact view. Core mounts it: `app.include_router(core.memory.routes.router)`.

Override dependencies in tests with `app.dependency_overrides[get_memory_deps] = ...`.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Header
from fastapi.responses import JSONResponse

from core.memory import views
from core.memory.client import get_client
from core.memory.views import MemoryDeps

router = APIRouter(prefix="/villages/{village_id}", tags=["memory"])


def _events(village: str) -> list[dict[str, Any]]:
    from core.db import db
    return [e for e in db.events if e.get("village") in (None, village)]


def _rx(village: str) -> list[dict[str, Any]]:
    from core.db import db
    return db.prescriptions.get(village, [])


def _now():
    from core.clock import clock
    return clock.now()


async def _write_decision(row: dict[str, Any]) -> None:
    from core.db import db
    await db.create_decision(row)


def _direct_drafts(village: str) -> list[dict[str, Any]]:
    from core.voice.institution_calls import fact_drafts
    return fact_drafts(village)


def get_memory_deps() -> MemoryDeps:
    return MemoryDeps(client=get_client(), events=_events, prescriptions=_rx, now=_now, write_decision=_write_decision,
                      extra={"drafts": _direct_drafts})


@router.get("/facts")
async def get_facts(village_id: str, subject: str | None = None, as_of: str | None = None,
                    deps: MemoryDeps = Depends(get_memory_deps)) -> dict[str, Any]:
    return await views.facts_view(deps, village_id, subject=subject, as_of=as_of)


@router.get("/facts/{entity}/{key}/history")
async def get_history(village_id: str, entity: str, key: str, deps: MemoryDeps = Depends(get_memory_deps)) -> dict[str, Any]:
    return await views.history_view(deps, village_id, entity, key)


@router.get("/uncertainties")
async def get_uncertainties(village_id: str, deps: MemoryDeps = Depends(get_memory_deps)) -> dict[str, Any]:
    return await views.uncertainties_view(deps, village_id)


@router.post("/uncertainties/{uid}/resolve")
async def post_resolve(village_id: str, uid: str, body: dict[str, Any] = Body(...),
                       x_member_id: str = Header(default=views.COORDINATOR),
                       deps: MemoryDeps = Depends(get_memory_deps)):
    if not isinstance(body.get("accepted_value"), str) or not body["accepted_value"].strip():
        return JSONResponse(status_code=422, content={"detail": "accepted_value required", "degraded": False})
    status, out = await views.resolve_view(deps, village_id, uid, body, by=x_member_id)
    return out if status == 200 else JSONResponse(status_code=status, content=out)
