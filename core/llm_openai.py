"""Opt-in OpenAI provider behind `core.llm.llm(role)`.

Callers speak the Anthropic Messages shape (`client.messages.create(system=..., messages=..., tools=[{name,
description, input_schema}], tool_choice=...)` and `client.messages.stream(...)`). `OpenAIClient` accepts exactly
that, maps it to OpenAI Chat Completions (function tools), and returns Anthropic-shaped objects (`.content` blocks of
type `text` / `tool_use`, `.usage.input_tokens/.output_tokens`), so no caller changes. If the OpenAI call fails
(auth, permission, rate limit, 5xx, connection/timeout, unknown model) it logs one warning line and replays the same
request on the Anthropic path (`fallback()` -> the existing direct/Bedrock client).

Env: OPENAI_API_KEY, OPENAI_MODEL (default gpt-6-sol), OPENAI_FAST_MODEL (haiku-tier roles; default OPENAI_MODEL),
OPENAI_REASONING_EFFORT (plain completions, default low), OPENAI_TOOL_REASONING_EFFORT (tool calls, default none); "" omits."""
from __future__ import annotations

import json
import logging
import os
from types import SimpleNamespace
from typing import Any, Callable, Iterator

log = logging.getLogger("core.llm")

DEFAULT_MODEL = "gpt-6-sol"  # newest id that accepts function tools on Chat Completions (verified 2026-10-16; gpt-6.1-sol needs /v1/responses for tools)


def _model_for(role: str) -> str:
    from core.llm import HAIKU_ROLES

    main = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    if role in HAIKU_ROLES:
        return os.environ.get("OPENAI_FAST_MODEL", "").strip() or main
    return main


def openai_client(role: str, fallback: Callable[[], Any] | None = None) -> "OpenAIClient | None":
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    import openai

    return OpenAIClient(openai.OpenAI(api_key=key, max_retries=0), model=_model_for(role), role=role, fallback=fallback)


# ---- Anthropic -> OpenAI request mapping ---------------------------------------------------------------------

def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        b = b if isinstance(b, dict) else getattr(b, "__dict__", {})
        if b.get("type") == "text":
            out.append(b.get("text", ""))
    return "".join(out)


