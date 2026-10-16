"""App action `ask_proposal_other {proposal_id, member_id}` (core-glue 2): a leader looking at an Evolve
proposal asks another member's opinion. Core posts a Village chat message to that member and marks the
proposal `asked_other` (an extra field surfaced through `proposal:<id>`; the proposal status is unchanged)."""
from __future__ import annotations

from typing import Any

from core import village as villages
from core.clock import clock


def _text(title: Any) -> str:
    if isinstance(title, dict):
        return str(title.get("en") or next(iter(title.values()), ""))
    return str(title or "")


async def ask_other(village_id: str, request: dict[str, Any]) -> dict[str, Any]:
    from core import services
    from core.evolve.proposals import ProposalError, get_record

    req_id = request.get("req_id")
    payload = {**(request.get("payload") or {}), **{k: v for k, v in request.items() if k in ("proposal_id",)}}
    pid = payload.get("proposal_id") or request.get("arg")
    target = payload.get("member_id")
    actor = request.get("member_id")

    def fail(error: str) -> dict[str, Any]:
        return {"type": "result", "req_id": req_id, "ok": False, "error": error}

    if not pid or not target:
        return fail("proposal_id and member_id required")
    if not villages.person(village_id, target):
        return fail("unknown member")
    try:
        rec = get_record(village_id, pid)
    except ProposalError:
        return fail("unknown proposal")
    proposal = rec["proposal"]
    if proposal.get("allow_ask_other") is False:
        return fail("this proposal can't be passed on")
    who = villages.first_name(village_id, actor, "Someone")
    title = _text(proposal.get("title"))
    message = await services.post_message(
        village_id, author="village", kind="proposal",
        text=f"{villages.first_name(village_id, target)}, {who} would like your view before saying yes: {title}"[:2000],
        refs=[pid, target], source={"kind": "app", "ref": actor or "village"},
    )
    proposal["asked_other"] = {"member_id": target, "by": actor, "at": clock.now().isoformat(), "message_id": message["id"]}
    return {"type": "result", "req_id": req_id, "ok": True,
            "decision": {"decision": "allow", "data": {"proposal_id": pid, "asked": target, "message_id": message["id"]}}}
