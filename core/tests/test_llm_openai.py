"""Opt-in OpenAI provider behind core.llm.llm(role): routing, schema mapping, response shape, fallback. No network."""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

import core.llm as mod
import core.llm_openai as oai
from core.settings import Settings

TOOL = {"name": "classify", "description": "Pick one.", "input_schema": {"type": "object", "properties": {"intent": {"type": "string"}}, "required": ["intent"]}}


@pytest.fixture
def env(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("VILLAGE_LLM_PROVIDER") or k.startswith("OPENAI_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANTHROPIC_DIRECT", "on")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    settings = Settings(VILLAGE_LLM="on", ANTHROPIC_API_KEY="test-anthropic", ANTHROPIC_WORKSPACE_ID="")
    monkeypatch.setattr(mod, "get_settings", lambda: settings)
    return monkeypatch


class FakeCompletions:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, []

    def create(self, **kw):
        self.calls.append(kw)
        if self.exc is not None:
            raise self.exc
        return self.result


def fake_openai(monkeypatch, completions):
    class FakeOpenAI:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(completions=completions)

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)


def tool_response(name="classify", args=None):
    call = SimpleNamespace(id="call_1", type="function", function=SimpleNamespace(name=name, arguments=json.dumps(args or {"intent": "need"})))
    msg = SimpleNamespace(content=None, tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")], model="gpt-test",
                           usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7))


def test_default_is_anthropic(env):
    env.setenv("OPENAI_API_KEY", "test-openai")
    for role in ("chat", "chat.mention", "actors", "builder", "haiku"):
        assert mod.provider_for(role) == "anthropic"
        assert mod.llm(role).village_provider == "anthropic"


def test_role_routing(env):
    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("OPENAI_MODEL", "gpt-main")
    env.setenv("OPENAI_FAST_MODEL", "gpt-fast")
    env.setenv("VILLAGE_LLM_PROVIDER_ACTORS", "openai")
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT", "openai")
    fake_openai(env, FakeCompletions())
    assert mod.llm("actors").village_provider == "openai"
    assert mod.llm("actors").village_model == "gpt-fast"  # haiku tier
    assert mod.llm("chat.mention").village_provider == "openai"  # inherits ..._CHAT
    assert mod.llm("chat.mention").village_model == "gpt-main"
    assert mod.llm("builder").village_provider == "anthropic"
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT_MENTION", "anthropic")
    assert mod.llm("chat.mention").village_provider == "anthropic"
    env.setenv("VILLAGE_LLM_PROVIDER", "openai")
    assert mod.llm("builder").village_provider == "openai"
    status = mod.llm_status()
    assert status["roles"]["actors"] == {"provider": "openai", "model": "gpt-fast"}
    assert status["roles"]["chat.mention"]["provider"] == "anthropic"


def test_openai_without_key_stays_anthropic(env):
    env.setenv("VILLAGE_LLM_PROVIDER", "openai")
    assert mod.llm("chat").village_provider == "anthropic"


def test_off_wins(env):
    env.setenv("VILLAGE_LLM_PROVIDER", "openai")
    env.setattr(mod, "get_settings", lambda: Settings(VILLAGE_LLM="off"))
    assert mod.llm("chat").provider == "off"


def test_tool_schema_and_message_mapping():
    req = oai.map_request("gpt-x", {
        "system": [{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}],
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "id": "t1", "name": "classify", "input": {"intent": "why"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "done"}, {"type": "text", "text": "next"}]},
        ],
        "tools": [TOOL], "tool_choice": {"type": "tool", "name": "classify"}, "max_tokens": 100, "thinking": {"type": "between_tools"},
    })
    assert req["tools"] == [{"type": "function", "function": {"name": "classify", "description": "Pick one.", "parameters": TOOL["input_schema"]}}]
    assert req["tool_choice"] == {"type": "function", "function": {"name": "classify"}}
    assert req["messages"][0] == {"role": "system", "content": "SYS"}
    assert req["messages"][2]["tool_calls"][0]["function"] == {"name": "classify", "arguments": json.dumps({"intent": "why"})}
    assert req["messages"][3] == {"role": "tool", "tool_call_id": "t1", "content": "done"}
    assert req["messages"][4] == {"role": "user", "content": "next"}
    assert "thinking" not in req and req["max_completion_tokens"] >= 100
    assert oai.map_tool_choice({"type": "any"}) == "required" and oai.map_tool_choice({"type": "auto"}) == "auto"


