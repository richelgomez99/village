from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from core import village as villages
from core.bindings import changed, snapshot_data, verification_prompt_frame
from core.clock import clock
from core.db import db
from core.settings import CONTRACT_VERSION


VILLAGE_KEYED = {"reasoning", "caption", "ledger", "blueprint"}  # control kinds whose payload schema allows `village`


@dataclass(eq=False)
class Client:
    ws: WebSocket
    village: str
    member_id: str | None
    role: str
    view_as: bool = False
    viewer: str | None = None
    prompted: set[tuple[str, bool]] = field(default_factory=set)


class Hub:
    def __init__(self) -> None:
        self.clients: list[Client] = []

    async def connect(
        self,
        ws: WebSocket,
        village: str,
        member_id: str | None,
        role: str,
        *,
        view_as: bool = False,
        viewer: str | None = None,
    ) -> Client:
        self.disconnect(ws)
        client = Client(ws=ws, village=village, member_id=member_id, role=role, view_as=view_as, viewer=viewer)
        self.clients.append(client)
        await ws.send_json(snapshot(village, role, member_id, view_as=view_as))
        await self.phones_live(village)
        return client

    def disconnect(self, ws: WebSocket) -> None:
        before = len(self.clients)
        gone = [client for client in self.clients if client.ws is ws]
        self.clients = [client for client in self.clients if client.ws is not ws]
        if len(self.clients) != before and any(c.role != "control" for c in gone):
            import asyncio

            try:
                asyncio.get_running_loop().create_task(self.phones_live(gone[0].village))
            except RuntimeError:
                pass

    def live_phone_count(self, village: str) -> int:
        return len({id(c.ws) for c in self.clients if c.village == village and c.role != "control" and not c.view_as})

    async def phones_live(self, village: str) -> None:
        await self.control(village, "counter", {"name": "phones_live", "value": self.live_phone_count(village), "label": "phones live"})

    async def _send(self, client: Client, frame: dict[str, Any]) -> None:
        try:
            await client.ws.send_json(frame)
        except Exception:
            self.disconnect(client.ws)

    async def broadcast_event(self, event: dict[str, Any]) -> None:
        for client in list(self.clients):
            if client.village != event.get("village"):
                continue
            frame: dict[str, Any] = {"type": "event", "event": event}
            data = changed(
                event,
                client.role,
                client.member_id or (villages.default_verifier(client.village) if client.role == "control" else None),
                client.village,
            )
            if data:
                frame["data"] = data
            await self._send(client, frame)

    async def control(self, village: str, kind: str, payload: dict[str, Any]) -> None:
        """Control frames go only to that village's Control Room sockets; kinds whose schema has `village`
        carry it in the payload (D30: every WS frame is village-keyed)."""
        if kind in VILLAGE_KEYED and "village" not in payload:
            payload = {**payload, "village": village}
        for client in list(self.clients):
            if client.village == village and client.role == "control":
                await self._send(client, {"type": "control", "kind": kind, "payload": payload, "at": clock.now().isoformat()})
        if kind == "counter" and payload.get("name") == "intake_covered":
            from core.founding_glue import founding_frames

            for derived_kind, derived in founding_frames(village):
                await self.control(village, derived_kind, derived)

    async def push_proposals(self, village: str, proposal: dict[str, Any] | None = None) -> None:
        """Proposal create / approve / reject / apply -> refresh proposals:pending on every socket that binds it
        (Ana's Proposal card, Control Room), as an `event` frame carrying a non-persisted spec_patch_proposed row."""
        from core.bindings import proposals_pending, view_binds

        targets = [c for c in list(self.clients) if c.village == village and c.role != "elder"
                   and ("*" in (b := view_binds(c.role, village)) or "proposals:pending" in b)]
        if not targets:
            return
        pending = proposals_pending(village)
        p = proposal or {}
        pid = p.get("id") or (pending[0]["proposal_id"] if pending else None)
        if not pid:
            return
        event = {
            "id": f"ev_{pid}_{p.get('status', 'pending')}"[:67],
            "village": village,
            "kind": "spec_patch_proposed",
            "payload": {"proposal_id": pid, "roles": sorted(p.get("ops") or {}) or ["coordinator"],
                        "detected_by": p.get("detected_by") if p.get("detected_by") in {"arize_eval", "memory_pattern"} else "memory_pattern"},
            "actor": "evolve",
            "source": {"kind": "system", "ref": "evolve"},
            "at": clock.now().isoformat(),
        }
        for client in targets:
            await self._send(client, {"type": "event", "event": event, "data": {"proposals:pending": pending}})

    async def broadcast_chat(self, message: dict[str, Any]) -> None:
        for client in list(self.clients):
            if client.village != message.get("village"):
                continue
            if client.role == "elder":
                continue
            await self._send(client, {"type": "chat", "village": message.get("village"), "message": message})

    async def broadcast_verification(self, verification: dict[str, Any]) -> None:
        claimed = verification.get("claimed_member_id") or verification.get("claimed_member")
        closed = verification.get("state") not in {"pending", "default_spoken"}
        frame = verification_prompt_frame(verification, closed=closed)
        for client in list(self.clients):
            if client.village != verification.get("village") or client.member_id != claimed:
                continue
            key = (verification["id"], closed)
            if key in client.prompted:
                continue  # one open prompt and one closed prompt per socket, however many row updates
            client.prompted.add(key)
            await self._send(client, frame)


def role_for_member(member_id: str | None) -> str:
    if member_id == "control":
        return "control"
    person = db.members.get(member_id or "")
    return person.get("view", "elder") if person else "elder"


def identity(village: str, role: str, member_id: str | None, *, view_as: bool = False) -> dict[str, Any]:
    village_row = db.villages.get(village, {})
    village_name = village_row.get("name") or db.specs.get(village, {}).get("village", {}).get("name") or village
    if role == "control" or member_id is None:
        out: dict[str, Any] = {"member_id": None, "name": "Control Room", "role": "control", "village_name": village_name}
    else:
        person = db.members.get(member_id, {})
        out = {
            "member_id": member_id,
            "name": str(person.get("name", member_id)).split()[0],
            "role": role,
            "village_name": village_name,
        }
        lang = person.get("lang")
        if lang in {"en", "es"}:
            out["lang"] = lang
    number = villages.village_number(village)
    if number:
        out["village_number"] = number
    if view_as:
        out["view_as"] = True
    return out


def snapshot(village: str, role: str, member_id: str | None, *, view_as: bool = False) -> dict[str, Any]:
    spec = db.specs.get(village, {})
    if role == "control":
        view_spec: dict[str, Any] = spec
        member_id = None
    else:
        view_spec = db.views.get((village, role)) or spec.get("views", {}).get(role, {})
    return {
        "type": "snapshot",
        "contract_version": CONTRACT_VERSION,
        "village": village,
        "role": role,
        "member_id": member_id,
        "rev": spec.get("rev", 0),
        "spec": view_spec,
        "data": snapshot_data(role, member_id, village),
        "now": clock.now().isoformat(),
        "identity": identity(village, role, member_id, view_as=view_as),
    }


hub = Hub()
