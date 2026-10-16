from fastapi import APIRouter, HTTPException

from core import services


router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/{name}")
async def dispatch_tool(name: str, body: dict) -> dict:
    try:
        return await services.handle_tool(name, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown tool: {name}") from exc
