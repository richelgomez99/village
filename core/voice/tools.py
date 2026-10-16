from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model, model_validator

from core import village
from core.voice.secret import require_secret

COMMON_REQUIRED = {
    "log_dose": ["conversation_id", "caller_id", "call_secs", "utterance", "confidence"],
    "report_symptom": ["conversation_id", "caller_id", "call_secs", "utterance", "description", "emergency_signals"],
    "whats_my_schedule": ["conversation_id", "caller_id", "call_secs", "utterance"],
    "get_today": ["conversation_id", "caller_id", "call_secs", "utterance"],
    "ask_family": ["conversation_id", "caller_id", "call_secs", "utterance", "to", "message", "urgency"],
    "report_money_request": ["conversation_id", "caller_id", "call_secs", "utterance", "urgency"],
    "await_verification": ["conversation_id", "caller_id", "call_secs", "utterance", "verification_id"],
    "submit_verification_answer": ["verification_id", "verification_answer"],
    "create_village": ["conversation_id", "caller_id", "call_secs", "utterance", "description", "members", "needs"],
    "answer_proposal": ["conversation_id", "caller_id", "call_secs", "utterance", "proposal_id", "answer"],
    "submit_answer": ["village_id", "text"],
    "screen_caller": ["conversation_id", "caller_id", "call_secs", "utterance", "claimed_identity"],
}

OPTIONAL_FIELDS = {
    "conversation_id",
    "caller_id",
    "call_secs",
    "utterance",
    "tool_call_id",
    "village_id",
    "slot",
    "pill_description",
    "taken_at",
    "confidence",
    "possible_duplicate",
    "description",
    "type",
    "value",
    "emergency_signals",
    "language",
    "intent",
    "to",
    "message",
    "urgency",
    "reason",
    "claimed_member",
    "claimed_identity",
    "amount",
    "currency",
    "method",
    "red_flags",
    "verification_id",
    "members",
    "needs",
    "medications_mentioned",
    "proposal_id",
    "answer",
    "verification_answer",
    "via",
    "listener_quote",
    "call_sid",
    "member_id",
    "text",
    "asks_money",
    "lang",
}

SENSITIVE_DIGITS = re.compile(r"(?<!\d)\d[\d\s-]{3,}\d(?!\d)")
TOOL_SPANS: list[dict[str, Any]] = []


class VoiceToolBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize_common(self) -> "VoiceToolBase":
        if hasattr(self, "call_secs"):
            value = getattr(self, "call_secs")
            if isinstance(value, str):
                object.__setattr__(self, "call_secs", float(value))
        if hasattr(self, "utterance"):
            object.__setattr__(self, "utterance", redact_digits(str(getattr(self, "utterance"))))
        return self


