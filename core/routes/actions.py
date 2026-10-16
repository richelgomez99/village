from fastapi import APIRouter

from core import services


router = APIRouter(prefix="/v/{village_id}/actions", tags=["actions"])


@router.post("/{name}")
async def action(village_id: str, name: str, body: dict) -> dict:
    request = dict(body)
    request.setdefault("village_id", village_id)
    if name == "log_dose":
        return await services.handle_tool("log_dose", request)
    return {"decision": "allow", "data": {"action": name}}
