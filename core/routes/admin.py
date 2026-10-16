from fastapi import APIRouter, Header, HTTPException

from core import village as villages
from core.db import db
from core.fixtures import FIXTURES, load_json, reset_demo
from core.settings import get_settings


router = APIRouter(prefix="/admin", tags=["admin"])
ALL_SCOPES = ("events_today", "verifications", "proposals", "tokens", "counters")


async def _lane_reset(village_id: str) -> dict:
    try:
        from core.watcher.routes import on_reset
    except ImportError:
        return {}
    try:
        return {"watcher": await on_reset(village_id)}
    except Exception as exc:  # a lane reset must not block the demo reset
        return {"watcher_error": type(exc).__name__}


@router.post("/reset")
async def reset(body: dict | None = None, x_admin_key: str = Header(default="")) -> dict:
    """Demo reset. No scopes = full reset_demo. Scopes: events_today, verifications, proposals, tokens, counters."""
    if x_admin_key != get_settings().admin_key:
        raise HTTPException(status_code=403, detail="bad admin key")
    village_id = (body or {}).get("village") or villages.default_village_id()
    scopes = [s for s in (body or {}).get("scopes", []) if s in ALL_SCOPES]
    unknown = [s for s in (body or {}).get("scopes", []) if s not in ALL_SCOPES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown scopes {unknown}")
    if not scopes or set(scopes) == set(ALL_SCOPES):
        result = await reset_demo(village_id)
        return {"ok": True, "scopes": scopes or list(ALL_SCOPES), **result, **(await _lane_reset(village_id))}

    from core import services

    done: dict = {}
    if "events_today" in scopes:
        seed_ids = {ev["id"] for vid in villages.village_ids() for ev in villages.seed_events(vid)}
        seed_msgs = {m["id"] for vid in villages.village_ids() for m in villages.seed_messages(vid)}
        before = len(db.events)
        db.events[:] = [ev for ev in db.events if ev["id"] in seed_ids]
        db.messages[:] = [m for m in db.messages if m["id"] in seed_msgs]
        db.decisions.clear()
        db.idem.clear()
        done["events_removed"] = before - len(db.events)
    if "verifications" in scopes:
        done["verifications_removed"] = len(db.verifications)
        db.verifications.clear()
    if "tokens" in scopes:
        spec = villages.fixture_spec(village_id)
        for person in spec["blueprint"]["people"]:
            await db.upsert_record("member", person["id"], {"village": village_id, **person})
        done["members_restored"] = len(spec["blueprint"]["people"])
    if "counters" in scopes:
        services.reset_chat_state()
        done["counters"] = "cleared"
    if "proposals" in scopes:
        done.update(await _lane_reset(village_id))
    return {"ok": True, "scopes": scopes, **done}
