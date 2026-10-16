from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.voice.outbound import ElevenLabsDialer, build_payload, member

FIXTURE = ROOT / "contracts" / "fixtures" / "scam_call_tool_requests.json"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def denied_report_request() -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text())
    return fixture["variants"]["denied"]["exchanges"][0]["request"]


async def post_fixture(core: str) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    secret = os.getenv("VILLAGE_TOOL_SECRET")
    if secret:
        headers["X-Village-Secret"] = secret
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{core.rstrip('/')}/tools/report_money_request",
            headers=headers,
            json=denied_report_request(),
        )
        response.raise_for_status()
        return response.json()


async def place_test_call() -> dict[str, Any]:
    target = os.getenv("TEST_CALL_TO")
    if not target:
        raise SystemExit("TEST_CALL_TO missing")
    marco = member("m_marco")
    if marco is None:
        raise SystemExit("m_marco missing from Reyes fixture")
    payload = build_payload(marco, "ver_1016_01")
    payload["to_number"] = target
    payload["agent_id"] = os.getenv("ELEVENLABS_CALLER_AGENT_ID") or os.getenv("ELEVENLABS_AGENT_CALLER_ID", "")
    payload["agent_phone_number_id"] = os.getenv("ELEVENLABS_PHONE_NUMBER_ID", "")
    payload["telephony_call_config"]["ringing_timeout_secs"] = 30
    return await ElevenLabsDialer().outbound_call(payload)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Village voice path without placing calls by default.")
    parser.add_argument("--core", default="http://127.0.0.1:8787")
    parser.add_argument("--call", action="store_true", help="Place a real outbound verification call to TEST_CALL_TO. Do not use until Twilio geo-permissions are fixed.")
    args = parser.parse_args()

    load_env()
    if args.call:
        result = await place_test_call()
        print(json.dumps({
            "conversation_id": result.get("conversation_id"),
            "call_sid": result.get("callSid"),
            "success": result.get("success", True),
        }, indent=2))
        return 0

    body = await post_fixture(args.core)
    print(body["say"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
