from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.settings import CONTRACT_VERSION
from core.ws_hub import hub, role_for_member


router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, village: str = "v_reyes", m: str = "m_carmen") -> None:
    await ws.accept()
    member_id = m
    role = role_for_member(member_id)
    try:
        msg = await ws.receive_json()
        if msg.get("type") == "hello":
            if msg.get("contract_version") != CONTRACT_VERSION:
                await ws.send_json({"type": "error", "code": "contract_mismatch", "contract_version": CONTRACT_VERSION})
                await ws.close()
                return
            village = msg.get("village", village)
            member_id = msg.get("member_id") or msg.get("m") or member_id
            role = msg.get("role") or role_for_member(member_id)
        await hub.connect(ws, village, member_id, role)
        while True:
            incoming = await ws.receive_json()
            if incoming.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        hub.disconnect(ws)
