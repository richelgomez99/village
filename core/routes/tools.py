from fastapi import APIRouter, HTTPException

from core import services


router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/{name}")
async def dispatch_tool(name: str, body: dict) -> dict:
    from core.voice.lang import bilingual

    try:
        response = await services.handle_tool(name, body)
    except KeyError:
        # voice2: mom-line/setup tools services doesn't serve (ask_family, report_symptom, whats_my_schedule, get_today,
        # create_village, submit_answer) are handled by core.voice.tools; unknown names still 404 there.
        from core.voice.tools import handler

        response = await handler.handle(name, body)
    return bilingual(response, body.get("lang"), body)
