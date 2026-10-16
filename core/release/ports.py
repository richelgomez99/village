"""Ports the release pipeline depends on. Real adapters: daytona_svc, anchor_qa, evals.
Fakes for offline tests: core/release/fakes.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

# broadcast(village_id, kind, payload) — same shape as core.services.control
Broadcast = Callable[[str, str, dict[str, Any]], Awaitable[None]]
LogFn = Callable[[str, str], Awaitable[None] | None]  # (line, level)


@dataclass
class BuildResult:
    build_ok: bool
    tests_passed: int = 0
    tests_failed: int = 0
    failures: list[str] = field(default_factory=list)
    sandbox_id: str = ""
    dist_dir: Path | None = None
    log_tail: str = ""
    timings_ms: dict[str, int] = field(default_factory=dict)  # create, upload, build, tests, download
    preview_url: str | None = None
    error: str | None = None
    image: str = ""  # e.g. "daytonaio/sandbox:0.8.0" (default image) or "node:22-bookworm-slim"


@dataclass
class QAResult:
    ok: bool
    degraded: bool = False
    assertions: list[dict[str, Any]] = field(default_factory=list)
    screenshots: list[Path] = field(default_factory=list)
    session_id: str | None = None
    live_view_url: str | None = None
    url: str = ""
    viewport: str = "390x844"
    error: str | None = None
    timings_ms: dict[str, int] = field(default_factory=dict)


@dataclass
class EvalResult:
    ok: bool
    scores: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    trace_url: str | None = None
    mirror_path: Path | None = None
    model_chip: str | None = None  # "Bedrock · claude-haiku-4-5 · 520 ms TTFT" (measured on the judge call)


class DaytonaPort(Protocol):
    async def build(self, files: dict[str, bytes], *, village_id: str, rev: int, log: LogFn | None = None) -> BuildResult: ...


class AnchorPort(Protocol):
    async def qa(self, url: str, *, village_id: str, rev: int, out_dir: Path, local_url: str | None = None,
                 alt_url: str | None = None) -> QAResult: ...


class EvalsPort(Protocol):
    async def run(self, spec: dict[str, Any], *, village_id: str, rev: int, release_id: str) -> EvalResult: ...


class PublisherPort(Protocol):
    async def stage(self, village_id: str, rev: int, dist_dir: Path) -> str: ...  # returns candidate path
    async def publish(self, village_id: str, rev: int) -> int | None: ...  # returns previous published rev
    def published_rev(self, village_id: str) -> int | None: ...
