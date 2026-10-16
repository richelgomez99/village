"""Builder HTTP surface (core includes `router` via LANE_ROUTER_MODULES). Ports only: the services
object is `CoreServices` (core db + control frames) unless a test sets another with `set_services`.

POST /villages (202 + background found) · GET /villages/{id} · POST /villages/{id}/answers ·
PATCH /villages/{id}/draft · POST /villages/{id}/activate · POST /builder/auth/redeem ·
POST /villages/{id}/ask"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from . import frames
from .ask import ask as builder_ask
from .conversation import IntakeState, Question, Review, extract, merge, next_question
from .decisions import builder_decision
from .founding import RUNS, SESSIONS, BuilderRun, FoundingInput, demo_options, found, replay_input, review_patch
from .llm_port import get_llm
from .patch import PatchError, apply_ops
from .registry import kind_config
from .services_stub import MemoryServices, now_iso
from .validate import validate_spec

router = APIRouter(tags=["builder"])
DRAFT_PATHS = ("/blueprint/people/", "/views/", "/channels/", "/policies", "/printables/", "/voice_lines")
TASKS: set[asyncio.Task] = set()


class CoreServices(MemoryServices):
    """MemoryServices that also writes through to core (db.specs, db.decisions, control frames)."""

    async def store_spec(self, village_id: str, spec: dict[str, Any], status: str = "draft") -> dict[str, Any]:
        stored = await super().store_spec(village_id, spec, status)
        try:
            from core.db import db

            db.specs[village_id] = deepcopy(stored)
            views = getattr(db, "views", None)
            if isinstance(views, dict):  # role snapshots read db.views first
                for role, view in stored.get("views", {}).items():
                    views[(village_id, role)] = deepcopy(view)
        except Exception:
            pass
        return stored

    async def get_spec(self, village_id: str) -> dict[str, Any] | None:
        got = await super().get_spec(village_id)
        if got is None:
            try:
                from core.db import db

                got = deepcopy(db.specs.get(village_id)) if village_id in db.specs else None
            except Exception:
                got = None
        return got

    async def broadcast_control(self, village_id: str, frame: dict[str, Any]) -> None:
        await super().broadcast_control(village_id, frame)
        try:
            from core import services as core_services

            await core_services.control(village_id, frame["kind"], frame["payload"])
        except Exception:
            pass

    async def broadcast_patch(self, village_id: str, frame: dict[str, Any]) -> None:
        """D33: the role's draft-view patch to that role's sockets (phones + Control Room mirrors viewing
        as the role); every other socket gets a fresh snapshot (one draft rev for all)."""
        await super().broadcast_patch(village_id, frame)
        try:
            from core.ws_hub import hub, snapshot

            for client in list(hub.clients):
                if client.village != village_id:
                    continue
                try:
                    if client.role == frame["role"]:
                        await client.ws.send_json(frame)
                    else:  # other roles + Control Room: re-snapshot so every socket tracks the one draft rev
                        await client.ws.send_json(snapshot(village_id, client.role, client.member_id, view_as=client.view_as))
                except Exception:
                    hub.disconnect(client.ws)
        except Exception:
            pass

    async def push_snapshot(self, village_id: str) -> None:
        try:
            from core.ws_hub import hub, snapshot

            for client in list(hub.clients):
                if client.village == village_id:
                    try:
                        await client.ws.send_json(snapshot(village_id, client.role, client.member_id, view_as=client.view_as))
                    except Exception:
                        hub.disconnect(client.ws)
        except Exception:
            pass

    async def record_decision(self, row: dict[str, Any]) -> dict[str, Any]:
        row = await super().record_decision(row)
        try:
            from core.db import db

            await db.create_decision(deepcopy(row))
        except Exception:
            pass
        return row

    async def decisions_for(self, village_id: str, limit: int = 60) -> list[dict[str, Any]]:
        try:
            from core.db import db

            rows = [d for d in db.decisions if d.get("village_id") == village_id or d.get("village") == village_id]
            if rows:
                return deepcopy(rows[-limit:])
        except Exception:
            pass
        return await super().decisions_for(village_id, limit)

    async def events_for(self, village_id: str, kinds: list[str] | None = None, limit: int = 60) -> list[dict[str, Any]]:
        try:
            from core.db import db

            rows = [e for e in db.events if e.get("village") == village_id and (not kinds or e.get("kind") in kinds)]
            return deepcopy(rows[-limit:])
        except Exception:
            return await super().events_for(village_id, kinds, limit)


_SERVICES: Any = None
INVITES: dict[str, dict[str, Any]] = {}  # sha256(token) → {invite_id, village, member_id, redeemed_at}


def set_services(svc: Any) -> None:
    global _SERVICES
    _SERVICES = svc


def services() -> Any:
    global _SERVICES
    if _SERVICES is None:
        _SERVICES = CoreServices()
    return _SERVICES


def _spawn(coro: Any) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)


@router.post("/villages", status_code=202)
async def create_village(body: dict, request: Request, resume: int | None = None) -> dict:
    kind = body.get("kind") or "care"
    if kind not in ("care", "block"):
        raise HTTPException(422, "kind must be care or block")
    resume = resume or body.get("resume")
    replay = bool(body.get("replay") or resume)
    description = body.get("description")
    answers: list[str] = []
    if replay:
        inp, answers = replay_input(kind=kind)
        village_id = body.get("village_id") or kind_config(kind)["village_id"]
    else:
        if not description:
            raise HTTPException(422, "description required")
        inp = FoundingInput(description=description, language=body.get("language", "en"), channel=body.get("channel", "text"), kind=body.get("kind"), medications=body.get("medications"), members=body.get("members") or [])
        village_id = body.get("village_id") or f"v_{uuid.uuid4().hex[:8]}"
    llm_mode = "off" if body.get("mode") == "fixture" else body.get("llm")
    opts = demo_options(kind, llm=llm_mode, replay_delay_s=float(body.get("pace", 0)), mode="fixture" if body.get("mode") == "fixture" else "full", replay=answers or None, resume=resume, clarify_wait_s=float(body.get("clarify_wait_s", 30)), dailymed=body.get("dailymed", "live"))
    if not body.get("scripted_dialer", replay):
        opts.dialer = None  # live founding: the real Dialer (core.voice.outbound) when FOUNDER_LIVE_CALLS=1
    run = BuilderRun(village_id=village_id, trace_id=uuid.uuid4().hex, mode=opts.mode)
    RUNS[village_id] = run
    SESSIONS.pop(village_id, None)
    _spawn(found(inp, village_id=village_id, services=services(), options=opts, run=run))
    return {"village_id": village_id, "state": run.state, "trace_id": run.trace_id, "status": "draft", "resume": resume}


@router.get("/villages/{village_id}")
async def get_village(village_id: str) -> JSONResponse:
    spec = await services().get_spec(village_id)
    run = RUNS.get(village_id)
    if spec is None and run is None:
        raise HTTPException(404, "unknown village")
    body: dict[str, Any] = dict(spec or {"village_id": village_id})
    if run is not None:
        body["builder"] = run.summary()
        s = SESSIONS.get(village_id)
        q = s.question if s and s.waiting else None
        body["builder"]["question"] = q.text if isinstance(q, (Question, Review)) else None
        body["builder"]["waiting_for_answer"] = bool(s and s.waiting)
        if s and s.intake:
            body["builder"]["meter"] = s.intake.meter()
            body["builder"]["gaps"] = s.intake.gaps()
    etag = f'W/"{village_id}-{(spec or {}).get("rev", 0)}-{run.state if run else ""}-{len(run.turns) if run else 0}"'
    return JSONResponse(body, headers={"ETag": etag})


@router.post("/villages/{village_id}/answers")
async def post_answer(village_id: str, body: dict) -> dict:
    text = str(body.get("text") or body.get("answer") or "").strip()
    if not text:
        raise HTTPException(422, "text required")
    s = SESSIONS.get(village_id)
    if s is None:
        raise HTTPException(404, "no founding session")
    q = s.question
    preview: dict[str, Any] = {}
    if isinstance(q, Question) and s.intake is not None:
        st = deepcopy(s.intake)
        merge(st, extract(text, q, st))
        nxt = next_question(st)
        preview = {"meter": st.meter(), "gaps": st.gaps(), "next_question": nxt.text if isinstance(nxt, (Question, Review)) else None}
    s.answers.put_nowait(text)
    return {"accepted": True, "village_id": village_id, "answered": q.text if isinstance(q, (Question, Review)) else None, **preview}


@router.patch("/villages/{village_id}/draft")
async def patch_draft(village_id: str, body: dict) -> dict:
    svc = services()
    spec = await svc.get_spec(village_id)
    if spec is None:
        raise HTTPException(404, "no draft")
    if spec.get("village", {}).get("status") == "active":
        raise HTTPException(409, "village is active; changes go through proposals")
    if body.get("text"):
        patched, what = review_patch(spec, body["text"])
        if not what:
            raise HTTPException(422, "couldn't turn that into a change")
    else:
        ops = body.get("ops") or []
        bad = [o for o in ops if not str(o.get("path", "")).startswith(DRAFT_PATHS)]
        if bad:
            raise HTTPException(422, f"path not editable: {bad[0].get('path')}")
        try:
            patched = apply_ops(spec, ops)
        except PatchError as exc:
            raise HTTPException(422, str(exc)) from exc
        what = f"{len(ops)} ops"
    report = validate_spec(patched)
    if not report.ok:
        raise HTTPException(422, {"errors": report.errors[:8]})
    patched["rev"] = int(spec.get("rev", 1))
    stored = await svc.store_spec(village_id, patched, status="draft")
    await svc.record_decision(builder_decision(village_id, f"Draft edited: {what}", kind="note", mode="asked_human"))
    return {"village_id": village_id, "applied": what, "spec": stored}


def _qr_svg(url: str) -> str | None:
    try:
        import segno  # type: ignore

        import io

        buf = io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=4, xmldecl=False)
        return buf.getvalue().decode()
    except Exception:
        return None


@router.post("/villages/{village_id}/activate")
async def activate(village_id: str, request: Request) -> dict:
    svc = services()
    spec = await svc.get_spec(village_id)
    if spec is None:
        raise HTTPException(404, "no draft")
    if spec.get("village", {}).get("status") == "active":
        raise HTTPException(409, "already active")
    base = str(request.base_url).rstrip("/")
    invites = []
    for p in spec["blueprint"]["people"]:
        if not p.get("view"):
            continue  # phone-only: fridge card + phone line instead of an app invite
        token = secrets.token_urlsafe(18)
        invite_id = f"inv_{village_id[2:]}_{p['id'][2:]}"[:60]
        INVITES[hashlib.sha256(token.encode()).hexdigest()] = {"invite_id": invite_id, "village": village_id, "member_id": p["id"], "redeemed_at": None}
        url = f"{base}/join.html?i={token}"
        invites.append({"invite_id": invite_id, "member_id": p["id"], "name": p["name"], "role": p["view"], "url": url, "svg": _qr_svg(url), "expires_in_s": 86400})
    spec["village"]["status"] = "active"
    spec["village"]["activated_at"] = now_iso()
    now = now_iso()
    spec["invites"] = [{"id": i["invite_id"], "member_id": i["member_id"], "kind": "join", "status": "active", "created_at": now} for i in invites]
    report = validate_spec(spec)
    if not report.ok:  # contract shape of invites differs → keep ids out of the spec
        spec.pop("invites", None)
    await svc.store_spec(village_id, spec, status="active")
    phone_only = [p["name"].split()[0] for p in spec["blueprint"]["people"] if not p.get("view")]
    await svc.record_decision(builder_decision(village_id, f"village_activated: {len(invites)} invites ({', '.join(i['name'].split()[0] for i in invites)}). Phone-only: {', '.join(phone_only) or 'none'} (fridge card + phone line).", kind="note", mode="asked_human"))
    await svc.broadcast_control(village_id, frames.reasoning(village_id, f"Invites sent: {len(invites)}", "decision", mode="asked_human"))
    return {"village_id": village_id, "status": "active", "invites": invites}


@router.post("/builder/auth/redeem")
async def redeem(body: dict) -> dict:
    """Redeems a builder-minted invite (hashed at rest). Core's /auth/redeem can delegate here."""
    token = str(body.get("invite") or "")
    row = INVITES.get(hashlib.sha256(token.encode()).hexdigest())
    if row is None:
        raise HTTPException(404, "unknown invite")
    if row["redeemed_at"]:
        raise HTTPException(409, "invite already used")
    row["redeemed_at"] = now_iso()
    svc = services()
    spec = await svc.get_spec(row["village"])
    for inv in (spec or {}).get("invites", []):
        if inv["id"] == row["invite_id"]:
            inv["status"], inv["redeemed_at"] = "redeemed", row["redeemed_at"]
    consent = body.get("consent") or {}
    if spec is not None and "ai_calls" in consent:
        for p in spec["blueprint"]["people"]:
            if p["id"] == row["member_id"]:
                p["consent"]["ai_calls"] = bool(consent["ai_calls"])
                p["consent"]["recorded_on"] = now_iso()[:10]
                p["consent"]["recorded_by"] = f"join screen ({consent.get('text_version', 'join_v1')})"
        await svc.store_spec(row["village"], spec, status=spec["village"].get("status", "active"))
    member_token = f"mt_{row['member_id'][2:]}_{secrets.token_urlsafe(9)}"
    consent_event = {"kind": "consent", "village": row["village"], "payload": {"member_id": row["member_id"], "ai_calls": consent.get("ai_calls"), "text_version": consent.get("text_version", "join_v1")}, "source": {"kind": "app", "ref": row["member_id"]}, "at": now_iso()}
    return {"member_id": row["member_id"], "village": row["village"], "member_token": member_token, "consent_event": consent_event}


