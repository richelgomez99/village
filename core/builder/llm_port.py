"""LLM port for the builder.

Every builder step talks to a `BuilderLLM`: `tool_call()` forces one tool and returns its input;
`stream_tool()` yields the tool's `partial_json` deltas. Tests use `FakeLLM` (model OFF).

Provider choice (LD-1): `VILLAGE_LLM=off` -> unavailable. If `ANTHROPIC_WORKSPACE_ID` is set the
Anthropic key is used with the `anthropic-workspace-id` header (Sonnet 5.5); otherwise Bedrock
Mantle with `BEDROCK_HAIKU_MODEL` (only `anthropic.claude-haiku-4-5` is enabled on the account).
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


class LLMUnavailable(RuntimeError):
    pass


class BuilderLLM(Protocol):
    model: str

    async def tool_call(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> dict[str, Any]: ...

    def stream_tool(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> AsyncIterator[str]: ...


def _tool_param(tool: dict[str, Any]) -> dict[str, Any]:
    return {"name": tool["name"], "description": tool.get("description", ""), "input_schema": tool["input_schema"]}


@dataclass
class AnthropicLLM:
    client: Any
    model: str
    provider: str
    usage: list[dict[str, Any]] = field(default_factory=list)

    def _system(self, system: str) -> list[dict[str, Any]]:
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    async def tool_call(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> dict[str, Any]:
        t0 = time.perf_counter()
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system(system),
            messages=messages,
            tools=[_tool_param(tool)],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        self.usage.append({"tool": tool["name"], "ms": int((time.perf_counter() - t0) * 1000), "usage": getattr(resp, "usage", None)})
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return dict(block.input)
        raise ValueError(f"model did not call {tool['name']}")

    async def stream_tool(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system(system),
            messages=messages,
            tools=[_tool_param(tool)],
            tool_choice={"type": "tool", "name": tool["name"]},
        ) as stream:
            async for event in stream:
                if getattr(event, "type", None) == "content_block_delta" and getattr(event.delta, "type", None) == "input_json_delta":
                    yield event.delta.partial_json


@dataclass
class FakeLLM:
    """Scripted LLM. `responses`: tool inputs (dict), exceptions, or ("sleep", secs, value).
    `deltas`: partial_json strings for `stream_tool`."""

    responses: list[Any] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)
    model: str = "fake"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def tool_call(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> dict[str, Any]:
        self.calls.append({"tool": tool["name"], "messages": messages})
        if not self.responses:
            raise LLMUnavailable("fake LLM has no recorded responses")
        item = self.responses.pop(0)
        if callable(item):
            item = item(tool=tool, messages=messages)
        if isinstance(item, tuple) and item and item[0] == "sleep":
            await asyncio.sleep(item[1])
            item = item[2]
        if isinstance(item, BaseException):
            raise item
        return item

    async def stream_tool(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> AsyncIterator[str]:
        self.calls.append({"tool": tool["name"], "messages": messages, "stream": True})
        for delta in self.deltas:
            await asyncio.sleep(0)
            yield delta


def llm_enabled() -> bool:
    try:
        from core.settings import get_settings

        return get_settings().village_llm != "off"
    except Exception:
        return os.getenv("VILLAGE_LLM", "off") != "off"


@dataclass
class SyncClientLLM:
    """Adapts the sync client from `core.llm.llm(role)` (Anthropic direct or Bedrock Mantle) to the
    async port: calls run in a worker thread; stream deltas cross back through an asyncio.Queue."""

    client: Any
    model: str
    provider: str

    def _kw(self, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        kw = self._base(system, messages, tool, max_tokens)
        if self.provider == "anthropic":
            kw["thinking"] = {"type": "between_tools"}  # Sonnet 5.5: no thinking before the tool call (latency)
        return kw

    def _base(self, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system + f"\n\nRespond only by calling the {tool['name']} tool, exactly once.", "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
            "tools": [_tool_param(tool)],
            # Sonnet 5.5 rejects forced tool_choice ("tool"/"any"); Bedrock Haiku 4.5 accepts it
            "tool_choice": {"type": "tool", "name": tool["name"]} if self.provider in ("bedrock", "openai") else {"type": "auto"},
        }

    async def tool_call(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> dict[str, Any]:
        resp = await asyncio.to_thread(self.client.messages.create, **self._kw(system, messages, tool, max_tokens))
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return dict(block.input)
        raise ValueError(f"model did not call {tool['name']}")

    async def stream_tool(self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        done = object()

        def worker() -> None:
            try:
                with self.client.messages.stream(**self._kw(system, messages, tool, max_tokens)) as stream:
                    for event in stream:
                        if getattr(event, "type", None) == "content_block_delta" and getattr(event.delta, "type", None) == "input_json_delta":
                            loop.call_soon_threadsafe(q.put_nowait, event.delta.partial_json)
            except Exception as exc:  # surfaced to the consumer
                loop.call_soon_threadsafe(q.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(q.put_nowait, done)

        fut = loop.run_in_executor(None, worker)
        while True:
            item = await q.get()
            if item is done:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
        await fut


def llm(role: str = "sonnet") -> BuilderLLM:
    """Every real call goes through `core.llm.llm(role)` (Sonnet 5.5 direct with the workspace key;
    Bedrock Haiku 4.5 fallback). VILLAGE_LLM=off → LLMUnavailable."""
    if not llm_enabled():
        raise LLMUnavailable("VILLAGE_LLM=off")
    _load_dotenv_aws()
    from core.llm import llm as core_llm

    client = core_llm(role)
    if getattr(client, "provider", None) == "off" or not hasattr(client, "village_model"):
        raise LLMUnavailable("core.llm returned the off client")
    return SyncClientLLM(client=client, model=client.village_model, provider=getattr(client, "village_provider", "?"))


def _load_dotenv_aws() -> None:
    """pydantic-settings reads .env into Settings only; boto-style creds must be in os.environ."""
    from .paths import ROOT

    _load_dotenv_env()
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key.startswith("AWS_") and value and key not in os.environ:
            os.environ[key] = value


def _load_dotenv_env() -> None:
    """core.llm reads ANTHROPIC_WORKSPACE_ID from os.environ; pydantic-settings doesn't export it."""
    from .paths import ROOT

    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key in ("ANTHROPIC_WORKSPACE_ID", "ANTHROPIC_SONNET_MODEL", "ANTHROPIC_HAIKU_MODEL") and value and key not in os.environ:
            os.environ[key] = value


def get_llm(llm_mode: str | None, role: str = "sonnet") -> BuilderLLM | None:
    """`llm_mode`: 'off' -> None; 'on' -> real (raises if unavailable); None -> env."""
    if llm_mode == "off":
        return None
    try:
        if llm_mode == "on":
            os.environ.setdefault("VILLAGE_LLM", "on")
            try:
                from core.settings import get_settings

                get_settings.cache_clear()
            except Exception:
                pass
        return llm(role)
    except LLMUnavailable:
        if llm_mode == "on":
            raise
        return None
