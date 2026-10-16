from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "contracts" / "fixtures" / "scam_call_tool_requests.json"


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text())


def _tool_key(exchange: dict[str, Any]) -> tuple[str, str, str | None]:
    request = exchange["request"]
    return (
        exchange["tool"],
        request["conversation_id"],
        request.get("tool_call_id"),
    )


def _seconds_between(start: str, end: str) -> float:
    started = datetime.fromisoformat(start)
    ended = datetime.fromisoformat(end)
    return max((ended - started).total_seconds(), 0)


class FixtureStore:
    def __init__(self) -> None:
        self.fixture = _load_fixture()
        self.exchanges: dict[tuple[str, str, str | None], dict[str, Any]] = {}
        self.variant_exchanges: dict[str, dict[tuple[str, str, str | None], dict[str, Any]]] = {}
        self.answers: dict[str, dict[str, Any]] = {}
        for variant_name, variant in self.fixture["variants"].items():
            variant_map: dict[tuple[str, str, str | None], dict[str, Any]] = {}
            for exchange in variant["exchanges"]:
                key = _tool_key(exchange)
                variant_map[key] = exchange
                self.exchanges.setdefault(key, exchange)
            self.variant_exchanges[variant_name] = variant_map
            for answer in variant.get("answers", []):
                body = answer.get("body", answer)
                verification_id = answer.get("verification_id") or body.get("verification_id") or "ver_1016_01"
                self.answers[verification_id] = answer

    def match_exchange(self, tool: str, body: dict[str, Any], variant: str | None = None) -> dict[str, Any]:
        key = (tool, body.get("conversation_id"), body.get("tool_call_id"))
        if variant:
            variant_map = self.variant_exchanges.get(variant)
            if variant_map and key in variant_map:
                return variant_map[key]

        if key in self.exchanges:
            return self.exchanges[key]

        fallback = (
            tool,
            body.get("conversation_id"),
            body.get("call_secs"),
            body.get("verification_id"),
        )
        for exchange in self.exchanges.values():
            request = exchange["request"]
            candidate = (
                exchange["tool"],
                request.get("conversation_id"),
                request.get("call_secs"),
                request.get("verification_id"),
            )
            if candidate == fallback:
                return exchange

        raise KeyError(key)


store = FixtureStore()
app = FastAPI(title="Village voice mock core")


@app.post("/tools/{tool_name}")
async def tool(tool_name: str, request: Request) -> JSONResponse:
    body = await request.json()
    try:
        exchange = store.match_exchange(tool_name, body, request.headers.get("X-Village-Variant"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"fixture exchange not found: {exc}") from exc

    if tool_name == "await_verification":
        delay = _seconds_between(exchange["at"], exchange["returned_at"])
        if delay:
            await asyncio.sleep(delay)

    return JSONResponse(exchange["response"], status_code=exchange.get("http_status", 200))


@app.post("/verifications/{verification_id}/answer")
async def answer_verification(verification_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    answer = store.answers.get(verification_id)
    if answer is not None:
        return answer.get("response", answer.get("verification_after", {"ok": True, "body": body}))
    return {
        "id": verification_id,
        "state": "confirmed" if body.get("verification_answer") == "yes" else "denied",
        "status": "confirmed" if body.get("verification_answer") == "yes" else "denied",
        "answer": body.get("verification_answer"),
    }