@router.post("/villages/{village_id}/ask")
async def ask_route(village_id: str, body: dict) -> dict:
    question = str(body.get("question") or "").strip()
    if not question:
        raise HTTPException(422, "question required")
    llm = get_llm(body.get("llm"), "sonnet") if body.get("llm") != "off" else None
    res = await builder_ask(village_id, question, services=services(), llm=llm, lang=body.get("lang", "en"), channel=body.get("channel", "http"))
    return res.as_dict()


# ---- Village as a chat participant (operator test 13:30): every member message is classified -----------
_PARTICIPANT_TASKS: set[asyncio.Task] = set()


def install_chat_participant() -> bool:
    """Wraps core.services.post_member_message (no core edit): messages that don't mention @Village (core
    already answers those through `core.builder.ask`) go to chat_intent.participant, which decides whether
    Village speaks (need → rota-grounded answer or swap proposal; why → cited answer; change → proposal;
    chit_chat → silence)."""
    try:
        from core import services as core_services
    except Exception:
        return False
    original = core_services.post_member_message
    if getattr(original, "_village_participant", False):
        return True

    async def post_member_message(village_id: str, member_id: str, text: str, **kw: Any) -> dict[str, Any]:
        result = await original(village_id, member_id, text, **kw)
        message = result.get("message") or {}
        if result.get("routed") == "none" and message.get("author") not in (None, "village", "system"):
            from .chat_intent import participant

            async def run() -> None:
                try:
                    out = await participant(village_id, message, llm=get_llm(None, "haiku"))
                    if out:
                        result["participant"] = out.get("kind")
                except Exception:
                    import logging

                    logging.getLogger("village.builder").exception("chat participant failed")

            task = asyncio.get_running_loop().create_task(run())
            _PARTICIPANT_TASKS.add(task)
            task.add_done_callback(_PARTICIPANT_TASKS.discard)
            try:
                core_services._CHAT_TASKS.add(task)  # drain_chat() waits for it too
                task.add_done_callback(core_services._CHAT_TASKS.discard)
            except Exception:
                pass
        return result

    post_member_message._village_participant = True  # type: ignore[attr-defined]
    core_services.post_member_message = post_member_message
    return True


