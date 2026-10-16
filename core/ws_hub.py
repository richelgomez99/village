from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

from core.bindings import changed, snapshot_data
from core.db import db
from core.settings import CONTRACT_VERSION


@dataclass
class Client:
    ws: WebSocket
    village: str
    member_id: str | None
    role: str


class Hub:
    def __init__(self) -> None:
        self.clients: list[Client] = []

    async def connect(self, ws: WebSocket, village: str, member_id: str | None, role: str) -> None:
        client = Client(ws=ws, village=village, member_id=member_id, role=role)
        self.clients.append(client)
        await ws.send_json(snapshot(village, role, member_id))

    def disconnect(self, ws: WebSocket) -> None:
        self.clients = [client for client in self.clients if client.ws is not ws]

    async def broadcast_event(self, event: dict[str, Any]) -> None:
        for client in list(self.clients):
            if client.village != event.get("village"):
                continue
            await client.ws.send_json({
                "type": "event",
                "contract_version": CONTRACT_VERSION,
                "event": event,
                "data": changed(event, client.role, client.member_id),
            })

    async def control(self, village: str, kind: str, payload: dict[str, Any]) -> None:
        for client in list(self.clients):
            if client.village == village and client.role == "control":
                await client.ws.send_json({"type": "control", "kind": kind, "payload": payload})


def role_for_member(member_id: str | None) -> str:
    if member_id == "control":
        return "control"
    person = db.members.get(member_id or "")
    return person.get("view", "elder") if person else "elder"


def snapshot(village: str, role: str, member_id: str | None) -> dict[str, Any]:
    spec = db.specs.get(village, {})
    view = db.views.get((village, role), {}) if role != "control" else {"spec": spec}
    return {
        "type": "snapshot",
        "contract_version": CONTRACT_VERSION,
        "village": village,
        "role": role,
        "member_id": member_id,
        "rev": spec.get("rev", 0),
        "view": view,
        "data": snapshot_data(role, member_id),
    }


hub = Hub()
