"""Offline fakes for the release ports (model off, no network)."""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any

from core.release.contrast import ratio
from core.release.floor_tests import FLOOR
from core.release.ports import BuildResult, EvalResult, LogFn, QAResult


def fmt(r: float) -> str:
    return f"{math.floor(r * 10) / 10:.1f}"


def floor_failures(files: dict[str, bytes]) -> tuple[int, list[str]]:
    """Python mirror of the generated contrast tests (enough to drive the pipeline offline)."""
    spec = json.loads(files["src/village/spec.json"])
    theme = json.loads(files["src/village/theme.json"])
    n, fails = 0, []
    for role, view in spec["views"].items():
        need = FLOOR["elder_contrast"] if view["theme"] == "elder" else FLOOR["other_contrast"]
        for eid, el in view["elements"].items():
            if el["type"] not in ("BigButton", "ContactCard"):
                continue
            n += 1
            tone = el["props"].get("tone") or ("danger" if el["type"] == "ContactCard" else "neutral")
            t = theme["tones"].get(tone, theme["tones"]["neutral"])
            r = ratio(t["fg"], t["bg"])
            if r < need:
                label = f"{role} {el['type']} tone={tone} #{eid}"
                where = "elder" if view["theme"] == "elder" else role
                fails.append(f"floor.test.ts › floor/contrast › {label} contrast >= {need:g}:1 :: AssertionError: "
                             f"contrast {fmt(r)}:1 on {where} Text ({label}) < {need:g}:1: expected false to be true")
    return n, fails


class FakeDaytona:
    def __init__(self, *, always_fail: bool = False, build_fail: bool = False) -> None:
        self.always_fail = always_fail
        self.build_fail = build_fail
        self.calls: list[dict[str, Any]] = []

    async def build(self, files: dict[str, bytes], *, village_id: str, rev: int, log: LogFn | None = None) -> BuildResult:
        self.calls.append({"rev": rev, "files": sorted(files)})
        if log:
            r = log(f"fake build {village_id} r{rev}", "info")
            if hasattr(r, "__await__"):
                await r
        if self.build_fail:
            return BuildResult(False, sandbox_id="sbx_fake", error="vite build failed")
        n, fails = floor_failures(files)
        if self.always_fail and not fails:
            fails = ["floor.test.ts › floor/sizes › elder BigButton #b_call text >= 28px :: AssertionError: font 20px on elder BigButton #b_call"]
        if fails:
            return BuildResult(True, n + 40 - len(fails), len(fails), fails, sandbox_id="sbx_fake",
                               timings_ms={"upload": 1, "build": 2, "tests": 3})
        out = Path(tempfile.mkdtemp(prefix="fake_dist_"))
        (out / "index.html").write_text('<!doctype html><div id="root"></div>')
        return BuildResult(True, n + 40, 0, [], sandbox_id="sbx_fake", dist_dir=out,
                           timings_ms={"upload": 1, "build": 2, "tests": 3, "download": 1})


class FakeAnchor:
    def __init__(self, *, ok: bool = True, degraded: bool = False, recording: bool = False) -> None:
        self.ok = ok
        self.degraded = degraded
        self.recording = recording
        self.urls: list[str] = []

    async def qa(self, url: str, *, village_id: str, rev: int, out_dir: Path, local_url: str | None = None,
                 alt_url: str | None = None) -> QAResult:
        self.urls.append(url)
        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / "elder.png"
        png.write_bytes(b"\x89PNG fake")
        assertions = [{"name": "3 elder BigButtons", "ok": self.ok, "detail": "found 3" if self.ok else "found 2"}]
        return QAResult(ok=self.ok, degraded=self.degraded, assertions=assertions, screenshots=[png],
                        session_id=None if self.degraded else "sess_fake",
                        live_view_url=None if self.degraded else "https://live.anchorbrowser.io/fake",
                        url=local_url if self.degraded else url, error="tunnel unreachable" if self.degraded else (None if self.ok else "assertion"))

    async def fetch_recording(self, session_id: str, dest: Path, **_: Any) -> Path | None:
        if not self.recording:
            return None
        dest.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 2000)
        return dest


class FakeEvals:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    async def run(self, spec: dict[str, Any], *, village_id: str, rev: int, release_id: str) -> EvalResult:
        scores = {"needs_coverage": 0.8, "no_medical_advice": 1.0 if self.ok else 0.0}
        return EvalResult(ok=self.ok, scores=scores, thresholds={"needs_coverage": 0.8, "no_medical_advice": 1.0},
                          failures=[] if self.ok else ["no_medical_advice 0.0 < 1.0"])


class Recorder:
    """broadcast(village, kind, payload) sink."""

    def __init__(self) -> None:
        self.frames: list[tuple[str, str, dict[str, Any]]] = []

    async def __call__(self, village_id: str, kind: str, payload: dict[str, Any]) -> None:
        self.frames.append((village_id, kind, json.loads(json.dumps(payload))))

    def receipts(self) -> list[dict[str, Any]]:
        return [p["receipt"] for _, k, p in self.frames if k == "release"]


class FakeLLMClient:
    """Mimics anthropic messages.create returning a fixed text."""

    village_model = "fake-haiku"
    village_provider = "fake"

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    @property
    def messages(self) -> "FakeLLMClient":
        return self

    def create(self, **kw: Any) -> Any:
        self.prompts.append(kw["messages"][0]["content"])

        class _B:
            def __init__(self, t: str) -> None:
                self.text = t

        class _M:
            def __init__(self, t: str) -> None:
                self.content = [_B(t)]

        return _M(self.text)
