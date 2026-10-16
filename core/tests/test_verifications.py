from core.clock import clock
from core.db import db
from core.fixtures import reset_demo
from core import services


async def test_start_verification_persists_versioned_row() -> None:
    await reset_demo("v_reyes")
    now = clock.now().isoformat()
    result = await services.start_verification(
        "v_reyes",
        {
            "village": "v_reyes",
            "kind": "money_request",
            "payload": {
                "subject": "m_carmen",
                "claimed_member_id": "m_marco",
                "claimed_identity": "Marco",
                "amount": 2000,
                "currency": "USD",
                "method": "unknown",
                "urgency": "now",
                "utterance": "needs money",
                "deadline": "2026-10-16T14:02:54-04:00",
            },
            "actor": "m_carmen",
            "source": {"kind": "call", "ref": "conv_verification", "secs": 9},
            "at": now,
        },
        idempotency_key="conv_verification:tool_1",
    )
    assert result["status"] == "pending"
    row = db.verifications[result["verification_id"]]
    assert row["version"] == 0
    assert row["state"] == "pending"


async def test_answer_verification_uses_cas() -> None:
    await db.upsert_verification({
        "id": "ver_cas",
        "village": "v_reyes",
        "claimed_member_id": "m_marco",
        "state": "pending",
        "status": "pending",
        "answers": [],
        "version": 0,
    })
    first = await services.answer_verification("ver_cas", "no", via="app_prompt", member_id="m_marco")
    second = await services.answer_verification("ver_cas", "yes", via="app_prompt", member_id="m_marco")
    assert first["outcome"] == "applied"
    assert second["outcome"] == "ignored"
    assert db.verifications["ver_cas"]["version"] == 1
