from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

from core.settings import CONTRACT_VERSION, get_settings


router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    settings = get_settings()
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "now": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "clock_offset_minutes": getattr(request.app.state, "clock_offset_minutes", 0),
        "layers": settings.layers,
        "deps": {
            "surreal": "configured" if settings.surreal_db_url else "memory",
            "live": "stub",
            "llm": "off" if settings.village_llm == "off" else "configured",
        },
    }
