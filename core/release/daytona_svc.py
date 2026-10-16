"""Real Daytona adapter: one warm sandbox (default image; snapshots are denied on this account),
template + node_modules installed once, then per release: upload village files, vite build,
vitest, tar + download dist. The sandbox never calls out (egress is blocked); Core pulls."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import io
import json
import os
import tarfile
import time
from pathlib import Path
from typing import Any

from core.release import bundle
from core.release.ports import BuildResult, LogFn

WARM_LABEL = {"village-release": "warm"}
APP = "app"


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def _emit(log: LogFn | None, line: str, level: str = "info") -> None:
    if log is None:
        return
    r = log(line[:500], level)
    if inspect.isawaitable(r):
        await r


def _deps_key(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for k in ("package.json", "package-lock.json"):
        h.update(files.get(k, b""))
    return h.hexdigest()[:16]


def parse_vitest(report: dict[str, Any]) -> tuple[int, int, list[str]]:
    passed = int(report.get("numPassedTests", 0))
    failed = int(report.get("numFailedTests", 0))
    failures: list[str] = []
    for f in report.get("testResults", []):
        name = os.path.basename(str(f.get("name", "")))
        for a in f.get("assertionResults", []):
            if a.get("status") == "failed":
                msg = (a.get("failureMessages") or [""])[0].splitlines()[0] if a.get("failureMessages") else ""
                full = " › ".join([*(a.get("ancestorTitles") or []), a.get("title", "")])
                failures.append(f"{name} › {full} :: {msg}"[:300])
    return passed, failed, failures[:20]


class DaytonaBuilder:
    def __init__(self, *, keep: bool = True, image: str | None = None) -> None:
        self.keep = keep
        self.image = image or os.environ.get("RELEASE_DAYTONA_IMAGE") or None
        self._client: Any = None
        self._sb: Any = None
        self._home: str = "/home/daytona"
        self._deps: str | None = None
        self._lock = asyncio.Lock()
        self.last_timings: dict[str, int] = {}

    async def client(self) -> Any:
        if self._client is None:
            from daytona import AsyncDaytona  # lazy: optional dependency

            self._client = AsyncDaytona()
        return self._client

    async def sandbox(self) -> Any:
        """Return the warm sandbox, creating one if needed (records create_ms)."""
        if self._sb is not None:
            return self._sb
        from daytona import CreateSandboxFromImageParams, CreateSandboxFromSnapshotParams

        d = await self.client()
        t0 = time.perf_counter()
        sid = os.environ.get("RELEASE_SANDBOX_ID")
        if sid:
            try:
                sb = await d.get(sid)
                if getattr(sb, "state", "") not in ("started", "SandboxState.STARTED") and "started" not in str(getattr(sb, "state", "")).lower():
                    await sb.start(timeout=60)
                self._sb = sb
            except Exception:
                self._sb = None
        if self._sb is None:
            labels = dict(WARM_LABEL)
            if self.image:
                params: Any = CreateSandboxFromImageParams(image=self.image, auto_stop_interval=0, labels=labels)
            else:
                params = CreateSandboxFromSnapshotParams(auto_stop_interval=0, labels=labels)
            self._sb = await d.create(params, timeout=180)
        self.last_timings["create"] = _ms(t0)
        try:
            self._home = await self._sb.get_user_home_dir()
        except Exception:
            pass
        return self._sb

    async def _exec(self, cmd: str, timeout: int = 180) -> tuple[int, str]:
        sb = await self.sandbox()
        r = await sb.process.exec(cmd, cwd=f"{self._home}/{APP}", timeout=timeout)
        return int(getattr(r, "exit_code", 1) or 0), str(getattr(r, "result", "") or "")

    async def _upload(self, files: dict[str, bytes]) -> None:
        from daytona import FileUpload

        sb = await self.sandbox()
        await sb.fs.upload_files(
            [FileUpload(source=data, destination=f"{self._home}/{APP}/{path}") for path, data in files.items()]
        )

    async def prepare(self, template: dict[str, bytes] | None = None, log: LogFn | None = None) -> dict[str, int]:
        """Upload the template and npm install once (pre-warm)."""
        tpl = template or bundle.template_files()
        key = _deps_key(tpl)
        timings: dict[str, int] = {}
        sb = await self.sandbox()
        if self._deps == key:
            return timings
        t0 = time.perf_counter()
        await sb.process.exec(f"mkdir -p {self._home}/{APP}", timeout=30)
        await self._upload(tpl)
        timings["upload_template"] = _ms(t0)
        code, out = await self._exec("cat .deps_key 2>/dev/null", timeout=30)
        if out.strip() != key:
            t0 = time.perf_counter()
            await _emit(log, "npm install (cold sandbox)")
            install = "npm ci --no-audit --no-fund --loglevel=error" if "package-lock.json" in tpl else "npm install --no-audit --no-fund --loglevel=error"
            code, out = await self._exec(f"{install} && echo {key} > .deps_key", timeout=300)
            timings["npm_install"] = _ms(t0)
            if code != 0:
                await _emit(log, out[-400:], "error")
                raise RuntimeError(f"npm install failed: {out[-300:]}")
        self._deps = key
        self.last_timings.update(timings)
        return timings

    async def build(self, files: dict[str, bytes], *, village_id: str, rev: int, log: LogFn | None = None) -> BuildResult:
        async with self._lock:
            return await self._build(files, village_id=village_id, rev=rev, log=log)

    async def _build(self, files: dict[str, bytes], *, village_id: str, rev: int, log: LogFn | None) -> BuildResult:
        timings: dict[str, int] = {}
        self.last_timings = {}
        try:
            sb = await self.sandbox()
            timings["create"] = self.last_timings.get("create", 0)
            tpl_keys = {k for k in files if not k.startswith(("src/village/", "tests/floor/"))}
            prep = await self.prepare({k: files[k] for k in tpl_keys}, log=log)
            timings.update(prep)
            t0 = time.perf_counter()
            await self._upload(files)
            timings["upload"] = _ms(t0)
            await _emit(log, f"uploaded {len(files)} files to sandbox {sb.id}")

            t0 = time.perf_counter()
            code, out = await self._exec("rm -rf dist && npx vite build --logLevel warn 2>&1", timeout=180)
            timings["build"] = _ms(t0)
            for line in out.strip().splitlines()[-5:]:
                await _emit(log, line, "info" if code == 0 else "error")
            if code != 0:
                return BuildResult(False, sandbox_id=sb.id, log_tail=out[-1500:], timings_ms=timings, error="vite build failed")
            await _emit(log, f"vite build ok in {timings['build']} ms")

            t0 = time.perf_counter()
            code, out = await self._exec("rm -f vitest.json; npx vitest run --reporter=json --outputFile=vitest.json >/dev/null 2>&1; echo $?", timeout=180)
            raw = await sb.fs.download_file(f"{self._home}/{APP}/vitest.json")
            timings["tests"] = _ms(t0)
            report = json.loads(raw or b"{}")
            passed, failed, failures = parse_vitest(report)
            await _emit(log, f"vitest: {passed} passed, {failed} failed", "info" if failed == 0 else "error")
            for f in failures[:3]:
                await _emit(log, f, "error")
            result = BuildResult(True, passed, failed, failures, sandbox_id=sb.id, timings_ms=timings, log_tail=out[-500:])
            if failed or not report:
                if not report:
                    result.error = "no vitest report"
                return result

            t0 = time.perf_counter()
            await self._exec("tar czf /tmp/dist.tgz -C dist .", timeout=60)
            tgz = await sb.fs.download_file("/tmp/dist.tgz")
            out_dir = bundle.ROOT / "var" / "releases" / village_id / f"r{rev}" / "dist"
            if out_dir.exists():
                import shutil

                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(tgz or b""), mode="r:gz") as tar:
                tar.extractall(out_dir, filter="data")
            timings["download"] = _ms(t0)
            result.dist_dir = out_dir
            await _emit(log, f"dist downloaded ({len(tgz or b'')} bytes) in {timings['download']} ms")
            return result
        except Exception as exc:  # surfaced as a failed daytona_build stage
            return BuildResult(False, sandbox_id=getattr(self._sb, "id", ""), timings_ms=timings, error=f"{type(exc).__name__}: {str(exc)[:300]}")

    async def keepalive(self) -> None:
        if self._sb is not None:
            try:
                await self._sb.refresh_activity()
            except Exception:
                pass

    async def close(self, delete: bool = False) -> None:
        if delete and self._sb is not None:
            try:
                await self._sb.delete()
            except Exception:
                pass
            self._sb = None
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None


