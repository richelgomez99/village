from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from core import services
from core.auth import resolve_token, role_of
from core.db import db


router = APIRouter(prefix="/villages/{village_id}", tags=["chat"])


def _caller(authorization: str | None, m: str | None) -> str:
    member = resolve_token(authorization) or resolve_token(m)
    if member is None:
        raise HTTPException(status_code=401, detail="bad_token")
    return member


@router.get("/messages")
async def list_messages(
    village_id: str,
    after: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    kind: str | None = None,
    authorization: str | None = Header(default=None),
    m: str | None = None,
) -> list[dict]:
    member = _caller(authorization, m)
    if member != "control" and role_of(member) == "elder":
        raise HTTPException(status_code=403, detail="elder view has no chat")
    rows = [row for row in db.messages if row.get("village") == village_id]
    if after:
        ids = [row["id"] for row in rows]
        if after in ids:
            rows = rows[ids.index(after) + 1:]
    if kind:
        rows = [row for row in rows if row.get("kind") == kind]
    return rows[-limit:]


@router.post("/messages", status_code=201)
async def create_message(
    village_id: str,
    body: dict,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    m: str | None = None,
):
    member = _caller(authorization, m)
    if member == "control" or role_of(member) == "elder":
        raise HTTPException(status_code=403, detail="only non-elder members post chat")
    text = str(body.get("text") or "").strip()
    if not text or len(text) > 2000:
        raise HTTPException(status_code=422, detail="text must be 1..2000 chars")
    result = await services.post_member_message(
        village_id,
        member,
        text,
        mention=body.get("mention"),
        reply_to=body.get("reply_to"),
        idempotency_key=idempotency_key,
    )
    return JSONResponse(status_code=201, content=result)