def redact_digits(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return re.sub(r"\d", "#", match.group(0))

    return SENSITIVE_DIGITS.sub(repl, text)


def _field(default_required: bool) -> tuple[type[Any], Any]:
    return (Any, Field(...) if default_required else None)


@lru_cache(maxsize=1)
def request_models() -> dict[str, type[BaseModel]]:
    models: dict[str, type[BaseModel]] = {}
    for tool_name, required in COMMON_REQUIRED.items():
        fields = {
            field_name: _field(field_name in required)
            for field_name in OPTIONAL_FIELDS
        }
        models[tool_name] = create_model(
            f"{tool_name.title().replace('_', '')}Request",
            __base__=VoiceToolBase,
            **fields,
        )
    return models


def cache_key(tool_name: str, body: dict[str, Any]) -> tuple[Any, ...]:
    if body.get("tool_call_id"):
        return (body.get("conversation_id"), body.get("tool_call_id"))
    return (body.get("conversation_id"), tool_name, body.get("call_secs"))


def load_services() -> Any:
    try:
        from core import services  # type: ignore

        return services
    except Exception:
        from core.voice.services_stub import fixture_services

        return fixture_services


def _await_say(status: str, body: dict[str, Any]) -> str:
    """Gate-owned Spanish line for an await result; names come from the village spec."""
    from core.gate.say import say as gate_say

    vid = body.get("village_id") or village.default_village_id()
    claimed_id = body.get("claimed_member_id") or village.default_verifier(vid)
    key = {"confirmed": "money_confirmed", "denied": "money_denied"}.get(status, "money_timeout")
    return gate_say(
        key,
        claimed_name=village.first_name(vid, claimed_id),
        pronoun=village.pronoun(village.person(vid, claimed_id)),
        coordinator_name=village.first_name(vid, village.coordinator_id(vid)),
        recipient_name=village.first_name(vid, village.care_recipient_id(vid)),
    )["es"]


@asynccontextmanager
async def tool_span(tool_name: str, body: dict[str, Any]):
    span = {
        "kind": "TOOL",
        "tool": tool_name,
        "session.id": f"village-{body.get('village_id') or village.default_village_id()}",
        "user.id": body.get("caller_id") or body.get("member_id") or "unknown",
        "ok": False,
    }
    TOOL_SPANS.append(span)
    try:
        yield span
        span["ok"] = True
    except Exception as exc:
        span["error"] = type(exc).__name__
        raise


class ToolHandler:
    def __init__(self, services: Any | None = None) -> None:
        self.services = services or load_services()
        self.cache: dict[tuple[Any, ...], dict[str, Any]] = {}

    async def handle(self, tool_name: str, raw_body: dict[str, Any], variant: str | None = None) -> dict[str, Any]:
        model = request_models().get(tool_name)
        if model is None:
            raise HTTPException(status_code=404, detail="unknown tool")

        try:
            body = model.model_validate(raw_body).model_dump(exclude_none=True)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        key = cache_key(tool_name, body)
        if key in self.cache:
            return self.cache[key]

        try:
            async with tool_span(tool_name, body):
                response = await self.delegate(tool_name, body, variant=variant)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="voice dependency degraded") from exc

        self.cache[key] = response
        return response

    async def delegate(self, tool_name: str, body: dict[str, Any], variant: str | None = None) -> dict[str, Any]:
        local = LOCAL_TOOLS.get(tool_name)
        if local is not None:
            return await local(body)
        if hasattr(self.services, "handle_voice_tool"):
            return await self.services.handle_voice_tool(tool_name, body, variant=variant)

        if tool_name in {"log_dose", "report_money_request"} and hasattr(self.services, "handle_tool"):
            return await self.services.handle_tool(tool_name, body)

        if tool_name == "await_verification" and hasattr(self.services, "await_verification"):
            result = await self.services.await_verification(body["verification_id"], max_wait_s=30)
            status = result.get("status", "timeout")
            say = _await_say(status, body)
            return {
                "decision": "advise_talk_to_coordinator" if status == "confirmed" else "advise_do_not_send",
                "say": say,
                "say_key": result.get("say_key") or ("money_confirmed" if status == "confirmed" else "money_timeout"),
                "rule_id": "R-MONEY-DEFAULT",
                "lang": "es",
                "data": {
                    "status": status,
                    "verification_id": result.get("verification_id", body["verification_id"]),
                    "state": result.get("state", status),
                    "answered_via": result.get("answered_via"),
                    "answered_at_secs": result.get("answered_at_secs"),
                    "incident_id": result.get("incident_id"),
                },
            }

        if tool_name == "submit_verification_answer" and hasattr(self.services, "answer_verification"):
            result = await self.services.answer_verification(
                body["verification_id"],
                body["verification_answer"],
                via=body.get("via") or "outbound_call",
                member_id=body.get("member_id") or village.default_verifier(body.get("village_id")),
                quote=body.get("listener_quote"),
                call_sid=body.get("call_sid"),
            )
            return {
                "decision": "allow",
                "say": "",
                "rule_id": "R-MONEY-VERIFY",
                "lang": "en",
                "data": {"status": result.get("status"), "verification_id": body["verification_id"]},
            }

        from core.voice.services_stub import fixture_services

        return await fixture_services.handle_voice_tool(tool_name, body, variant=variant)


# ---- D19 receptionist: screen_caller (contract in LANE-REPORT.md ## voice2; evolve lane owns the real handler) ----
SCREEN_DEFAULT_SAY = "I can't put you through right now. I'll let the family know you called."


async def screen_caller(body: dict[str, Any]) -> dict[str, Any]:
    """Default until the evolve lane lands its handler: Core services win if they implement `screen_caller`;
    otherwise a known caller id passes through and anyone else is held back (never put through unverified)."""
    services = load_services()
    if hasattr(services, "screen_caller"):
        return await services.screen_caller(body)
    vid = body.get("village_id") or village.default_village_id()
    caller = str(body.get("caller_id") or "")
    known = next((p for p in village.people(vid) if caller and p.get("phone") == caller), None)
    if known is not None and not body.get("asks_money"):
        return {
            "decision": "allow",
            "say": "",
            "rule_id": "R-NOOP",
            "lang": "en",
            "data": {"screen": "pass_through", "claimed_member_id": known["id"]},
        }
    return {
        "decision": "mark_unverified",
        "say": SCREEN_DEFAULT_SAY,
        "rule_id": "R-MONEY-UNKNOWN",
        "lang": "en",
        "data": {"screen": "refuse"},
    }


async def _create_village(body: dict[str, Any]) -> dict[str, Any]:
    from core.voice.setup_tools import create_village

    return await create_village(body)


async def _submit_answer(body: dict[str, Any]) -> dict[str, Any]:
    from core.voice.setup_tools import submit_answer

    return await submit_answer(body)


LOCAL_TOOLS: dict[str, Any] = {
    "create_village": _create_village,
    "submit_answer": _submit_answer,
    "screen_caller": lambda body: screen_caller(body),
}


def _register_handlers() -> None:
    from core.voice.handlers import HANDLERS

    LOCAL_TOOLS.update(HANDLERS)


_register_handlers()


app = FastAPI(title="Village voice tools")
handler = ToolHandler()


@app.post("/tools/{tool_name}")
async def voice_tool(
    tool_name: str,
    request: Request,
    x_village_secret: str | None = Header(default=None),
    x_village_variant: str | None = Header(default=None),
) -> dict[str, Any]:
    require_secret(x_village_secret)
    return await handler.handle(tool_name, await request.json(), variant=x_village_variant)
