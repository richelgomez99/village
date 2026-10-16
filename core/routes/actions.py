from fastapi import APIRouter

from core import services


router = APIRouter(prefix="/v/{village_id}/actions", tags=["actions"])


@router.post("/{name}")
async def action(village_id: str, name: str, body: dict) -> dict:
    return await services.handle_action(village_id, name, body)