install_chat_participant()


# ---- D39 asks + D38 demo actors ------------------------------------------------------------------------
@router.post("/villages/{village_id}/asks/{ask_id}/answer")
async def answer_ask_route(village_id: str, ask_id: str, body: dict, request: Request) -> dict:
    from .asks import answer

    member = body.get("member_id")
    try:
        from core.auth import resolve_token

        member = resolve_token(request.headers.get("authorization")) or member
    except Exception:
        pass
    try:
        ask = await answer(ask_id, str(member), str(body.get("answer", "")))
    except KeyError as exc:
        raise HTTPException(404, "unknown ask") from exc
    except PermissionError as exc:
        raise HTTPException(403, "you were not asked") from exc
    return {"ask_id": ask_id, "status": ask["status"], "answers": ask["answers"], "event_id": ask.get("event_id")}


@router.post("/admin/demo-actors")
async def demo_actors_route(body: dict, request: Request) -> dict:
    from .actors import actors, set_actors

    try:
        from core.auth import resolve_token
        from core.settings import get_settings

        ok = request.headers.get("x-admin-key") == get_settings().admin_key or resolve_token(request.headers.get("authorization")) == "control"
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(401, "admin key or control token required")
    on = body.get("on", True)
    names = body.get("actors") or []
    if on and not names:  # default: every non-leader member with an app view
        from core import village as villages

        vid = body.get("village_id") or villages.default_village_id()
        names = [p["id"] for p in villages.people(vid) if p.get("view") and p["id"] != villages.coordinator_id(vid) and p.get("role") != "care_recipient"]
    return {"actors": sorted(set_actors(names if on else []))}


