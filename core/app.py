from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.routes.health import router as health_router
from core.routes.tools import router as tools_router
from core.settings import CONTRACT_VERSION, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.contract_version = CONTRACT_VERSION
    app.state.clock_offset_minutes = 0
    yield


app = FastAPI(title="Village Core", version=CONTRACT_VERSION, lifespan=lifespan)
app.include_router(health_router)
app.include_router(tools_router)
