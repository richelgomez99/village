import asyncio

import pytest

from core.obs import tracing


def test_noop_span_carries_graph_attributes():
    tracing.init_tracing(force=True)
    assert tracing.mode() == "noop"
    with tracing.span("GUARDRAIL", "gate.decide", village_id="v_reyes", node_id="gate", parent_id="voice",
                      user_id="m_carmen", input={"a": 1}) as s:
        s.set_output({"decision": "verify_with_member"})
        s.set_eval("x", "ok", 1)
    a = s.attributes
    assert a["openinference.span.kind"] == "GUARDRAIL" and a["session.id"] == "village-v_reyes"
    assert a["graph.node.id"] == "gate" and a["graph.node.parent_id"] == "voice" and a["user.id"] == "m_carmen"
    assert a["eval.x.label"] == "ok" and s.trace_id is None
    assert tracing.flush()


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        with tracing.span("BOGUS", "x"):
            pass


def test_decorators_sync_and_async():
    @tracing.tool(node_id="t")
    def f(x, village_id=None):
        return x + 1

    @tracing.agent()
    async def g(x):
        return x * 2

    assert f(1, village_id="v_reyes") == 2
    assert asyncio.run(g(3)) == 6


def test_errors_propagate():
    with pytest.raises(RuntimeError):
        with tracing.span("CHAIN", "x"):
            raise RuntimeError("boom")