def install_answer_ask_action() -> bool:
    """App action `answer_ask` {arg: "<ask_id>:yes|no"} or payload {ask_id, answer} — wraps core.services.handle_action."""
    try:
        from core import services as core_services
    except Exception:
        return False
    original = core_services.handle_action
    if getattr(original, "_village_asks", False):
        return True

    async def handle_action(village_id: str, name: str, request: dict[str, Any]) -> dict[str, Any]:
        if name != "answer_ask":
            return await original(village_id, name, request)
        from .asks import answer

        payload = request.get("payload") or {}
        arg = str(request.get("arg") or "")
        ask_id = payload.get("ask_id") or arg.split(":")[0]
        value = payload.get("answer") or (arg.split(":")[1] if ":" in arg else "")
        try:
            ask = await answer(ask_id, str(request.get("member_id")), str(value))
            return {"ok": True, "ask_id": ask_id, "status": ask["status"]}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": type(exc).__name__}

    handle_action._village_asks = True  # type: ignore[attr-defined]
    core_services.handle_action = handle_action
    return True


install_answer_ask_action()


def install_wall_clock_chat() -> bool:
    """ASKS-2 (4): live chat rows get wall-clock `at` (the demo clock may be warped); seeded rows don't pass here."""
    try:
        from core import services as core_services
    except Exception:
        return False
    original = core_services.post_message
    if getattr(original, "_village_wall_clock", False):
        return True

    async def post_message(village_id: str, **kw: Any) -> dict[str, Any]:
        from core.db import db

        from .asks import real_now

        refs = kw.get("refs") or ()
        message: dict[str, Any] = {
            "id": core_services._message_id(), "village": village_id, "author": kw["author"], "kind": kw["kind"], "text": str(kw["text"])[:2000],
            "mention": kw.get("mention"), "reply_to": kw.get("reply_to"),
            "refs": [r if isinstance(r, dict) else core_services._ref_for_id(str(r)) for r in refs][:12],
            "source": kw["source"], "at": real_now(),
        }
        for key in ("text_i18n", "routed", "trace_id"):
            if kw.get(key):
                message[key] = kw[key]
        core_services._MESSAGE_LOG.append(message)
        await db.create_message(message)
        return message

    post_message._village_wall_clock = True  # type: ignore[attr-defined]
    core_services.post_message = post_message
    return True


install_wall_clock_chat()
