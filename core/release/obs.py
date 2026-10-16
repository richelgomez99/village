"""Tiny OpenInference-style span helpers. No-op unless a tracer provider is registered
(scripts/release_smoke.py and core call arize.otel.register())."""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

_tracer = trace.get_tracer("village.release")


@contextmanager
def span(name: str, kind: str, *, village: str | None = None, node: str | None = None, parent_node: str | None = None,
         input: Any = None, **attrs: Any) -> Iterator[Any]:
    with _tracer.start_as_current_span(name) as sp:
        sp.set_attribute("openinference.span.kind", kind)
        if village:
            sp.set_attribute("session.id", f"village-{village}")
            sp.set_attribute("village.id", village)
        sp.set_attribute("graph.node.id", node or name)
        if parent_node:
            sp.set_attribute("graph.node.parent_id", parent_node)
        if input is not None:
            sp.set_attribute("input.value", input if isinstance(input, str) else json.dumps(input, default=str)[:4000])
        for k, v in attrs.items():
            if v is not None:
                sp.set_attribute(k, v if isinstance(v, (str, int, float, bool)) else json.dumps(v, default=str)[:4000])
        yield sp


def finish(sp: Any, ok: bool, output: Any = None, error: str | None = None) -> None:
    if output is not None:
        sp.set_attribute("output.value", output if isinstance(output, str) else json.dumps(output, default=str)[:4000])
    sp.set_status(Status(StatusCode.OK) if ok else Status(StatusCode.ERROR, (error or "failed")[:200]))


def trace_id_of(sp: Any) -> str | None:
    ctx = sp.get_span_context()
    if not ctx or not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")
