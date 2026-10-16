"""Rounds endpoints + scheduler hook. Core mounts `router` and `admin_router`, and may call
`on_reset(village_id)` from reset_demo and `RoundsScheduler(...).start()` in lifespan.

  POST /villages/{id}/rounds/run   (X-Admin-Key) -> counts + rows
  GET  /villages/{id}/rounds/latest
  POST /admin/rounds/run           (X-Admin-Key) -> runs the demo village (or body.village)
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from core import village as village_reg
from core.settings import ROOT, get_settings
from core.watcher import rounds as R

router = APIRouter(prefix="/villages/{village_id}/rounds", tags=["watcher"])
admin_router = APIRouter(prefix="/admin/rounds", tags=["watcher"])
LATEST: dict[str, dict[str, Any]] = {}
VAR = ROOT / "var" / "watcher"


class _CoreChat:
    async def post(self, village, text, *, to, refs):
        from core import services
        return await services.post_message(village, author="village", kind="nudge", text=f"@{to} {text}",
                                           refs=refs or [{"kind": "member", "id": to}],
                                           source={"kind": "system", "ref": "evolve"})


def _evals_port():
    try:  # evals lane owns these; absent on this branch -> None (step skipped / local fallback)
        from evals import rounds_port  # type: ignore
        return rounds_port
    except Exception:  # noqa: BLE001
        return None


def default_deps() -> dict[str, Any]:
    from core.clock import clock
    from core.db import db

    async def write_decision(row):
        await db.create_decision(row)

    async def broadcast(village, kind, payload):
        from core import services
        await services.control(village, kind, payload)

    try:
        from core.memory.client import get_client
        memory = get_client()
    except Exception:  # noqa: BLE001
        memory = None
    return {
        "clock": clock,
        "services": R.Services(events=lambda v: [e for e in db.events if e.get("village") in (None, v)],
                               prescriptions=lambda v: db.prescriptions.get(v, [])),
        "memory": memory,
        "ports": R.Ports(dialer=R.RecordingDialer(), chat=_CoreChat(), evals=_evals_port(),
                         write_decision=write_decision, broadcast=broadcast),
        "budget": R.Budget(),
    }


def get_rounds_deps() -> dict[str, Any]:
    return default_deps()


def _check_admin(key: str) -> None:
    if key != get_settings().admin_key:
        raise HTTPException(status_code=403, detail="bad admin key")


async def run_and_store(village_id: str, deps: dict[str, Any], at: datetime | None = None) -> dict[str, Any]:
    result = await R.run_round(village_id, deps["clock"], deps["services"], deps.get("memory"),
                               deps.get("budget"), deps.get("ports"), at=at)
    LATEST[village_id] = result
    try:
        VAR.mkdir(parents=True, exist_ok=True)
        (VAR / f"latest_{village_id}.json").write_text(json.dumps(result, indent=2, default=str))
    except OSError:
        pass
    return result


@router.post("/run")
async def run(village_id: str, body: dict[str, Any] | None = Body(default=None), x_admin_key: str = Header(default=""),
              deps: dict[str, Any] = Depends(get_rounds_deps)) -> dict[str, Any]:
    _check_admin(x_admin_key)
    at = datetime.fromisoformat(body["at"]) if body and body.get("at") else None
    return await run_and_store(village_id, deps, at)


@router.get("/latest")
async def latest(village_id: str) -> dict[str, Any]:
    if village_id in LATEST:
        return LATEST[village_id]
    p = VAR / f"latest_{village_id}.json"
    if p.exists():
        return json.loads(p.read_text())
    raise HTTPException(status_code=404, detail="no round yet")


@admin_router.post("/run")
async def admin_run(body: dict[str, Any] | None = Body(default=None), x_admin_key: str = Header(default=""),
                    deps: dict[str, Any] = Depends(get_rounds_deps)) -> dict[str, Any]:
    _check_admin(x_admin_key)
    village = (body or {}).get("village") or village_reg.default_village_id()
    at = datetime.fromisoformat(body["at"]) if body and body.get("at") else None
    return await run_and_store(village, deps, at)


async def on_reset(village_id: str | None = None) -> dict[str, Any]:
    """Hook for core.fixtures.reset_demo: run tonight's round on the fresh seed."""
    village_id = village_id or village_reg.default_village_id()
    return await run_and_store(village_id, default_deps())


class RoundsScheduler:
    """Clock tick: once per village per day when the (demo) clock passes ROUNDS_AT."""

    def __init__(self, villages: list[str], deps_factory=default_deps, hour: str = R.ROUNDS_AT, interval_s: float = 30) -> None:
        self.villages, self.deps_factory, self.hour, self.interval_s = villages, deps_factory, hour, interval_s
        self.done: set[tuple[str, str]] = set()
        self._task: asyncio.Task | None = None

    async def tick(self) -> list[dict[str, Any]]:
        deps = self.deps_factory()
        now = deps["clock"].now().astimezone(R.ET)
        out = []
        if now.time() >= R._hm(self.hour):
            for v in self.villages:
                k = (v, now.date().isoformat())
                if k not in self.done:
                    self.done.add(k)
                    out.append(await run_and_store(v, deps))
        return out

    async def _loop(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(self.interval_s)

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="watcher-rounds")
        return self._task

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
