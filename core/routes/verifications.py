from fastapi import APIRouter, HTTPException

from core import services
from core.db import db


router = APIRouter(prefix="/verifications", tags=["verification"])


@router.post("/{verification_id}/answer")
async def answer_verification(verification_id: str, body: dict) -> dict:
    row = db.verifications.get(verification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="verification not found")

    answer = body.get("verification_answer") or body.get("answer")
    if answer not in {"yes", "no", "unsure"}:
        raise HTTPException(status_code=422, detail="verification_answer must be yes, no, or unsure")

    via = body.get("via") or ("outbound_call" if body.get("call_sid") else "app_prompt")
    member_id = body.get("member_id") or row.get("claimed_member_id")
    if member_id != row.get("claimed_member_id", member_id):
        raise HTTPException(status_code=403, detail="answering member is not claimed member")

    try:
        return await services.answer_verification(
            verification_id,
            answer,
            via=via,
            member_id=member_id,
            quote=body.get("listener_quote") or body.get("quote"),
            call_sid=body.get("call_sid"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="verification not found") from exc
