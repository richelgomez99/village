import asyncio
import importlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path as _Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.auth import resolve_token
from core.fixtures import reset_demo
from core.live import start_live, stop_live
from core.routes.actions import router as actions_router
from core.routes.admin import router as admin_router
from core.routes.clock import router as clock_router
from core.routes.decisions import router as decisions_router
from core.routes.health import router as health_router
from core.routes.join import router as join_router
from core.routes.messages import router as messages_router
from core.routes.tools import router as tools_router
from core.routes.verifications import router as verifications_router
from core.routes.villages import router as villages_router
from core.routes.ws import router as ws_router
from core.scheduler import recover, tick
from core.settings import CONTRACT_VERSION, get_settings

log = logging.getLogger("village.core")

# Lane routers: each lane ships `<module>.router`; merging a lane is one import, no app.py edit.
LANE_ROUTER_MODULES = (
    "core.builder.routes",
    "core.release.routes",
    "core.memory.routes",
    "core.watcher.routes",
)
LANE_ROUTERS: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.contract_version = CONTRACT_VERSION
    app.state.clock_offset_minutes = 0
    await reset_demo()
    memory = await _memory_start()
    await start_live()
    app.state.recovery = await recover()
    ticker = asyncio.create_task(_ticker())
    warm = asyncio.create_task(_warm_release())
    yield
    ticker.cancel()
    warm.cancel()
    if memory:
        await memory.stop()
    await stop_live()


async def _memory_start():
    """Agent Memory outbox (memory lane): mirrors ledger rows into facts. Optional; VILLAGE_MEMORY=off skips it."""
    import os

    if os.environ.get("VILLAGE_MEMORY", "on").lower() == "off":
        return None
    try:
        from core.memory import runtime
        from core.db import db
    except ImportError:
        return None
    try:
        await runtime.start(db)
        return runtime
    except Exception:
        log.exception("memory runtime failed to start")
        return None


async def _warm_release() -> None:
    """Pre-warm the release lane's Daytona sandbox without blocking boot (never raises)."""
    try:
        from core.release.service import get_service
    except ImportError:
        return
    try:
        await get_service().startup()
    except Exception:
        log.exception("release warm failed")


async def _ticker(every_s: float = 1.0) -> None:
    """Background scheduler: closes verifications at their deadline and posts the 15:00 rota nudge."""
    while True:
        await asyncio.sleep(every_s)
        try:
            await tick()
        except Exception:  # never let the ticker die
            log.exception("tick failed")


app = FastAPI(title="Village Core", version=CONTRACT_VERSION, lifespan=lifespan)


@app.middleware("http")
async def control_token_guard(request: Request, call_next):
    """Operator endpoints need the control token: release starts (release lane left them open)."""
    path = request.url.path
    if request.method == "POST" and path.startswith("/villages/") and path.rstrip("/").endswith("/releases"):
        if resolve_token(request.headers.get("authorization")) != "control":
            return JSONResponse(status_code=401, content={"detail": "control token required"})
    return await call_next(request)

for _router in (
    health_router,
    tools_router,
    clock_router,
    ws_router,
    actions_router,
    decisions_router,
    verifications_router,
    messages_router,
    join_router,
    admin_router,
    villages_router,
):
    app.include_router(_router)

for _module in LANE_ROUTER_MODULES:
    try:
        _mod = importlib.import_module(_module)
    except ImportError as _exc:
        LANE_ROUTERS[_module] = "absent"
        if not _module.startswith(str(getattr(_exc, "name", "") or "~")):
            log.warning("lane router %s failed to import: %s", _module, _exc)
        continue
    _found = [getattr(_mod, _name) for _name in ("router", "admin_router") if getattr(_mod, _name, None) is not None]
    if not _found:
        LANE_ROUTERS[_module] = "no_router"
        continue
    for _lane_router in _found:
        app.include_router(_lane_router)
    LANE_ROUTERS[_module] = "included"

# Voice lane modules ship standalone FastAPI apps; graft their webhook/outbound routes onto Core (same paths ElevenLabs is configured with).
for _vm, _prefixes in (("core.voice.init_hook", ("/hooks/",)), ("core.voice.post_call", ("/hooks/",)), ("core.voice.outbound", ("/calls/",))):
    try:
        _vmod = importlib.import_module(_vm)
    except Exception as _exc:  # pragma: no cover
        log.warning("voice module %s not grafted: %s", _vm, _exc)
        continue
    _vapp = getattr(_vmod, "app", None)
    for _route in getattr(_vapp, "routes", []):
        _path = getattr(_route, "path", "")
        if _path.startswith(_prefixes) and not any(getattr(r, "path", None) == _path for r in app.router.routes):
            app.router.routes.append(_route)
    LANE_ROUTERS[_vm] = "grafted"

# Serve the built kit (kit/dist) at / after all API routes. Vite base is './' so assets resolve relative to each entry.
_dist = _Path(__file__).resolve().parent.parent / "kit" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="kit")
