"""Run the real release pipeline once against the Reyes fixture and print measured timings.

  uv run --with daytona --with anchorbrowser --with playwright --with boto3 python scripts/release_smoke.py [--break-contrast] [--cold]

Real Daytona sandbox (reuses RELEASE_SANDBOX_ID when set and not --cold), real Anchor when a public
URL answers (TUNNEL_URL candidate, else the Daytona signed preview of the same build), else local
Playwright (degraded). Evals in-process (model only if VILLAGE_LLM != off). Spans → Arize when keys exist.
Never prints keys."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
# An empty AWS_BEARER_TOKEN_BEDROCK makes the anthropic SDK send "Bearer " (illegal header); drop empties so SigV4 is used.
for _k in [k for k, v in os.environ.items() if k.startswith(("AWS_", "ANTHROPIC_")) and v == ""]:
    os.environ.pop(_k)


def register_arize() -> str:
    if not (os.environ.get("ARIZE_SPACE_ID") and os.environ.get("ARIZE_API_KEY")):
        return "off (no keys)"
    try:
        from arize.otel import register

        register(space_id=os.environ["ARIZE_SPACE_ID"], api_key=os.environ["ARIZE_API_KEY"],
                 project_name=os.environ.get("ARIZE_PROJECT_NAME", "village"), set_global_tracer_provider=True)
        return f"on (project {os.environ.get('ARIZE_PROJECT_NAME', 'village')})"
    except Exception as exc:
        return f"off ({type(exc).__name__})"


async def serve_local(port: int):
    import uvicorn
    from fastapi import FastAPI

    from core.release.routes import router

    app = FastAPI()
    app.include_router(router)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)
    return server, task


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break-contrast", action="store_true", help="inject a 4.1:1 theme token; the Builder must fix it")
    ap.add_argument("--cold", action="store_true", help="create a fresh sandbox instead of reusing RELEASE_SANDBOX_ID")
    ap.add_argument("--rev", type=int, default=None)
    ap.add_argument("--spec", default="contracts/fixtures/reyes_spec.json")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--delete", action="store_true", help="delete the sandbox afterwards (use with --cold)")
    args = ap.parse_args()

    arize = register_arize()
    from core.llm import llm
    from core.release import run_release
    from core.release.anchor_qa import AnchorQA
    from core.release.daytona_svc import DaytonaBuilder
    from core.release.evals import ReleaseEvals
    from core.release.pipeline import BACKGROUND, LAST_TIMINGS

    if args.cold:
        os.environ.pop("RELEASE_SANDBOX_ID", None)
        os.environ["RELEASE_COLD"] = "1"
    model_on = os.environ.get("VILLAGE_LLM", "off") != "off"
    spec = json.loads((ROOT / args.spec).read_text())
    vid = spec["village"]["id"]
    rev = args.rev or (3 if args.break_contrast else int(spec.get("rev", 1)))
    local = f"http://127.0.0.1:{args.port}"
    server, server_task = await serve_local(args.port)
    daytona = DaytonaBuilder(preview=not args.no_preview)
    anchor = AnchorQA()
    t0 = time.perf_counter()

    async def broadcast(village: str, kind: str, payload: dict) -> None:
        dt = time.perf_counter() - t0
        if kind == "release":
            r = payload["receipt"]
            cur = [s for s in r["stages"] if s["status"] in ("running", "passed", "failed")]
            s = cur[-1] if cur else r["stages"][0]
            print(f"  +{dt:5.1f}s {r['id']} a{r['attempt']} {s['name']:<13} {s['status']:<8} {s['details'].get('summary', '')}", flush=True)
        elif kind == "build_log":
            print(f"  +{dt:5.1f}s   log[{payload['level']}] {payload['line'][:150]}", flush=True)

    print(f"arize={arize} model={'on' if model_on else 'off'} sandbox={'cold' if args.cold else ('id' if os.environ.get('RELEASE_SANDBOX_ID') else 'warm-label')} rev={rev} inject={'contrast' if args.break_contrast else None}")
    history: list[dict] = []
    try:
        receipt = await run_release(
            vid, spec, rev, broadcast=broadcast, llm=llm if model_on else None, daytona=daytona, anchor=anchor,
            evals=ReleaseEvals(llm=llm if model_on else None), local_base=local,
            inject="contrast" if args.break_contrast else None, history=history,
        )
        total = time.perf_counter() - t0
        # Anchor MP4: fetched in the background after the session ends; wait for it and serve it once.
        t_rec = time.perf_counter()
        if BACKGROUND:
            await asyncio.wait(list(BACKGROUND), timeout=120)
        qa_det = receipt["stages"][3]["details"]
        rec_url = qa_det.get("video_url")
        print(f"\nAnchor MP4: {'none' if not rec_url else rec_url} (+{time.perf_counter() - t_rec:.1f}s after release, "
              f"fetch {anchor.last_timings.get('recording_fetch')} ms, {anchor.last_timings.get('recording_bytes')} bytes)")
        if rec_url:
            import httpx

            async with httpx.AsyncClient() as c:
                resp = await c.get(local + rec_url.split(".net", 1)[-1] if ".net/" in rec_url else rec_url)
                print(f"  served by GET /releases/{{rel}}/qa/qa.mp4: {resp.status_code} {resp.headers.get('content-type')} {len(resp.content)} bytes")
    finally:
        total = locals().get("total") or (time.perf_counter() - t0)
        server.should_exit = True
        await asyncio.wait_for(server_task, 5)
    timings = dict(LAST_TIMINGS.get(vid, {}))
    timings["wall_total"] = int(total * 1000)
    print("\nReceipts:")
    for r in history:
        print(f"  {r['id']} attempt={r['attempt']} trigger={r['trigger']} result={r['result']} live_rev={r['live_rev']} "
              f"stages={'/'.join(s['status'][0].upper() for s in r['stages'])} trace={r.get('trace_id')}")
        for s in r["stages"]:
            if s["details"].get("summary"):
                print(f"     {s['name']:<13} {s['status']:<7} {s['details'].get('duration_ms', '')!s:>6} ms  {s['details']['summary']}")
    qa = receipt["stages"][3]["details"]
    print(f"\nAnchor: session={qa.get('anchor_session_id')} live_view={'yes' if qa.get('live_view_url') else 'no'}")
    print("\nTimings (ms):")
    for k, v in timings.items():
        print(f"  {k:<18} {v}")
    print(f"\nSANDBOX_ID={getattr(daytona._sb, 'id', None)}")
    out = ROOT / "var" / "releases" / f"smoke_{int(time.time())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"timings_ms": timings, "receipts": history, "anchor_timings": anchor.last_timings,
                               "daytona_timings": daytona.last_timings}, indent=1, ensure_ascii=False))
    print(f"wrote {out.relative_to(ROOT)}")
    try:
        from opentelemetry import trace

        trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]
    except Exception:
        pass
    await daytona.close(delete=args.delete)
    return 0 if receipt["result"] == "released" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
