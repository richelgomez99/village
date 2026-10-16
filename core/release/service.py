"""Release service: the one object Core holds. Wires real adapters (Daytona, Anchor, Arize evals,
core.llm) when their keys exist, keeps the warm pool, and starts releases in the background.

Core mounts it with two lines (see LANE-REPORT `## release`):

    from core.release.routes import router as release_router
    app.include_router(release_router)
    # optional, in lifespan: await core.release.service.get_service().startup()   # pre-warm sandbox + Anchor

Tests swap adapters with `set_service(ReleaseService(daytona=FakeDaytona(), ...))`."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from core.release.pipeline import release_id, run_release
from core.release.ports import AnchorPort, Broadcast, DaytonaPort, EvalsPort, PublisherPort
from core.release.receipts import ReceiptStore
from core.release.serve import LocalPublisher

log = logging.getLogger("village.release")
ROOT = Path(__file__).resolve().parents[2]


async def _core_control(village: str, kind: str, payload: dict[str, Any]) -> None:
    from core import services  # lazy: core imports this module, not the other way round

    await services.control(village, kind, payload)


def _core_spec(village: str) -> dict[str, Any] | None:
    try:
        from core.db import db

        spec = db.specs.get(village)
        if spec and spec.get("views"):
            return spec
    except Exception:
        pass
    from core import village as village_reg  # registry: data/villages/index.json

    return json.loads(json.dumps(village_reg.fixture_spec(village))) or None


def _core_llm() -> Callable[[str], Any] | None:
    try:
        from core.llm import llm

        return llm
    except Exception:
        return None


class ReleaseService:
    def __init__(self, *, daytona: DaytonaPort | None = None, anchor: AnchorPort | None = None,
                 evals: EvalsPort | None = None, llm: Callable[[str], Any] | None = None,
                 broadcast: Broadcast | None = None, spec_for: Callable[[str], dict[str, Any] | None] | None = None,
                 publisher: PublisherPort | None = None, store: ReceiptStore | None = None) -> None:
        self.llm = llm if llm is not None else _core_llm()
        if daytona is None and os.environ.get("DAYTONA_API_KEY"):
            from core.release.daytona_svc import DaytonaBuilder

            daytona = DaytonaBuilder()
        if anchor is None and os.environ.get("ANCHORBROWSER_API_KEY"):
            from core.release.anchor_qa import AnchorQA

            anchor = AnchorQA(keep_session=False)
        if evals is None:
            from core.release.evals import ReleaseEvals

            evals = ReleaseEvals(llm=self.llm)
        self.daytona, self.anchor, self.evals = daytona, anchor, evals
        self.broadcast = broadcast or _core_control
        self.spec_for = spec_for or _core_spec
        self.publisher = publisher or LocalPublisher()
        self.store = store or ReceiptStore()
        self.tasks: dict[str, asyncio.Task[Any]] = {}
        self.warm: dict[str, Any] = {"sandbox": "miss"}

    async def startup(self) -> dict[str, Any]:
        """Pre-warm the sandbox (template + node_modules). Never raises."""
        prep = getattr(self.daytona, "prepare", None)
        if prep is None:
            return self.warm
        try:
            sb = await self.daytona.sandbox()  # type: ignore[union-attr]
            self.warm = {"sandbox": "ready", "sandbox_id": getattr(sb, "id", None), **(await prep())}
        except Exception as exc:
            self.warm = {"sandbox": "miss", "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        return self.warm

    def busy(self, village: str) -> bool:
        t = self.tasks.get(village)
        return t is not None and not t.done()

    def start(self, village: str, rev: int, *, inject: str | None = None, trigger: str = "manual",
              publish: bool = True, proposal_id: str | None = None,
              spec: dict[str, Any] | None = None, approved_by: str | None = None) -> dict[str, str]:
        """Start a release in the background. Raises LookupError (no spec), RuntimeError (busy / no builder)."""
        if self.busy(village):
            raise RuntimeError("release in progress")
        if self.daytona is None:
            raise RuntimeError("no builder configured (DAYTONA_API_KEY)")
        spec = spec or self.spec_for(village)
        if not spec:
            raise LookupError(f"no spec for {village}")
        spec = dict(spec, rev=rev)
        pipeline_trigger = {"manual": "initial", "repair": "repair"}.get(trigger, trigger)

        async def go() -> None:
            try:
                await run_release(village, spec, rev, broadcast=self.broadcast, llm=self.llm, daytona=self.daytona,
                                  anchor=self.anchor, evals=self.evals, publisher=self.publisher, store=self.store,
                                  inject=inject, trigger=pipeline_trigger, proposal_id=proposal_id, publish=publish,
                                  approved_by=approved_by)
            except Exception:
                log.exception("release %s r%s crashed", village, rev)

        self.tasks[village] = asyncio.create_task(go())
        return {"release_id": release_id(village, rev), "candidate_path": f"/v/{village}/r/{rev}/"}


_SERVICE: ReleaseService | None = None


def get_service() -> ReleaseService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ReleaseService()
    return _SERVICE


def set_service(svc: ReleaseService | None) -> None:
    global _SERVICE
    _SERVICE = svc
