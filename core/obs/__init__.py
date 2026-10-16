"""Observability helpers (Arize / OpenTelemetry). Owned by the evals lane.

`builder_tracer()` adapts `core.obs.tracing.span` to the builder's Tracer port
(`core/builder/spans.py`: `tracer.span(name, kind, **attrs)` yielding a record with `.set(k, v)`),
so builder spans land in Arize project `village` with session.id `village-<id>` when ARIZE_* keys exist."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class _BuilderRecord:
    def __init__(self, handle: Any, name: str, kind: str, attrs: dict[str, Any]) -> None:
        self._handle = handle
        self.name, self.kind, self.attrs = name, kind, attrs

    @property
    def trace_id(self) -> str | None:
        return getattr(self._handle, "trace_id", None)

    def set(self, key: str, value: Any) -> None:
        self.attrs[key] = value
        self._handle.set_attribute(key, value)


class BuilderTracer:
    @contextmanager
    def span(self, name: str, kind: str = "CHAIN", **attrs: Any) -> Iterator[_BuilderRecord]:
        from core.obs import tracing

        kind = kind.upper() if kind.upper() in tracing.KINDS else "CHAIN"
        session = attrs.get("session.id")
        village_id = session[len("village-"):] if isinstance(session, str) and session.startswith("village-") else None
        with tracing.span(kind, name, village_id=village_id, session_id=session,
                          node_id=attrs.get("graph.node.id"), parent_id=attrs.get("graph.node.parent_id"),
                          attributes={k: v for k, v in attrs.items() if v is not None}) as handle:
            yield _BuilderRecord(handle, name, kind, dict(attrs))


_TRACER = BuilderTracer()


def builder_tracer() -> BuilderTracer:
    return _TRACER
