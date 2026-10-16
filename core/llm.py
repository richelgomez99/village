from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import anthropic

from core.settings import get_settings


class LLMOff(RuntimeError):
    pass


@dataclass
class OffClient:
    role: str
    provider: Literal["off"] = "off"

    @property
    def messages(self) -> "OffClient":
        return self

    def create(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise LLMOff("VILLAGE_LLM=off")


def llm(role: str = "default"):
    settings = get_settings()
    if settings.village_llm == "off":
        return OffClient(role=role)
    wants_sonnet = role not in {"watcher", "verifier", "explainer", "haiku"}
    if wants_sonnet and settings.anthropic_api_key:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        client.village_model = "claude-sonnet-5-5"
        client.village_provider = "anthropic"
        return client
    if settings.bedrock_sonnet_model or settings.bedrock_haiku_model:
        model = settings.bedrock_haiku_model if role in {"watcher", "verifier", "explainer"} else settings.bedrock_sonnet_model
        client = anthropic.AnthropicBedrockMantle()
        client.village_model = model
        client.village_provider = "bedrock"
        return client
    if settings.anthropic_api_key:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        client.village_model = "claude-sonnet-5-5"
        client.village_provider = "anthropic"
        return client
    return OffClient(role=role)


def llm_status() -> dict[str, str]:
    client = llm("health")
    return {
        "provider": getattr(client, "village_provider", getattr(client, "provider", "unknown")),
        "model": getattr(client, "village_model", "off"),
    }
