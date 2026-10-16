"""Arize tracing for Village, with a no-op fallback.

    from core.obs.tracing import init_tracing, span, traced

    init_tracing()                       # arize_otel.register when ARIZE_* keys exist
    with span("GUARDRAIL", "gate.decide", village_id="v_reyes", node_id="gate", parent_id="voice",
              user_id="m_carmen", input=req) as s:
        s.set_output(decision)
        s.set_attribute("gate.rule_id", decision["rule_id"])

    @traced("TOOL", node_id="report_money_request", parent_id="mom_line")
    def handle(...): ...

Every span carries openinference.span.kind, session.id=village-<id>, graph.node.id,
graph.node.parent_id and user.id when known (AGENTS.md rule 4). Without keys, or with
VILLAGE_TRACING=off, everything is a no-op and never raises.
"""

from __future__ import annotations

import functools
import json
import os
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

KINDS = {"AGENT", "TOOL", "GUARDRAIL", "CHAIN", "EVALUATOR", "LLM", "RETRIEVER"}

_lock = threading.Lock()
_state: dict[str, Any] = {"provider": None, "tracer": None, "mode": "uninitialized"}


def _jsonish(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)[:20000]
    except Exception:
        return str(value)[:20000]


def init_tracing(project: str | None = None, *, force: bool = False) -> str:
    """Register the Arize exporter once. Returns 'arize' or 'noop'."""
    with _lock:
        if _state["mode"] != "uninitialized" and not force:
            return _state["mode"]
        space, key = os.environ.get("ARIZE_SPACE_ID"), os.environ.get("ARIZE_API_KEY")
        if os.environ.get("VILLAGE_TRACING", "").lower() == "off" or not space or not key:
            _state.update(provider=None, tracer=None, mode="noop")
            return "noop"
        try:
            from arize.otel import register

            provider = register(
                space_id=space,
                api_key=key,
                project_name=project or os.environ.get("ARIZE_PROJECT_NAME", "village"),
                set_global_tracer_provider=False,
            )
            _state.update(provider=provider, tracer=provider.get_tracer("village"), mode="arize")
            try:
                from openinference.instrumentation.anthropic import AnthropicInstrumentor

                AnthropicInstrumentor().instrument(tracer_provider=provider)
            except Exception:
                pass
        except Exception as exc:  # never break the app over tracing
            _state.update(provider=None, tracer=None, mode=f"noop:{type(exc).__name__}")
        return _state["mode"]


def mode() -> str:
    return _state["mode"]


def flush(timeout_ms: int = 5000) -> bool:
    provider = _state.get("provider")
    if provider is None:
        return True
    try:
        return bool(provider.force_flush(timeout_ms))
    except Exception:
        return False


class SpanHandle:
    """Thin wrapper so callers never touch OTel types (works for real and no-op spans)."""

    def __init__(self, otel_span: Any = None) -> None:
        self._span = otel_span
        self.attributes: dict[str, Any] = {}

    @property
    def recording(self) -> bool:
        return self._span is not None

    @property
    def trace_id(self) -> str | None:
        if self._span is None:
            return None
        ctx = self._span.get_span_context()
        return format(ctx.trace_id, "032x")

    @property
    def span_id(self) -> str | None:
        if self._span is None:
            return None
        return format(self._span.get_span_context().span_id, "016x")

    def set_attribute(self, key: str, value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, (str, bool, int, float)):
            value = _jsonish(value)
        self.attributes[key] = value
        if self._span is not None:
            try:
                self._span.set_attribute(key, value)
            except Exception:
                pass

    def set_output(self, value: Any) -> None:
        self.set_attribute("output.value", _jsonish(value))

    def set_eval(self, name: str, label: str, score: float | None = None, explanation: str | None = None) -> None:
        self.set_attribute(f"eval.{name}.label", label)
        if score is not None:
            self.set_attribute(f"eval.{name}.score", float(score))
        if explanation:
            self.set_attribute(f"eval.{name}.explanation", explanation[:2000])


@contextmanager
def span(kind: str, name: str, *, village_id: str | None = None, node_id: str | None = None,
         parent_id: str | None = None, user_id: str | None = None, session_id: str | None = None,
         input: Any = None, attributes: dict[str, Any] | None = None) -> Iterator[SpanHandle]:
    kind = kind.upper()
    if kind not in KINDS:
        raise ValueError(f"unknown span kind {kind}")
    if _state["mode"] == "uninitialized":
        init_tracing()
    tracer = _state.get("tracer")
    attrs: dict[str, Any] = {"openinference.span.kind": kind, "graph.node.id": node_id or name}
    if parent_id:
        attrs["graph.node.parent_id"] = parent_id
    sid = session_id or (f"village-{village_id}" if village_id else None)
    if sid:
        attrs["session.id"] = sid
    if user_id:
        attrs["user.id"] = user_id
    if village_id:
        attrs["village.id"] = village_id
    if input is not None:
        attrs["input.value"] = _jsonish(input)
    attrs.update(attributes or {})
    if tracer is None:
        handle = SpanHandle(None)
        for k, v in attrs.items():
            handle.set_attribute(k, v)
        yield handle
        return
    with tracer.start_as_current_span(name) as otel_span:
        handle = SpanHandle(otel_span)
        for k, v in attrs.items():
            handle.set_attribute(k, v)
        try:
            yield handle
        except Exception as exc:
            try:
                from opentelemetry.trace import Status, StatusCode

                otel_span.record_exception(exc)
                otel_span.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
            except Exception:
                pass
            raise
        else:
            try:
                from opentelemetry.trace import Status, StatusCode

                otel_span.set_status(Status(StatusCode.OK))
            except Exception:
                pass


def traced(kind: str, name: str | None = None, *, node_id: str | None = None, parent_id: str | None = None,
           village_kw: str = "village_id", user_kw: str = "user_id") -> Callable:
    """Decorator: wraps a sync or async function in a span; kwargs village_id/user_id feed session/user."""

    def wrap(fn: Callable) -> Callable:
        span_name = name or fn.__qualname__

        if _is_coro(fn):
            @functools.wraps(fn)
            async def aw(*args: Any, **kwargs: Any) -> Any:
                with span(kind, span_name, village_id=kwargs.get(village_kw), user_id=kwargs.get(user_kw),
                          node_id=node_id or span_name, parent_id=parent_id, input=_call_input(args, kwargs)) as s:
                    out = await fn(*args, **kwargs)
                    s.set_output(out)
                    return out

            return aw

        @functools.wraps(fn)
        def w(*args: Any, **kwargs: Any) -> Any:
            with span(kind, span_name, village_id=kwargs.get(village_kw), user_id=kwargs.get(user_kw),
                      node_id=node_id or span_name, parent_id=parent_id, input=_call_input(args, kwargs)) as s:
                out = fn(*args, **kwargs)
                s.set_output(out)
                return out

        return w

    return wrap


agent = functools.partial(traced, "AGENT")
tool = functools.partial(traced, "TOOL")
guardrail = functools.partial(traced, "GUARDRAIL")
chain = functools.partial(traced, "CHAIN")
evaluator = functools.partial(traced, "EVALUATOR")


def _is_coro(fn: Callable) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn)


def _call_input(args: tuple, kwargs: dict) -> Any:
    try:
        return {"args": list(args), "kwargs": kwargs}
    except Exception:
        return None
