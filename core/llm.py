from __future__ import annotations

import os
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


HAIKU_ROLES = {"watcher", "verifier", "explainer", "haiku"}


def _anthropic_client(settings):  # type: ignore[no-untyped-def]
    """Direct Anthropic only with a workspace id (the key is a user key: without the header the API answers 400)."""
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID") or getattr(settings, "anthropic_workspace_id", "")
    if not settings.anthropic_api_key or not workspace:
        return None
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, default_headers={"anthropic-workspace-id": workspace})
    client.village_model = "claude-sonnet-5-5"
    client.village_provider = "anthropic"
    return client


def llm(role: str = "default"):
    settings = get_settings()
    if settings.village_llm == "off":
        return OffClient(role=role)
    wants_sonnet = role not in HAIKU_ROLES
    if wants_sonnet:
        direct = _anthropic_client(settings)
        if direct is not None:
            return direct
    if settings.bedrock_sonnet_model or settings.bedrock_haiku_model:
        model = (settings.bedrock_haiku_model or settings.bedrock_sonnet_model) if role in HAIKU_ROLES else (settings.bedrock_sonnet_model or settings.bedrock_haiku_model)
        client = anthropic.AnthropicBedrockMantle()
        client.village_model = model
        client.village_provider = "bedrock"
        return client
    direct = _anthropic_client(settings)
    if direct is not None:
        return direct
    return OffClient(role=role)


def llm_status() -> dict[str, str]:
    client = llm("health")
    return {
        "provider": getattr(client, "village_provider", getattr(client, "provider", "unknown")),
        "model": getattr(client, "village_model", "off"),
    }
