from fastapi import APIRouter, Header, HTTPException

from core.fixtures import reset_demo
from core.settings import get_settings


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset")
async def reset(body: dict, x_admin_key: str = Header(default="")) -> dict:
    if x_admin_key != get_settings().admin_key:
        raise HTTPException(status_code=403, detail="bad admin key")
    result = await reset_demo("v_reyes")
    return {"ok": True, "scopes": body.get("scopes", []), **result}
