"""Phone-size QA of the candidate build (390×844).

Order of targets:
 1. Anchor cloud browser on the public candidate URL (${TUNNEL_URL}/v/{v}/r/{rev}/) when it answers 200.
 2. Anchor on the Daytona signed preview URL of the same build (vite preview in the sandbox) when given.
 3. Degrade: local headless Playwright against Core on 127.0.0.1 (stage summary starts with "degraded").
Assertions: the elder view shows exactly 3 BigButtons, each visible, ≥ 88 px tall and ≥ 28 px text,
and the 911 ContactCard is visible. Evidence: elder.png + report.json; the Anchor live view URL."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from core.release.ports import QAResult

VIEWPORT = {"width": 390, "height": 844}
MEASURE_JS = """() => {
  const q = (s) => Array.from(document.querySelectorAll(s));
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  return {
    buttons: q('[data-type="BigButton"]').map(e => ({ id: e.dataset.id, text: e.textContent.trim().slice(0, 40),
      h: Math.round(e.getBoundingClientRect().height), fs: parseFloat(getComputedStyle(e).fontSize), visible: vis(e) })),
    e911: q('[data-type="ContactCard"]').filter(e => (e.getAttribute('href') || '').includes('911')).map(e => ({ visible: vis(e), h: Math.round(e.getBoundingClientRect().height) })),
    title: (document.querySelector('h1') || {}).textContent || '',
    theme: (document.querySelector('[data-theme]') || { dataset: {} }).dataset.theme || 'elder',
  };
}"""


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def assertions_from(m: dict[str, Any], min_h: int = 88, min_fs: int = 28, n_buttons: int = 3) -> list[dict[str, Any]]:
    if m.get("theme", "elder") != "elder":
        out = [{"name": f"{m['theme']} view rendered", "ok": bool(m.get("title")), "detail": m.get("title", "")[:60]}]
        for b in m["buttons"]:
            ok = b["visible"] and b["h"] >= 48
            out.append({"name": f"BigButton {b['id']} visible ≥48px", "ok": bool(ok), "detail": f"h={b['h']}px font={b['fs']}px"})
        return out
    out = [{"name": f"{n_buttons} elder BigButtons", "ok": len(m["buttons"]) == n_buttons, "detail": f"found {len(m['buttons'])}"}]
    for b in m["buttons"]:
        ok = b["visible"] and b["h"] >= min_h and b["fs"] >= min_fs
        out.append({"name": f"BigButton {b['id']} visible ≥{min_h}px", "ok": bool(ok),
                    "detail": f"h={b['h']}px font={b['fs']}px visible={b['visible']} '{b['text']}'"})
    out.append({"name": "911 ContactCard visible", "ok": any(e["visible"] for e in m["e911"]), "detail": f"{len(m['e911'])} found"})
    return out


async def _reachable(url: str | None, headers: dict[str, str] | None = None) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True) as c:
            r = await c.get(url, headers=headers or {})
            return r.status_code == 200 and "<div id=\"root\">" in r.text
    except Exception:
        return False


class AnchorQA:
    def __init__(self, *, keep_session: bool = False) -> None:
        self.keep_session = keep_session
        self._client: Any = None
        self._session: Any = None  # (id, cdp_url, live_view_url)
        self.last_timings: dict[str, int] = {}

    async def _ab(self) -> Any:
        if self._client is None:
            from anchorbrowser import AsyncAnchorbrowser

            self._client = AsyncAnchorbrowser(api_key=os.environ.get("ANCHORBROWSER_API_KEY"))
        return self._client

    async def prewarm(self) -> dict[str, Any]:
        if self._session is None:
            t0 = time.perf_counter()
            ab = await self._ab()
            resp = await ab.sessions.create_session(
                browser={"viewport": VIEWPORT},
                session={"tags": ["village-release"], "recording": {"active": True},
                         "timeout": {"max_duration": 30, "idle_timeout": 10}},
            )
            d = resp.data
            self._session = (d.id, d.cdp_url, d.live_view_url)
            self.last_timings["anchor_create"] = _ms(t0)
        return {"session_id": self._session[0], "live_view_url": self._session[2]}

    async def fetch_recording(self, session_id: str, dest: Path, *, tries: int = 10, wait_s: float = 6.0) -> Path | None:
        """Download the session's primary MP4 (`recordings.fetch_primary_recording`). Anchor finalises it a
        few seconds after the session ends, so poll; never raises. Returns the saved path or None."""
        t0 = time.perf_counter()
        for i in range(tries):
            try:
                ab = await self._ab()
                resp = await ab.recordings.fetch_primary_recording(session_id, timeout=30)
                data = await resp.read()
                if len(data) > 1000 and data[4:8] == b"ftyp":
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    self.last_timings["recording_fetch"] = _ms(t0)
                    self.last_timings["recording_bytes"] = len(data)
                    return dest
            except Exception:
                pass
            if i < tries - 1:
                await asyncio.sleep(wait_s)
        self.last_timings["recording_fetch"] = _ms(t0)
        return None

    async def close(self) -> None:
        if self._session and self._client:
            try:
                await self._client.sessions.delete_session(self._session[0])
            except Exception:
                pass
        self._session = None

    async def _measure(self, page: Any, url: str, out_dir: Path, shot: str) -> tuple[dict[str, Any], Path]:
        await page.goto(url, wait_until="load", timeout=20_000)
        await page.wait_for_selector('[data-type="Screen"]', timeout=10_000)
        m = await page.evaluate(MEASURE_JS)
        png = out_dir / shot
        await page.screenshot(path=str(png), full_page=True)
        return m, png

    async def qa(self, url: str, *, village_id: str, rev: int, out_dir: Path, local_url: str | None = None,
                 alt_url: str | None = None) -> QAResult:
        from playwright.async_api import async_playwright

        out_dir.mkdir(parents=True, exist_ok=True)
        timings: dict[str, int] = {}
        skip = {"X-Daytona-Skip-Preview-Warning": "true"}
        t0 = time.perf_counter()
        target = url if await _reachable(url) else (alt_url if await _reachable(alt_url, skip) else None)
        timings["reach"] = _ms(t0)
        reason = "tunnel unreachable" if target is None else None
        res = QAResult(ok=False, url=target or (local_url or url), viewport=f"{VIEWPORT['width']}x{VIEWPORT['height']}")
        async with async_playwright() as p:
            if target is not None:
                try:
                    t0 = time.perf_counter()
                    info = await self.prewarm()
                    timings["anchor_session"] = _ms(t0)
                    res.session_id, res.live_view_url = info["session_id"], info["live_view_url"]
                    t0 = time.perf_counter()
                    browser = await p.chromium.connect_over_cdp(self._session[1], timeout=20_000)
                    timings["cdp_connect"] = _ms(t0)
                    ctx = browser.contexts[0] if browser.contexts else await browser.new_context(viewport=VIEWPORT)
                    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                    await page.set_viewport_size(VIEWPORT)
                    await page.set_extra_http_headers(skip)
                    t0 = time.perf_counter()
                    m, png = await self._measure(page, target, out_dir, "elder.png")
                    timings["flow"] = _ms(t0)
                    res.assertions, res.screenshots = assertions_from(m), [png]
                    res.ok = all(a["ok"] for a in res.assertions)
                    await browser.close()
                except Exception as exc:
                    reason = f"anchor_unavailable: {type(exc).__name__}: {str(exc)[:120]}"
                    res.assertions = []
                finally:
                    if not self.keep_session:
                        await self.close()
            if not res.assertions:
                res.degraded = True
                res.live_view_url = None
                res.session_id = None
                try:
                    t0 = time.perf_counter()
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
                    m, png = await self._measure(page, local_url or url, out_dir, "elder_local.png")
                    timings["local_flow"] = _ms(t0)
                    await browser.close()
                    res.url = local_url or url
                    res.assertions, res.screenshots = assertions_from(m), [png]
                    res.ok = all(a["ok"] for a in res.assertions)
                    res.error = reason
                except Exception as exc:
                    res.ok = False
                    res.error = f"app_unreachable: {reason}; local: {type(exc).__name__}: {str(exc)[:160]}"
        res.timings_ms = timings
        self.last_timings.update(timings)
        report = {"village": village_id, "rev": rev, "url": res.url, "degraded": res.degraded, "viewport": res.viewport,
                  "anchor_session_id": res.session_id, "live_view_url": res.live_view_url, "assertions": res.assertions,
                  "error": res.error, "timings_ms": timings}
        (out_dir / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
        return res
