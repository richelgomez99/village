from fastapi import APIRouter

from core.db import db


router = APIRouter(prefix="/villages/{village_id}", tags=["villages"])


@router.get("/decisions")
async def decisions(village_id: str, limit: int = 20) -> dict:
    rows = [row for row in db.decisions if row.get("village_id") == village_id or row.get("village") == village_id]
    return {"decisions": rows[-limit:]}


@router.get("/prescriptions")
async def prescriptions(village_id: str) -> dict:
    return {"village": village_id, "prescriptions": db.prescriptions.get(village_id, [])}
