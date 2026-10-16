from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.voice.mock_core import app
FIXTURE = json.loads((ROOT / "contracts" / "fixtures" / "scam_call_tool_requests.json").read_text())


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("core.voice.mock_core.asyncio.sleep", no_sleep)
    return TestClient(app)


@pytest.mark.parametrize("variant", ["denied", "timeout", "confirmed", "unknown_claimed", "duplicate_webhook"])
def test_fixture_variants_replay(client: TestClient, variant: str) -> None:
    for exchange in FIXTURE["variants"][variant]["exchanges"]:
        response = client.post(
            f"/tools/{exchange['tool']}",
            json=exchange["request"],
            headers={"X-Village-Variant": variant},
        )
        assert response.status_code == exchange.get("http_status", 200)
        assert response.json() == exchange["response"]


def test_answer_endpoint_returns_fixture_shape(client: TestClient) -> None:
    answers = FIXTURE["variants"]["confirmed"]["answers"]
    if not answers:
        pytest.skip("fixture has no explicit answer exchange")

    answer = answers[0]
    verification_id = answer.get("verification_id", "ver_1016_01")
    response = client.post(f"/verifications/{verification_id}/answer", json=answer["body"])

    assert response.status_code == 200
    assert response.json()
