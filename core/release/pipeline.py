"""Release pipeline (FS-5, D7/D23): spec → daytona_build → tests → anchor_qa → arize_evals → live.

Every stage transition is broadcast as control{kind: release} (validated against
ws_messages.schema.json → release.schema.json). Blue/green: a failing stage keeps the last
good rev live. A failing floor test hands the failure to the Builder (repair.py), which
patches the theme token and re-releases as rev+1 (trigger=repair, repair_of=<blocked id>),
at most 2 repairs (attempt ≤ 3)."""
from __future__ import annotations

import asyncio
import copy
import os
import re
import time
from typing import Any, Callable

from core.release import bundle, obs, receipts
from core.release.ports import AnchorPort, Broadcast, DaytonaPort, EvalsPort, PublisherPort
from core.release.receipts import Receipt, ReceiptStore, now_iso, stage
from core.release.repair import repair as repair_theme
from core.release.serve import LocalPublisher

_locks: dict[str, asyncio.Lock] = {}
LAST_TIMINGS: dict[str, dict[str, int]] = {}


class FrameError(ValueError):
    pass


def release_id(village_id: str, rev: int) -> str:
    return f"rel_{village_id.removeprefix('v_')}_r{rev}"


def _summary_from_failures(failures: list[str]) -> str:
    if not failures:
        return "tests failed"
    m = re.search(r"(contrast [0-9.]+:1 on [a-z_]+ Text).*?< ([0-9.]+):1", failures[0])
    if m:
        return f"{m.group(1)} (needs {m.group(2).rstrip('0').rstrip('.') if '.' in m.group(2) else m.group(2)}:1)"
    tail = failures[0].split("::")[-1].strip()
    return tail[:200]


def _spec_summary(spec: dict[str, Any]) -> str:
    views = spec.get("views") or {}
    customs = spec.get("custom_components") or []
    return f"VillageSpec valid ({len(views)} views, {len(customs)} custom component{'s' if len(customs) != 1 else ''})"


def _validate_spec(spec: dict[str, Any]) -> list[str]:
    v = receipts._validator("village_spec.schema.json")
    return [f"{'/'.join(map(str, e.path))}: {e.message}"[:300] for e in v.iter_errors(spec)][:10]


class _Run:
    def __init__(self, village_id: str, broadcast: Broadcast, store: ReceiptStore, strict: bool) -> None:
        self.village_id = village_id
        self.broadcast = broadcast
        self.store = store
        self.strict = strict

    async def emit(self, r: Receipt) -> None:
        frame = {"type": "control", "kind": "release", "payload": {"receipt": copy.deepcopy(r)}, "at": now_iso()}
        errs = receipts.validate_control(frame)
        if errs:
            if self.strict:
                raise FrameError("; ".join(errs[:3]))
        self.store.put(r)
        await self.broadcast(self.village_id, "release", frame["payload"])

    async def log(self, rel: str, rev: int, stage_name: str, line: str, level: str = "info") -> None:
        payload = {"release_id": rel, "rev": rev, "stage": stage_name, "line": line[:500], "level": level}
        try:
            await self.broadcast(self.village_id, "build_log", payload)
        except Exception:
            pass

    async def start(self, r: Receipt, name: str) -> dict[str, Any]:
        st = stage(r, name)
        st["status"], st["started"], st["ended"] = "running", now_iso(), None
        await self.emit(r)
        return st

    async def end(self, r: Receipt, name: str, ok: bool, t0: float, **details: Any) -> dict[str, Any]:
        st = stage(r, name)
        st["status"], st["ended"] = ("passed" if ok else "failed"), now_iso()
        if st["started"] is None:
            st["started"] = st["ended"]
        details.setdefault("duration_ms", int((time.perf_counter() - t0) * 1000))
        evidence = details.pop("evidence_urls", None)
        evidence_url = details.pop("evidence_url", None)
        trace_id = details.pop("trace_id", None)
        st["details"].update({k: v for k, v in details.items() if v is not None and v != [] and v != {}})
        if evidence:
            st["evidence_urls"] = evidence[:12]
        if evidence_url:
            st["evidence_url"] = evidence_url
        if trace_id:
            st["trace_id"] = trace_id
        await self.emit(r)
        return st

    async def block(self, r: Receipt) -> None:
        for st in r["stages"]:
            if st["status"] in ("pending", "running"):
                st["status"], st["started"], st["ended"] = "skipped", None, None
        r["result"] = "blocked"
        r["live_rev"] = r["previous_live_rev"]
        await self.emit(r)