def test_response_shape_and_conveniences(env):
    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT", "openai")
    comp = FakeCompletions(tool_response())
    fake_openai(env, comp)
    client = mod.llm("chat")
    resp = client.messages.create(model=client.village_model, system="s", messages=[{"role": "user", "content": "x"}], tools=[TOOL],
                                  tool_choice={"type": "tool", "name": "classify"}, max_tokens=50)
    block = resp.content[0]
    assert (block.type, block.name, block.input) == ("tool_use", "classify", {"intent": "need"})
    assert resp.usage.input_tokens == 11 and resp.stop_reason == "tool_use"
    assert client.tool_call("s", [{"role": "user", "content": "x"}], TOOL, 50) == {"intent": "need"}


async def test_builder_port_tool_call_via_openai(env):
    from core.builder.llm_port import SyncClientLLM

    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT", "openai")
    comp = FakeCompletions(tool_response())
    fake_openai(env, comp)
    client = mod.llm("chat")
    port = SyncClientLLM(client=client, model=client.village_model, provider=client.village_provider)
    assert await port.tool_call(system="s", messages=[{"role": "user", "content": "x"}], tool=TOOL, max_tokens=50) == {"intent": "need"}
    assert comp.calls[0]["tool_choice"] == {"type": "function", "function": {"name": "classify"}}


@pytest.mark.parametrize("exc_cls,status", [(openai.AuthenticationError, 401), (openai.RateLimitError, 429), (openai.InternalServerError, 500)])
def test_fallback_to_anthropic(env, caplog, exc_cls, status):
    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT", "openai")
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    fake_openai(env, FakeCompletions(exc=exc_cls("boom", response=httpx.Response(status, request=req), body=None)))
    sent = {}

    class FakeAnthropicMessages:
        def create(self, **kw):
            sent.update(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name="classify", input={"intent": "why"})])

    class FakeAnthropic:
        def __init__(self, **kw):
            self.messages = FakeAnthropicMessages()

    env.setattr(mod.anthropic, "Anthropic", FakeAnthropic)
    client = mod.llm("chat.mention")  # sonnet tier
    with caplog.at_level(logging.WARNING, logger="core.llm"):
        resp = client.messages.create(model=client.village_model, system="s", messages=[{"role": "user", "content": "x"}], tools=[TOOL],
                                      tool_choice={"type": "tool", "name": "classify"}, max_tokens=50)
    assert resp.content[0].input == {"intent": "why"}
    assert sent["model"] == "claude-sonnet-5-5" and sent["tool_choice"] == {"type": "auto"}  # Sonnet 5.5 rejects forced
    lines = [r.getMessage() for r in caplog.records if "falling back" in r.getMessage()]
    assert len(lines) == 1 and "test-openai" not in lines[0] and exc_cls.__name__ in lines[0]


def test_bad_request_does_not_fall_back(env):
    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT", "openai")
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    fake_openai(env, FakeCompletions(exc=openai.BadRequestError("bad", response=httpx.Response(400, request=req), body=None)))
    with pytest.raises(openai.BadRequestError):
        mod.llm("chat").messages.create(system="s", messages=[{"role": "user", "content": "x"}], max_tokens=10)


def test_stream_maps_tool_deltas(env):
    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("VILLAGE_LLM_PROVIDER_CHAT", "openai")
    chunks = [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=a))]))]) for a in ('{"in', 'tent":"x"}')]
    fake_openai(env, FakeCompletions(iter(chunks)))
    with mod.llm("chat").messages.stream(system="s", messages=[{"role": "user", "content": "x"}], tools=[TOOL], max_tokens=10) as stream:
        parts = [e.delta.partial_json for e in stream if e.delta.type == "input_json_delta"]
    assert "".join(parts) == '{"intent":"x"}'


async def test_demo_actor_line_opt_in(env):
    from core.builder import actors

    assert await actors.model_line("Ana", "yes", "Saturday", "Ana, can you cover?") is None  # not opted in -> canned
    env.setenv("OPENAI_API_KEY", "test-openai")
    env.setenv("VILLAGE_LLM_PROVIDER_ACTORS", "openai")
    comp = FakeCompletions(tool_response("say", {"text": "Yep, Saturday's mine."}))
    fake_openai(env, comp)
    assert await actors.model_line("Ana", "yes", "Saturday", "Ana, can you cover?") == "Yep, Saturday's mine."
    assert comp.calls[0]["tool_choice"] == {"type": "function", "function": {"name": "say"}}
