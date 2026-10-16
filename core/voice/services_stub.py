from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "contracts" / "fixtures" / "scam_call_tool_requests.json"


class FixtureVoiceServices:
    def __init__(self) -> None:
        self.fixture = json.loads(FIXTURE_PATH.read_text())
        self.by_variant: dict[str, dict[tuple[str, str | None], dict[str, Any]]] = {}
        self.default: dict[tuple[str, str | None], dict[str, Any]] = {}
        for variant_name, variant in self.fixture["variants"].items():
            variant_map: dict[tuple[str, str | None], dict[str, Any]] = {}
            for exchange in variant["exchanges"]:
                request = exchange["request"]
                key = (exchange["tool"], request.get("tool_call_id"))
                variant_map[key] = exchange["response"]
                self.default.setdefault(key, exchange["response"])
            self.by_variant[variant_name] = variant_map

    async def handle_voice_tool(
        self,
        tool_name: str,
        body: dict[str, Any],
        *,
        variant: str | None = None,
    ) -> dict[str, Any]:
        key = (tool_name, body.get("tool_call_id"))
        if variant and key in self.by_variant.get(variant, {}):
            return self.by_variant[variant][key]
        if key in self.default:
            return self.default[key]
        if tool_name == "report_money_request":
            return self.default[("report_money_request", "toolu_01")]
        raise LookupError(f"no fixture response for {tool_name}")


fixture_services = FixtureVoiceServices()

