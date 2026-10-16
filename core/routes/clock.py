from datetime import datetime

from fastapi import APIRouter, Request

from core import village as villages
from core.clock import clock
from core.scheduler import tick
from core.ws_hub import hub


router = APIRouter(prefix="/clock", tags=["clock"])


@router.post("/warp")
async def warp(body: dict, request: Request) -> dict:
    target = datetime.fromisoformat(body["to"]) if body.get("to") else None
    offset = clock.warp(minutes=body.get("minutes"), to=target, reset=body.get("reset", False))
    tick_result = await tick()
    request.app.state.clock_offset_minutes = offset
    payload = {"offset_minutes": offset, "now": clock.now().isoformat(), "tick": tick_result}
    for village_id in {c.village for c in hub.clients} | {villages.default_village_id()}:
        await hub.control(village_id, "clock", {"now": payload["now"], "offset_minutes": offset})
    return payload
