from __future__ import annotations
import logging

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


HAIKU_ROLES = {"watcher", "verifier", "explainer", "haiku", "chat", "actors"}


def _anthropic_client(settings, role: str = "default"):  # type: ignore[no-untyped-def]
    """Direct Anthropic API (Sonnet 5.5 / Haiku 5.5). A workspace-scoped key works as is; a user key needs the
    anthropic-workspace-id header, sent only when ANTHROPIC_WORKSPACE_ID is set. Set ANTHROPIC_DIRECT=off to skip."""
    if not settings.anthropic_api_key or os.environ.get("ANTHROPIC_DIRECT", "on") == "off":
        return None
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID") or getattr(settings, "anthropic_workspace_id", "") or ""
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, default_headers=headers)
    haiku = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-5-5")
    sonnet = os.environ.get("ANTHROPIC_SONNET_MODEL", "claude-sonnet-5-5")
    client.village_model = haiku if role in HAIKU_ROLES else sonnet
    client.village_provider = "anthropic"
    return client


def provider_for(role: str) -> str:
    """`VILLAGE_LLM_PROVIDER_<ROLE>` (dots -> underscores; "chat.mention" also checks ..._CHAT), else
    `VILLAGE_LLM_PROVIDER`, else "anthropic" (today's behaviour)."""
    parts = role.upper().replace("-", "_").split(".")
    for i in range(len(parts), 0, -1):
        v = os.environ.get("VILLAGE_LLM_PROVIDER_" + "_".join(parts[:i]), "").strip().lower()
        if v:
            return v
    return os.environ.get("VILLAGE_LLM_PROVIDER", "").strip().lower() or "anthropic"


def provider_explicit(role: str) -> bool:
    """True when a per-role provider line names this role (used to opt features like demo-actor lines in)."""
    parts = role.upper().replace("-", "_").split(".")
    return any(os.environ.get("VILLAGE_LLM_PROVIDER_" + "_".join(parts[:i]), "").strip() for i in range(len(parts), 0, -1))


def llm(role: str = "default"):
    settings = get_settings()
    if settings.village_llm == "off":
        return OffClient(role=role)
    if provider_for(role) == "openai":
        from core.llm_openai import openai_client

        client = openai_client(role, fallback=lambda: _anthropic_path(settings, role))
        if client is not None:
            return client
        logging.getLogger(__name__).warning("openai provider requested for role %s but OPENAI_API_KEY is unset; using anthropic", role)
    return _anthropic_path(settings, role)


def _anthropic_path(settings, role: str):  # type: ignore[no-untyped-def]
    direct = _anthropic_client(settings, role)
    if direct is not None:
        return direct
    if settings.bedrock_sonnet_model or settings.bedrock_haiku_model:
        model = (settings.bedrock_haiku_model or settings.bedrock_sonnet_model) if role in HAIKU_ROLES else (settings.bedrock_sonnet_model or settings.bedrock_haiku_model)
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"
        try:
            try:
                client = anthropic.AnthropicBedrockMantle(aws_region=region)
            except TypeError:  # test doubles without kwargs
                client = anthropic.AnthropicBedrockMantle()
        except Exception as exc:  # never let a client-construction error take down a request
            logging.getLogger(__name__).warning("bedrock client unavailable: %s", exc)
            direct = _anthropic_client(settings)
            return direct if direct is not None else OffClient(role=role)
        client.village_model = model
        client.village_provider = "bedrock"
        return client
    return OffClient(role=role)


STATUS_ROLES = ("chat", "chat.mention", "actors", "builder", "sonnet", "haiku", "watcher", "verifier")


def llm_status() -> dict:
    """Top-level provider/model is the default ("health") route; `roles` lists provider+model per role."""
    def one(role: str) -> dict[str, str]:
        try:
            client = llm(role)
        except Exception as exc:  # status must never raise
            return {"provider": "error", "model": type(exc).__name__}
        return {"provider": getattr(client, "village_provider", getattr(client, "provider", "unknown")),
                "model": getattr(client, "village_model", "off")}

    out: dict = dict(one("health"))
    out["roles"] = {r: one(r) for r in STATUS_ROLES}
    return out
