from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from core.release import run_release
from core.release.fakes import FakeAnchor, FakeDaytona, FakeEvals, FakeLLMClient, Recorder

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


async def test_trace_shape_agent_tool_fail_llm_tool_ok(spec, publisher, store):
    _exporter.clear()
    client = FakeLLMClient('{"patch":[{"path":"tones.info.fg","value":"#1F1A15"}],"why":"ink"}')
    history = []
    r = await run_release("v_reyes", spec, 3, broadcast=Recorder(), llm=lambda role: client, daytona=FakeDaytona(),
                          anchor=FakeAnchor(), evals=FakeEvals(), publisher=publisher, store=store, inject="contrast", history=history)
    spans = sorted(_exporter.get_finished_spans(), key=lambda s: s.start_time)
    kinds = [(s.name, s.attributes.get("openinference.span.kind"), s.status.status_code.name) for s in spans]
    seq = [(n, k, st) for n, k, st in kinds if n in ("builder.release", "daytona_build", "builder.repair_theme")]
    assert seq == [("builder.release", "AGENT", "OK"), ("daytona_build", "TOOL", "ERROR"),
                   ("builder.repair_theme", "LLM", "OK"), ("daytona_build", "TOOL", "OK")]
    root = spans[0]
    assert all(s.context.trace_id == root.context.trace_id for s in spans)
    assert root.attributes["session.id"] == "village-v_reyes"
    assert r["trace_id"] == format(root.context.trace_id, "032x") == history[0]["trace_id"]


async def test_approval_marks_release_span_and_annotates(spec, publisher, store, monkeypatch):
    import asyncio

    from core.release import annotate, pipeline

    calls = []
    monkeypatch.setattr(annotate, "_write", lambda sid, member, label, score, note: calls.append((sid, member, label, score)) or {"ok": True})
    real = annotate.write_human_approval
    monkeypatch.setattr(annotate, "write_human_approval", lambda *a, **k: real(*a, **{**k, "delays": (0.0,)}))
    _exporter.clear()
    r = await run_release("v_reyes", spec, 7, broadcast=Recorder(), llm=None, daytona=FakeDaytona(), anchor=FakeAnchor(),
                          evals=FakeEvals(), publisher=publisher, store=store, trigger="proposal", proposal_id="prop_scamcheck",
                          approved_by="m_ana")
    await asyncio.gather(*list(pipeline.BACKGROUND))
    root = next(s for s in _exporter.get_finished_spans() if s.name == "builder.release")
    assert root.attributes["human.approval"] == "approved_by:m_ana" and root.attributes["user.id"] == "m_ana"
    assert r["stages"][5]["details"]["summary"].endswith("approved by m_ana")
    assert calls == [(format(root.context.span_id, "016x"), "m_ana", "approved", 1.0)]
    assert annotate.LAST["rel_reyes_r7"]["ok"] is True