async def run_release(
    village_id: str,
    spec: dict[str, Any],
    rev: int,
    *,
    broadcast: Broadcast,
    llm: Callable[[str], Any] | None,
    daytona: DaytonaPort,
    anchor: AnchorPort | None,
    evals: EvalsPort | None,
    publisher: PublisherPort | None = None,
    store: ReceiptStore | None = None,
    public_base: str | None = None,
    local_base: str | None = None,
    inject: str | None = None,
    trigger: str = "initial",
    proposal_id: str | None = None,
    publish: bool = True,
    max_repairs: int = 2,
    strict: bool = True,
    history: list[Receipt] | None = None,
) -> Receipt:
    """Release `spec` as `rev`. Returns the final receipt; `history` (if given) gets every attempt."""
    lock = _locks.setdefault(village_id, asyncio.Lock())
    async with lock:
        return await _run(village_id, spec, rev, broadcast=broadcast, llm=llm, daytona=daytona, anchor=anchor,
                          evals=evals, publisher=publisher or LocalPublisher(), store=store or ReceiptStore(),
                          public_base=public_base, local_base=local_base, inject=inject, trigger=trigger,
                          proposal_id=proposal_id, publish=publish, max_repairs=max_repairs, strict=strict,
                          history=history if history is not None else [])


