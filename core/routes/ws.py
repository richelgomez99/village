from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core import services
from core import village as villages
from core.auth import resolve_token
from core.db import db
from core.settings import CONTRACT_VERSION
from core.ws_hub import hub, role_for_member


router = APIRouter(tags=["ws"])


def _error(code: str, message: str) -> dict:
    return {"type": "error", "code": code, "message": message}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, village: str | None = None, m: str | None = None) -> None:
    await ws.accept()
    # D30: the village comes from the socket (?village=), else the member's village, else DEMO_VILLAGE_ID;
    # with no member the socket defaults to that village's care recipient (legacy elder default).
    member_id = (resolve_token(m) or m) if m else None
    village = village or villages.member_village(member_id if member_id != "control" else None)
    member_id = member_id or villages.care_recipient_id(village) or villages.coordinator_id(village)
    client = None
    try:
        while client is None:
            msg = await ws.receive_json()
            if msg.get("type") != "hello":
                await ws.send_json(_error("bad_message", "send hello first"))
                continue
            client = await _hello(ws, msg, village, member_id)
            if client is False:
                return
        while True:
            incoming = await ws.receive_json()
            kind = incoming.get("type")
            if kind == "ping":
                await ws.send_json({"type": "pong"})
            elif kind == "hello":
                new_client = await _hello(ws, incoming, client.village, client.viewer or client.member_id)
                if new_client is False:
                    return
                client = new_client
            elif kind in {"action", "ack"}:
                if client.view_as:
                    await ws.send_json(_error("not_allowed", "View as is read-only"))
                    continue
                if client.role == "control" and kind == "action":
                    await ws.send_json(_error("not_allowed", "control socket has no member actions"))
                    continue
                if kind == "ack":
                    result = await services.handle_ack(client.village, client.member_id, incoming)
                else:
                    body = {**incoming.get("body", {}), **({"payload": incoming["payload"]} if incoming.get("payload") else {})}
                    if incoming.get("arg") is not None:
                        body["arg"] = incoming["arg"]
                    try:
                        result = await services.handle_action(
                            client.village,
                            incoming.get("name", incoming.get("action", "")),
                            {**body, "req_id": incoming.get("req_id"), "member_id": client.member_id},
                        )
                    except KeyError:
                        result = {"type": "result", "req_id": incoming.get("req_id"), "ok": False, "error": "unknown action"}
                await ws.send_json(result)
            else:
                await ws.send_json(_error("bad_message", f"unknown frame type {kind}"))
    except WebSocketDisconnect:
        hub.disconnect(ws)


async def _hello(ws: WebSocket, msg: dict, village: str, fallback_member: str | None):
    if msg.get("contract_version") != CONTRACT_VERSION:
        await ws.send_json({**_error("contract_mismatch", f"server speaks {CONTRACT_VERSION}"), "contract_version": CONTRACT_VERSION})
        await ws.close()
        return False
    village = msg.get("village", village)
    token = msg.get("member_token") or msg.get("member_id") or msg.get("m")
    member_id = resolve_token(token) if token else fallback_member
    if member_id is None:
        member_id = token  # legacy: unknown ids keep the elder default
    role = "control" if member_id == "control" else (msg.get("role") or role_for_member(member_id))
    view_as = msg.get("view_as")
    if view_as:
        allowed = role in {"control", "coordinator"} and view_as in db.members
        if allowed:
            return await hub.connect(ws, village, view_as, role_for_member(view_as), view_as=True, viewer=member_id)
        await ws.send_json(_error("not_allowed", "view_as is only for the Control Room or the coordinator"))
    return await hub.connect(ws, village, None if role == "control" else member_id, role, viewer=member_id)