def map_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool {name, description, input_schema} -> OpenAI function tool."""
    return {"type": "function", "function": {"name": tool["name"], "description": tool.get("description", ""),
                                              "parameters": tool.get("input_schema") or {"type": "object", "properties": {}}}}


def map_tool_choice(choice: Any) -> Any:
    if not choice:
        return None
    t = choice.get("type") if isinstance(choice, dict) else str(choice)
    if t == "tool":
        return {"type": "function", "function": {"name": choice["name"]}}
    if t == "any":
        return "required"
    if t == "none":
        return "none"
    return "auto"


def map_messages(system: Any, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sys_text = _text_of(system) if system else ""
    if sys_text:
        out.append({"role": "system", "content": sys_text})
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        texts, calls, results = [], [], []
        for b in content or []:
            b = b if isinstance(b, dict) else dict(getattr(b, "__dict__", {}))
            kind = b.get("type")
            if kind == "text":
                texts.append(b.get("text", ""))
            elif kind == "tool_use":
                calls.append({"id": b.get("id"), "type": "function", "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input") or {})}})
            elif kind == "tool_result":
                results.append({"role": "tool", "tool_call_id": b.get("tool_use_id"), "content": _text_of(b.get("content")) if not isinstance(b.get("content"), str) else b.get("content")})
        if role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": "".join(texts) or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:
            out.extend(results)
            if texts or not results:
                out.append({"role": role, "content": "".join(texts)})
    return out


def map_request(model: str, kw: dict[str, Any]) -> dict[str, Any]:
    req: dict[str, Any] = {"model": model, "messages": map_messages(kw.get("system"), kw.get("messages") or [])}
    if kw.get("max_tokens"):
        # reasoning models spend completion tokens on reasoning first; leave headroom so the answer is not cut off
        req["max_completion_tokens"] = int(kw["max_tokens"]) + 1024
    # Chat Completions rejects function tools with reasoning on gpt-5.5+/gpt-6 ("use /v1/responses or set
    # reasoning_effort to 'none'"); gpt-6.1-sol has no 'none', hence the gpt-6-sol default.
    effort = (os.environ.get("OPENAI_TOOL_REASONING_EFFORT", "none") if kw.get("tools") else os.environ.get("OPENAI_REASONING_EFFORT", "low")).strip()
    if effort:
        req["reasoning_effort"] = effort
    if kw.get("tools"):
        req["tools"] = [map_tool(t) for t in kw["tools"]]
        tc = map_tool_choice(kw.get("tool_choice"))
        if tc is not None:
            req["tool_choice"] = tc
    if kw.get("timeout") is not None:
        req["timeout"] = kw["timeout"]
    return req


# ---- OpenAI -> Anthropic response mapping --------------------------------------------------------------------

def map_response(resp: Any) -> SimpleNamespace:
    choice = resp.choices[0]
    msg = choice.message
    blocks: list[SimpleNamespace] = []
    if getattr(msg, "content", None):
        blocks.append(SimpleNamespace(type="text", text=msg.content))
    for call in getattr(msg, "tool_calls", None) or []:
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append(SimpleNamespace(type="tool_use", id=call.id, name=call.function.name, input=args))
    usage = getattr(resp, "usage", None)
    stop = {"tool_calls": "tool_use", "length": "max_tokens", "stop": "end_turn"}.get(getattr(choice, "finish_reason", ""), "end_turn")
    return SimpleNamespace(content=blocks, model=getattr(resp, "model", ""), stop_reason=stop, role="assistant", type="message",
                           usage=SimpleNamespace(input_tokens=getattr(usage, "prompt_tokens", 0) or 0, output_tokens=getattr(usage, "completion_tokens", 0) or 0))


def _fallback_errors() -> tuple[type[BaseException], ...]:
    import openai

    return (openai.AuthenticationError, openai.PermissionDeniedError, openai.RateLimitError, openai.InternalServerError,
            openai.APIConnectionError, openai.APITimeoutError, openai.NotFoundError)


def _for_anthropic(fb: Any, kw: dict[str, Any]) -> dict[str, Any]:
    kw = dict(kw, model=fb.village_model)
    # Sonnet 5.5 direct rejects a forced tool_choice; Haiku / Bedrock accept it (see core.builder.llm_port)
    tc = kw.get("tool_choice") or {}
    if getattr(fb, "village_provider", "") == "anthropic" and isinstance(tc, dict) and tc.get("type") in ("tool", "any") \
            and fb.village_model == os.environ.get("ANTHROPIC_SONNET_MODEL", "claude-sonnet-5-5"):
        kw["tool_choice"] = {"type": "auto"}
    return kw


class _Messages:
    def __init__(self, owner: "OpenAIClient") -> None:
        self._o = owner

    def create(self, **kw: Any) -> Any:
        o = self._o
        try:
            return map_response(o._raw.chat.completions.create(**map_request(o.village_model, kw)))
        except _fallback_errors() as exc:
            fb = o._fallback_client(exc)
            if fb is None:
                raise
            return fb.messages.create(**_for_anthropic(fb, kw))

    def stream(self, **kw: Any) -> "_Stream":
        return _Stream(self._o, kw)


class _Stream:
    """Context manager yielding Anthropic-like stream events: `content_block_delta` with `input_json_delta`
    (tool arguments) or `text_delta` (plain text). Falls back to the Anthropic stream if OpenAI fails before
    the first event."""

    def __init__(self, owner: "OpenAIClient", kw: dict[str, Any]) -> None:
        self._o, self._kw, self._fb_cm = owner, kw, None

    def __enter__(self) -> Iterator[Any]:
        o = self._o
        try:
            req = map_request(o.village_model, self._kw)
            req["stream"] = True
            raw = o._raw.chat.completions.create(**req)
            return self._events(raw)
        except _fallback_errors() as exc:
            fb = o._fallback_client(exc)
            if fb is None:
                raise
            self._fb_cm = fb.messages.stream(**_for_anthropic(fb, self._kw))
            return self._fb_cm.__enter__()

    def __exit__(self, *exc: Any) -> Any:
        if self._fb_cm is not None:
            return self._fb_cm.__exit__(*exc)
        return False

    @staticmethod
    def _events(raw: Any) -> Iterator[Any]:
        for chunk in raw:
            for ch in getattr(chunk, "choices", None) or []:
                d = ch.delta
                if getattr(d, "content", None):
                    yield SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=d.content))
                for call in getattr(d, "tool_calls", None) or []:
                    args = getattr(getattr(call, "function", None), "arguments", None)
                    if args:
                        yield SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="input_json_delta", partial_json=args))


class OpenAIClient:
    village_provider = "openai"

    def __init__(self, raw: Any, *, model: str, role: str, fallback: Callable[[], Any] | None = None) -> None:
        self._raw = raw
        self.village_model = model
        self.village_role = role
        self._fallback = fallback
        self.messages = _Messages(self)

    def _fallback_client(self, exc: BaseException) -> Any | None:
        fb = self._fallback() if self._fallback else None
        if fb is None or not hasattr(fb, "village_model"):
            return None
        log.warning("openai %s failed for role %s (%s); falling back to %s %s", self.village_model, self.village_role,
                    type(exc).__name__, getattr(fb, "village_provider", "?"), fb.village_model)
        return fb

    # Same conveniences the builder port offers on the Anthropic path.
    def tool_call(self, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], max_tokens: int = 4096) -> dict[str, Any]:
        resp = self.messages.create(model=self.village_model, system=system, messages=messages, tools=[tool],
                                    tool_choice={"type": "tool", "name": tool["name"]}, max_tokens=max_tokens)
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use" and b.name == tool["name"]:
                return dict(b.input)
        raise ValueError(f"model did not call {tool['name']}")

    def complete(self, system: str, messages: list[dict[str, Any]], max_tokens: int = 1024) -> str:
        resp = self.messages.create(model=self.village_model, system=system, messages=messages, max_tokens=max_tokens)
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
