"""Tracer port. Core's tracer (core.obs, Arize OITracer) plugs in via `set_tracer`; tests use
`RecordingTracer`. Span kinds follow OpenInference: AGENT, CHAIN, LLM, TOOL, EVALUATOR."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol


class Tracer(Protocol):
    def span(self, name: str, kind: str = "CHAIN", **attrs: Any) -> Any: ...


@dataclass
class SpanRecord:
    name: str
    kind: str
    attrs: dict[str, Any]

    def set(self, key: str, value: Any) -> None:
        self.attrs[key] = value


class NullTracer:
    @contextmanager
    def span(self, name: str, kind: str = "CHAIN", **attrs: Any) -> Iterator[SpanRecord]:
        yield SpanRecord(name, kind, dict(attrs))


@dataclass
class RecordingTracer:
    spans: list[SpanRecord] = field(default_factory=list)

    @contextmanager
    def span(self, name: str, kind: str = "CHAIN", **attrs: Any) -> Iterator[SpanRecord]:
        rec = SpanRecord(name, kind, dict(attrs))
        self.spans.append(rec)
        yield rec


_TRACER: Any = None


def set_tracer(tracer: Any) -> None:
    global _TRACER
    _TRACER = tracer


def get_tracer() -> Any:
    if _TRACER is not None:
        return _TRACER
    try:  # core.obs lands with the evals lane
        from core.obs import builder_tracer  # type: ignore

        return builder_tracer()
    except Exception:
        return NullTracer()


@contextmanager
def span(name: str, kind: str = "CHAIN", **attrs: object) -> Iterator[Any]:
    with get_tracer().span(name, kind, **attrs) as rec:
        yield rec
