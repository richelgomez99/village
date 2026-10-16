from __future__ import annotations

import sys
import types

from core.builder import prompts


class _Msg:
    def __init__(self, role, content):
        self.role, self.content = role, content


def _fake_arize(text="HUB SYSTEM PROMPT", vid="UHJvbXB0VmVyc2lvbjoxMDk0MDE6dFZIMw=="):
    mod = types.ModuleType("arize")
    calls = []

    class _Prompts:
        def get(self, *, prompt, space, label):
            calls.append((prompt, space, label))
            return types.SimpleNamespace(version=types.SimpleNamespace(id=vid, messages=[_Msg("MessageRole.SYSTEM", text)]))

    class ArizeClient:
        def __init__(self, api_key):
            self.prompts = _Prompts()

    mod.ArizeClient = ArizeClient
    return mod, calls


def test_hub_fetch_with_sdk_mocked(monkeypatch) -> None:
    mod, calls = _fake_arize()
    monkeypatch.setitem(sys.modules, "arize", mod)
    monkeypatch.setenv("ARIZE_API_KEY", "k")
    monkeypatch.setenv("ARIZE_SPACE_ID", "s")
    prompts._CACHE = None
    t = prompts.get_builder_prompt("hub")
    assert (t.source, t.version_id, t.text, t.name) == ("hub", "UHJvbXB0VmVyc2lvbjoxMDk0MDE6dFZIMw==", "HUB SYSTEM PROMPT", "village-builder")
    assert calls == [("village-builder", "s", "production")]
    prompts.get_builder_prompt("hub")
    assert len(calls) == 1  # 10 s TTL cache


def test_hub_down_falls_back_to_local(monkeypatch) -> None:
    mod = types.ModuleType("arize")

    class ArizeClient:
        def __init__(self, api_key):
            raise RuntimeError("down")

    mod.ArizeClient = ArizeClient
    monkeypatch.setitem(sys.modules, "arize", mod)
    monkeypatch.setenv("ARIZE_API_KEY", "k")
    monkeypatch.setenv("ARIZE_SPACE_ID", "s")
    prompts._CACHE = None
    t = prompts.get_builder_prompt("hub")
    assert t.source == "local" and t.version_id == "local" and "## SYSTEM PROMPT" in t.text
    prompts._CACHE = None


def test_render_spans_carry_prompt_template_attrs(monkeypatch) -> None:
    import asyncio

    from core.builder import templates
    from core.builder.render import render_views
    from core.builder.services_stub import MemoryServices
    from core.builder.spans import RecordingTracer, set_tracer

    mod, _ = _fake_arize()
    monkeypatch.setenv("BUILDER_PROMPT_SOURCE", "hub")
    monkeypatch.setitem(sys.modules, "arize", mod)
    monkeypatch.setenv("ARIZE_API_KEY", "k")
    monkeypatch.setenv("ARIZE_SPACE_ID", "s")
    prompts._CACHE = None
    tracer = RecordingTracer()
    set_tracer(tracer)
    try:
        spec = templates.spec("care", village_id="v_pp")

        class Fake:
            model = "fake"

            async def tool_call(self, **kw):
                raise RuntimeError("no model")

        asyncio.run(render_views(spec, village_id="v_pp", services=MemoryServices(), llm=Fake()))
        llm_spans = [s for s in tracer.spans if s.kind == "LLM"]
        assert llm_spans and all(s.attrs["llm.prompt_template.version"] == "UHJvbXB0VmVyc2lvbjoxMDk0MDE6dFZIMw==" and s.attrs["llm.prompt_template.name"] == "village-builder" for s in llm_spans)
    finally:
        set_tracer(None)
        prompts._CACHE = None
