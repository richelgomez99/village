from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

from core.live import live_status
from core.llm import llm_status
from core.settings import CONTRACT_VERSION, get_settings


router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    settings = get_settings()
    llm = llm_status()
    extra = {}
    try:
        from core.memory import runtime

        extra["outbox"] = runtime.health()
    except Exception:
        pass
    try:
        from core.app import LANE_ROUTERS

        extra["lanes"] = LANE_ROUTERS
    except Exception:
        pass
    return {
        **extra,
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "now": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "clock_offset_minutes": getattr(request.app.state, "clock_offset_minutes", 0),
        "layers": settings.layers,
        "demo_caller": __import__("core.demo_caller", fromlist=["role"]).role(),
        "deps": {
            "surreal": "configured" if settings.surreal_db_url else "memory",
            "live": live_status.status,
            "llm": llm["provider"],
            "llm_model": llm["model"],
            "llm_roles": llm.get("roles", {}),
        },
    }
