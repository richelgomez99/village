from __future__ import annotations

from core import services
from core.bindings import changed, snapshot_data
from core.db import db
from core.fixtures import reset_demo
from core.ws_hub import Client, hub


class FakeWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send_json(self, frame: dict) -> None:
        self.frames.append(frame)


async def _money_request() -> dict:
    return await services.handle_tool(
        "report_money_request",
        {
            "conversation_id": "conv_hub_money",
            "tool_call_id": "tool_hub_money",
            "call_secs": 9,
            "utterance": "Marco needs money",
            "claimed_member": "marco",
            "claimed_identity": "Marco",
            "amount": 2000,
            "currency": "USD",
            "method": "unknown",
            "urgency": "now",
        },
    )


async def test_prompt_only_goes_to_claimed_member_and_closes_on_terminal() -> None:
    await reset_demo("v_reyes")
    marco = FakeWebSocket()
    ana = FakeWebSocket()
    hub.clients = [
        Client(ws=marco, village="v_reyes", member_id="m_marco", role="helper"),
        Client(ws=ana, village="v_reyes", member_id="m_ana", role="coordinator"),
    ]
    result = await _money_request()
    verification_id = result["data"]["verification_id"]

    await hub.broadcast_verification(db.verifications[verification_id])
    assert marco.frames[-1]["type"] == "prompt"
    assert marco.frames[-1]["verification_id"] == verification_id
    assert "closed" not in marco.frames[-1]
    assert ana.frames == []

    await services.answer_verification(verification_id, "no", via="app_prompt", member_id="m_marco")
    await hub.broadcast_verification(db.verifications[verification_id])
    assert marco.frames[-1]["type"] == "prompt"
    assert marco.frames[-1]["closed"] is True

    hub.clients = []


async def test_verification_bindings_resolve_pending_and_incident_state() -> None:
    await reset_demo("v_reyes")
    result = await _money_request()
    verification_id = result["data"]["verification_id"]
    pending_event = next(
        ev
        for ev in db.events
        if ev["kind"] == "verification_pending" and ev["payload"]["verification_id"] == verification_id
    )

    data = snapshot_data("helper", "m_marco")
    assert data["verifications:pending?member=me"]["verification_id"] == verification_id
    assert data["alerts:active"][0]["verification"]["status"] == "pending"
    assert changed(pending_event, "helper", "m_marco")["verifications:pending?member=me"]["verification_id"] == verification_id

    await services.answer_verification(verification_id, "no", via="app_prompt", member_id="m_marco")
    denied_event = next(ev for ev in db.events if ev["kind"] == "verification_denied")
    incident_event = next(
        ev
        for ev in db.events
        if ev["kind"] == "incident" and ev["payload"].get("verification_id") == verification_id
    )

    denied_data = changed(denied_event, "helper", "m_marco")
    assert denied_data["verifications:pending?member=me"] is None
    assert denied_data["alerts:active"][0]["verification"]["status"] == "denied"
    incidents = changed(incident_event, "coordinator", "m_ana")["incidents:open"]
    assert any(incident["verification_id"] == verification_id for incident in incidents)
