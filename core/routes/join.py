"""Join + QR (D11): per-member app/join URLs for the Control Room and POST /auth/redeem for /join.html."""
import hashlib
import unicodedata

from fastapi import APIRouter, Header, HTTPException, Request

from core.auth import resolve_token
from core.db import db
from core.settings import get_settings

router = APIRouter(tags=["join"])


def _slug(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def member_token(member_id: str) -> str:
    first = _slug(str(db.members.get(member_id, {}).get("name", member_id)).split()[0])
    digest = hashlib.sha256(f"{get_settings().admin_key}:{member_id}".encode()).hexdigest()[:16]
    return f"mt_{first}_{digest}"


def invite_token(member_id: str) -> str:
    first = _slug(str(db.members.get(member_id, {}).get("name", member_id)).split()[0])
    digest = hashlib.sha256(f"invite:{get_settings().admin_key}:{member_id}".encode()).hexdigest()[:12]
    return f"inv_{first}_{digest}"


def _member_for_invite(invite: str) -> str | None:
    for member_id in db.members:
        if invite in {invite_token(member_id), member_id}:
            return member_id
    if invite.startswith("inv_"):
        return resolve_token("mt_" + invite[4:])
    return resolve_token(invite)


@router.get("/villages/{village_id}/qr")
async def qr(village_id: str, request: Request, kind: str = "app", member: str | None = None, format: str = "json",
             authorization: str | None = Header(default=None), t: str | None = None) -> list[dict]:
    if resolve_token(authorization) != "control" and resolve_token(t) != "control":
        raise HTTPException(status_code=401, detail="control token required")
    base = str(request.base_url).rstrip("/")
    rows = []
    for member_id, person in db.members.items():
        if person.get("village", village_id) != village_id or (member and member != member_id):
            continue
        if kind == "join":
            url = f"{base}/join.html?i={invite_token(member_id)}"
        else:
            url = f"{base}/?m={member_token(member_id)}"
        rows.append({"member_id": member_id, "kind": kind if kind in {"app", "join"} else "app", "url": url})
    return rows


@router.post("/auth/redeem")
async def redeem(body: dict) -> dict:
    member_id = _member_for_invite(str(body.get("invite") or ""))
    if member_id is None or member_id == "control":
        raise HTTPException(status_code=404, detail="unknown invite")
    person = dict(db.members.get(member_id, {}))
    consent = dict(person.get("consent", {}))
    if isinstance(body.get("consent"), dict) and "ai_calls" in body["consent"]:
        consent["ai_calls"] = bool(body["consent"]["ai_calls"])
    person["consent"] = consent
    phone = body.get("phone")
    if isinstance(phone, str) and phone.startswith("+") and phone[1:].isdigit():
        person["phone"] = phone  # the judge playing a verifier gets that member's verification call (D11)
    await db.upsert_record("member", member_id, person)
    token = member_token(member_id)
    return {"member_id": member_id, "member_token": token, "app_url": f"./?m={token}", "role": person.get("view")}
