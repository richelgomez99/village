from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.voice.tools import ToolHandler, app, handler
from core.voice.services_stub import fixture_services

FIXTURE = json.loads((ROOT / "contracts" / "fixtures" / "scam_call_tool_requests.json").read_text())


@pytest.fixture(autouse=True)
def reset_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VILLAGE_SECRET", "test-secret")
    handler.services = fixture_services
    handler.cache.clear()


def client() -> TestClient:
    return TestClient(app)


def post_tool(c: TestClient, variant: str, exchange: dict[str, Any]) -> Any:
    return c.post(
        f"/tools/{exchange['tool']}",
        json=exchange["request"],
        headers={"X-Village-Secret": "test-secret", "X-Village-Variant": variant},
    )


@pytest.mark.parametrize("variant", ["denied", "timeout", "confirmed", "unknown_claimed", "duplicate_webhook"])
def test_replays_fixture_variants_byte_for_byte(variant: str) -> None:
    c = client()
    for exchange in FIXTURE["variants"][variant]["exchanges"]:
        response = post_tool(c, variant, exchange)
        assert response.status_code == 200
        assert response.json() == exchange["response"]


def test_duplicate_returns_cached_body() -> None:
    c = client()
    first, second = FIXTURE["variants"]["duplicate_webhook"]["exchanges"]

    response1 = post_tool(c, "duplicate_webhook", first)
    response2 = post_tool(c, "duplicate_webhook", second)

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.content == response2.content


def test_secret_is_required_when_configured() -> None:
    exchange = FIXTURE["variants"]["denied"]["exchanges"][0]
    response = client().post(f"/tools/{exchange['tool']}", json=exchange["request"])
    assert response.status_code == 401


def test_extra_field_rejected() -> None:
    exchange = FIXTURE["variants"]["denied"]["exchanges"][0]
    body = dict(exchange["request"], extra="nope")
    response = client().post(
        f"/tools/{exchange['tool']}",
        json=body,
        headers={"X-Village-Secret": "test-secret", "X-Village-Variant": "denied"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_call_secs_coerced_and_sensitive_digits_redacted() -> None:
    seen: dict[str, Any] = {}

    class Services:
        async def handle_voice_tool(self, tool_name: str, body: dict[str, Any], *, variant: str | None = None) -> dict[str, Any]:
            seen.update(body)
            return FIXTURE["variants"]["denied"]["exchanges"][0]["response"]

    local = ToolHandler(Services())
    body = dict(FIXTURE["variants"]["denied"]["exchanges"][0]["request"])
    body["utterance"] = "Mi tarjeta es 4111 1111 1111 1111 y necesita dinero"
    await local.handle("report_money_request", body)

    assert seen["call_secs"] == 9.0
    assert "4111" not in seen["utterance"]
    assert "#### #### #### ####" in seen["utterance"]


def test_degraded_dependency_returns_503() -> None:
    class Services:
        async def handle_voice_tool(self, tool_name: str, body: dict[str, Any], *, variant: str | None = None) -> dict[str, Any]:
            raise RuntimeError("down")

    old_services = handler.services
    handler.services = Services()
    try:
        exchange = FIXTURE["variants"]["denied"]["exchanges"][0]
        response = client().post(
            f"/tools/{exchange['tool']}",
            json=exchange["request"],
            headers={"X-Village-Secret": "test-secret"},
        )
    finally:
        handler.services = old_services

    assert response.status_code == 503


def test_delegates_to_core_handle_tool_when_available() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class Services:
        async def handle_tool(self, tool_name: str, body: dict[str, Any]) -> dict[str, Any]:
            calls.append((tool_name, body))
            return FIXTURE["variants"]["denied"]["exchanges"][0]["response"]

    handler.services = Services()
    exchange = FIXTURE["variants"]["denied"]["exchanges"][0]
    response = client().post(
        f"/tools/{exchange['tool']}",
        json=exchange["request"],
        headers={"X-Village-Secret": "test-secret"},
    )

    assert response.status_code == 200
    assert calls[0][0] == "report_money_request"
