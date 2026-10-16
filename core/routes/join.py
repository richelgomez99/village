"""Join + QR (D11): per-member app/join URLs for the Control Room and POST /auth/redeem for /join.html."""
import hashlib
import unicodedata

from fastapi import APIRouter, Header, HTTPException, Request

from core.auth import register_token, resolve_token
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


async def _builder_redeem(body: dict) -> dict | None:
    """Invites minted by the builder's activate (hashed at rest there). Returns None when the builder
    doesn't know the invite either; re-raises its 409 (already used)."""
    try:
        from core.builder.routes import redeem as builder_redeem
    except Exception:
        return None
    try:
        out = await builder_redeem(body)
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise
    village_id, member_id = out["village"], out["member_id"]
    spec = db.specs.get(village_id) or {}
    person = next((dict(p) for p in spec.get("blueprint", {}).get("people", []) if p.get("id") == member_id), {"id": member_id})
    phone = body.get("phone")
    if isinstance(phone, str) and phone.startswith("+") and phone[1:].isdigit():
        person["phone"] = phone  # the judge's phone is the real call target (D11)
        for p in spec.get("blueprint", {}).get("people", []):
            if p.get("id") == member_id:
                p["phone"] = phone
    existing = db.members.get(member_id)
    if existing is None or existing.get("village") == village_id:
        await db.upsert_record("member", member_id, {**(existing or {}), "village": village_id, **person})
    register_token(out["member_token"], member_id, village_id)
    if out.get("consent_event"):
        try:
            await db.create_event(out["consent_event"])
        except Exception:
            pass
    token = out["member_token"]
    return {"member_id": member_id, "member_token": token, "village": village_id,
            "app_url": f"./?m={token}&village={village_id}", "role": person.get("view"),
            **({"consent_event": out["consent_event"]} if out.get("consent_event") else {})}


@router.post("/auth/redeem")
async def redeem(body: dict) -> dict:
    member_id = _member_for_invite(str(body.get("invite") or ""))
    if member_id is None or member_id == "control":
        handed = await _builder_redeem(body)
        if handed is not None:
            return handed
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
