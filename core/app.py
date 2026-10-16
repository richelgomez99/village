from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.fixtures import reset_demo
from core.live import start_live, stop_live
from core.routes.actions import router as actions_router
from core.routes.admin import router as admin_router
from core.routes.clock import router as clock_router
from core.routes.decisions import router as decisions_router
from core.routes.health import router as health_router
from core.routes.tools import router as tools_router
from core.routes.ws import router as ws_router
from core.settings import CONTRACT_VERSION, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.contract_version = CONTRACT_VERSION
    app.state.clock_offset_minutes = 0
    await reset_demo("v_reyes")
    await start_live()
    yield
    await stop_live()


app = FastAPI(title="Village Core", version=CONTRACT_VERSION, lifespan=lifespan)
app.include_router(health_router)
app.include_router(tools_router)
app.include_router(clock_router)
app.include_router(ws_router)
app.include_router(actions_router)
app.include_router(decisions_router)
app.include_router(admin_router)
