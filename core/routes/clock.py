from datetime import datetime

from fastapi import APIRouter, Request

from core.clock import clock
from core.ws_hub import hub


router = APIRouter(prefix="/clock", tags=["clock"])


@router.post("/warp")
async def warp(body: dict, request: Request) -> dict:
    target = datetime.fromisoformat(body["to"]) if body.get("to") else None
    offset = clock.warp(minutes=body.get("minutes"), to=target, reset=body.get("reset", False))
    request.app.state.clock_offset_minutes = offset
    payload = {"offset_minutes": offset, "now": clock.now().isoformat()}
    await hub.control("v_reyes", "clock", payload)
    return payload