async def _run(village_id: str, spec: dict[str, Any], rev: int, *, broadcast: Broadcast, llm: Any,
               daytona: DaytonaPort, anchor: AnchorPort | None, evals: EvalsPort | None,
               publisher: PublisherPort, store: ReceiptStore, public_base: str | None, local_base: str | None,
               inject: str | None, trigger: str, proposal_id: str | None, publish: bool, max_repairs: int,
               strict: bool, history: list[Receipt]) -> Receipt:
    run = _Run(village_id, broadcast, store, strict)
    local_base = (local_base or os.environ.get("RELEASE_LOCAL_BASE") or "http://127.0.0.1:8787").rstrip("/")
    public_base = (public_base or os.environ.get("TUNNEL_URL") or local_base).rstrip("/")
    theme = bundle.village_theme(spec)
    repair_of: str | None = None
    spec_note: str | None = None
    attempt = 1
    timings: dict[str, int] = {}
    LAST_TIMINGS[village_id] = timings
    t_total = time.perf_counter()

    with obs.span("builder.release", "AGENT", village=village_id, node="builder", input={"village": village_id, "rev": rev, "trigger": trigger}) as root:
        trace_id = obs.trace_id_of(root)
        while True:
            rel = release_id(village_id, rev)
            prev_live = publisher.published_rev(village_id)
            r = receipts.new_receipt(release_id=rel, village=village_id, rev=rev, previous_live_rev=prev_live,
                                     attempt=attempt, trigger=trigger if attempt == 1 else "repair",
                                     repair_of=repair_of, trace_id=trace_id, proposal_id=proposal_id)
            r["evidence_base_url"] = f"{public_base}/releases/{rel}/qa/"
            history.append(r)

            # ── spec ──
            t0 = time.perf_counter()
            await run.start(r, "spec")
            errs = _validate_spec(spec)
            if errs:
                await run.end(r, "spec", False, t0, summary=f"VillageSpec invalid: {errs[0]}"[:200], failures=errs)
                await run.block(r)
                obs.finish(root, False, error="spec invalid")
                return r
            files = bundle.build(spec, rev, theme=theme, inject=inject if attempt == 1 else None)
            await run.end(r, "spec", True, t0, summary=spec_note or _spec_summary(spec))

            # ── daytona_build + tests ──
            t0 = time.perf_counter()
            await run.start(r, "daytona_build")

            async def log(line: str, level: str = "info", _rel: str = rel, _rev: int = rev) -> None:
                await run.log(_rel, _rev, "daytona_build", line, level)

            with obs.span("daytona_build", "TOOL", village=village_id, node=f"daytona_build_{attempt}", parent_node="builder",
                          input={"rev": rev, "files": len(files)}, **{"tool.name": "daytona_build"}) as sp:
                res = await daytona.build(files, village_id=village_id, rev=rev, log=log)
                tests_ok = res.build_ok and res.tests_failed == 0 and res.error is None
                obs.finish(sp, tests_ok, output={"build_ok": res.build_ok, "passed": res.tests_passed, "failed": res.tests_failed,
                                                 "failures": res.failures[:3]}, error=(res.failures[:1] or [res.error or ""])[0])
            for k, v in res.timings_ms.items():
                timings[f"{k}" if attempt == 1 else f"{k}_a{attempt}"] = v
            build_ms = sum(res.timings_ms.get(k, 0) for k in ("create", "upload_template", "npm_install", "upload", "build"))
            await run.end(r, "daytona_build", res.build_ok, t0, duration_ms=build_ms,
                          summary=("vite build ok" if res.build_ok else f"build failed: {res.error or 'vite'}")[:200],
                          sandbox_id=res.sandbox_id[:80] or None, preview_url=res.preview_url,
                          error=None if res.build_ok else (res.error or res.log_tail[-400:] or "build failed")[:500])
            if not res.build_ok:
                await run.block(r)
                obs.finish(root, False, error="build failed")
                return r

            st = stage(r, "tests")
            st["status"], st["started"], st["ended"] = "running", stage(r, "daytona_build")["ended"], None
            ok = res.tests_failed == 0 and res.error is None
            await run.end(r, "tests", ok, time.perf_counter(), duration_ms=res.timings_ms.get("tests", 0),
                          tests_passed=res.tests_passed, tests_failed=res.tests_failed, failures=res.failures,
                          summary=(f"{res.tests_passed} floor tests passed" if ok else (res.error or _summary_from_failures(res.failures)))[:200])
            if not ok:
                await run.block(r)
                if attempt > max_repairs or res.error:
                    obs.finish(root, False, error="tests failed; no repairs left")
                    return r
                # The Builder fixes its own build (D23 #2).
                fix = repair_theme(theme, res.failures, llm=llm, village=village_id)
                await run.log(rel, rev, "tests", f"builder repair ({fix.mode}): {fix.summary}", "warn")
                theme = fix.theme
                spec_note = fix.summary[:200]
                repair_of = rel
                rev += 1
                attempt += 1
                spec = copy.deepcopy(spec)
                spec["rev"] = rev
                continue

            # ── anchor_qa ──
            t0 = time.perf_counter()
            await run.start(r, "anchor_qa")
            candidate = await publisher.stage(village_id, rev, res.dist_dir) if res.dist_dir else f"/v/{village_id}/r/{rev}/"
            r["candidate_path"] = candidate
            qa_dir = (bundle.ROOT / "var" / "releases" / village_id / f"r{rev}" / "qa")
            qa_dir.mkdir(parents=True, exist_ok=True)
            if anchor is None:
                st = stage(r, "anchor_qa")
                st["status"], st["started"], st["ended"] = "skipped", None, None
                st["details"] = {"summary": "QA not configured"}
                await run.emit(r)
            else:
                with obs.span("anchor_qa", "TOOL", village=village_id, node="anchor_qa", parent_node="builder",
                              **{"tool.name": "anchor_qa"}) as sp:
                    qa = await anchor.qa(f"{public_base}{candidate}?role=elder", village_id=village_id, rev=rev,
                                         out_dir=qa_dir, local_url=f"{local_base}{candidate}?role=elder",
                                         alt_url=f"{res.preview_url}?role=elder" if res.preview_url else None)
                    obs.finish(sp, qa.ok, output={"assertions": qa.assertions, "degraded": qa.degraded}, error=qa.error)
                timings["anchor"] = int((time.perf_counter() - t0) * 1000)
                ev = [{"kind": "screenshot", "url": f"{public_base}/releases/{rel}/qa/{p.name}", "label": p.stem[:80], "viewport": qa.viewport}
                      for p in qa.screenshots]
                if (qa_dir / "report.json").exists():
                    ev.append({"kind": "report", "url": f"{public_base}/releases/{rel}/qa/report.json"})
                if qa.live_view_url:
                    ev.append({"kind": "recording", "url": qa.live_view_url, "label": "Anchor live view"})
                n_ok = sum(1 for a in qa.assertions if a.get("ok"))
                summary = f"{n_ok}/{len(qa.assertions)} checks at {qa.viewport}"
                if qa.degraded:
                    summary = f"degraded: local Playwright ({(qa.error or 'tunnel unreachable')[:60]}); " + summary
                elif not qa.ok:
                    summary = f"QA failed: {(qa.error or '')[:120]}"
                await run.end(r, "anchor_qa", qa.ok, t0, summary=summary[:200], viewport=qa.viewport,
                              anchor_session_id=(qa.session_id or None) and qa.session_id[:80], live_view_url=qa.live_view_url,
                              failures=[f"{a['name']}: {a.get('detail', '')}"[:300] for a in qa.assertions if not a.get("ok")],
                              evidence_urls=ev, evidence_url=qa.live_view_url, error=qa.error if not qa.ok else None)
                if not qa.ok:
                    await run.block(r)
                    obs.finish(root, False, error="anchor qa failed")
                    return r

            # ── arize_evals ──
            t0 = time.perf_counter()
            await run.start(r, "arize_evals")
            if evals is None:
                st = stage(r, "arize_evals")
                st["status"], st["started"], st["ended"] = "skipped", None, None
                await run.emit(r)
            else:
                with obs.span("arize_evals", "EVALUATOR", village=village_id, node="arize_evals", parent_node="builder") as sp:
                    er = await evals.run(spec, village_id=village_id, rev=rev, release_id=rel)
                    obs.finish(sp, er.ok, output=er.scores, error="; ".join(er.failures[:2]) or None)
                timings["evals"] = int((time.perf_counter() - t0) * 1000)
                await run.end(r, "arize_evals", er.ok, t0, eval_scores=er.scores, eval_thresholds=er.thresholds,
                              failures=er.failures[:20], trace_id=trace_id, evidence_url=er.trace_url,
                              summary=("evals passed" if er.ok else f"eval failed: {er.failures[0] if er.failures else ''}")[:200])
                if not er.ok:
                    await run.block(r)
                    obs.finish(root, False, error="evals failed")
                    return r

            # ── live (blue/green) ──
            t0 = time.perf_counter()
            await run.start(r, "live")
            if not publish:
                st = stage(r, "live")
                st["status"], st["started"], st["ended"] = "pending", None, None
                st["details"] = {"summary": "awaiting approval"}
                await run.emit(r)
                obs.finish(root, True, output={"result": "in_progress"})
                return r
            prev = await publisher.publish(village_id, rev)
            r["live_rev"] = rev
            r["result"] = "released"
            await run.end(r, "live", True, t0, summary=f"published_rev {prev if prev is not None else '∅'} → {rev}",
                          roles_patched=sorted((spec.get("views") or {}).keys()))
            timings["total"] = int((time.perf_counter() - t_total) * 1000)
            LAST_TIMINGS[village_id] = timings
            obs.finish(root, True, output={"result": "released", "live_rev": rev, "attempts": attempt})
            return r


