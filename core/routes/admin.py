from fastapi import APIRouter, Header, HTTPException

from core import village as villages
from core.db import db
from core.fixtures import FIXTURES, load_json, reset_demo
from core.settings import get_settings


router = APIRouter(prefix="/admin", tags=["admin"])
ALL_SCOPES = ("events_today", "verifications", "proposals", "tokens", "counters")


async def _lane_reset(village_id: str) -> dict:
    try:
        try:
            from core.evolve import proposals as _evolve_proposals
            _evolve_proposals.reset(village_id)  # D34: proposals are in-memory; the demo reset forgets them
        except Exception:
            pass
        from core.watcher.routes import on_reset
    except ImportError:
        return {}
    try:
        return {"watcher": await on_reset(village_id)}
    except Exception as exc:  # a lane reset must not block the demo reset
        return {"watcher_error": type(exc).__name__}


def drop_founding_villages() -> list[str]:
    """Full reset forgets villages created by founding (anything not in data/villages/index.json):
    builder runs/sessions/invites/specs, their specs/views in core, and their issued member tokens."""
    keep = set(villages.village_ids())
    dropped: set[str] = {v for v in db.specs if v not in keep}
    try:
        from core.builder import routes as broutes
        from core.builder.founding import RUNS, SESSIONS

        dropped |= {v for v in list(RUNS) + list(SESSIONS) if v not in keep}
        for v in dropped:
            RUNS.pop(v, None)
            SESSIONS.pop(v, None)
        for key, row in list(broutes.INVITES.items()):
            if row.get("village") not in keep:
                broutes.INVITES.pop(key, None)
        svc = broutes.services()
        for v in [v for v in getattr(svc, "specs", {}) if v not in keep]:
            dropped.add(v)
            svc.specs.pop(v, None)
    except Exception:
        pass
    for v in dropped:
        db.specs.pop(v, None)
    for key in [k for k in db.views if k[0] in dropped]:
        db.views.pop(key, None)
    from core.auth import ISSUED

    for token, (_member, village) in list(ISSUED.items()):
        if village not in keep:
            ISSUED.pop(token, None)
    return sorted(dropped)


@router.post("/demo-caller")
async def demo_caller_switch(body: dict, x_admin_key: str = Header(default=""), authorization: str | None = Header(default=None)) -> dict:
    """Stage switch for the presenter's one phone: role elder (default) | unknown (receptionist beat)."""
    from core import demo_caller
    from core.auth import resolve_token

    if x_admin_key != get_settings().admin_key and resolve_token(authorization) != "control":
        raise HTTPException(status_code=403, detail="admin key or control token required")
    try:
        role = demo_caller.set_role(str(body.get("role") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "demo_caller": role}


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
        dropped = drop_founding_villages()
        result = await reset_demo(village_id)
        return {"ok": True, "scopes": scopes or list(ALL_SCOPES), **result, "founding_dropped": dropped, **(await _lane_reset(village_id))}

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
