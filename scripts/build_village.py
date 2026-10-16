#!/usr/bin/env python
"""Found a village from a conversation against MemoryServices (no core needed).

  uv run python scripts/build_village.py --llm off --replay                 # Reyes intake A0–A12
  uv run python scripts/build_village.py --llm off --replay --kind block    # West 147th intake
  uv run python scripts/build_village.py --llm off --replay --resume 8      # stage: replay to 8/10, then stdin
  uv run python scripts/build_village.py --llm off --text "Mom forgets her pills" --time
  uv run --with boto3 python scripts/build_village.py --llm on --replay --time --ask "why Marco and not Lucía?"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.builder.ask import ask  # noqa: E402
from core.builder.founding import FoundingInput, demo_options, found, replay_input  # noqa: E402
from core.builder.llm_port import get_llm  # noqa: E402
from core.builder.registry import kind_config  # noqa: E402
from core.builder.services_stub import MemoryServices  # noqa: E402
from core.builder.validate import validate_spec  # noqa: E402


class PrintingServices(MemoryServices):
    def __init__(self, quiet: bool) -> None:
        super().__init__()
        self.quiet = quiet

    async def broadcast_control(self, village_id, frame):  # type: ignore[no-untyped-def]
        await super().broadcast_control(village_id, frame)
        if self.quiet:
            return
        p = frame["payload"]
        if frame["kind"] == "reasoning":
            print(f"  [{p['source']}/{p['kind']}] {p['text']}")
        elif frame["kind"] == "ledger" and p["status"] not in ("running", "queued"):
            print(f"  [ledger] {p['status']:8} {p['what']} · {p.get('result', '')}"[:220])


async def amain() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["care", "block"], default="care")
    ap.add_argument("--llm", choices=["off", "on"], default="off")
    ap.add_argument("--replay", action="store_true", help="play the recorded intake transcript for --kind")
    ap.add_argument("--resume", type=int, help="replay until the meter reaches N, then read answers from stdin")
    ap.add_argument("--text", help="opener only (no transcript)")
    ap.add_argument("--dailymed", choices=["live", "fixture", "off"], default="live")
    ap.add_argument("--time", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--ask", help="ask the Explainer a question after the draft")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.replay or args.resume:
        inp, answers = replay_input(kind=args.kind)
    else:
        inp, answers = FoundingInput(description=args.text or "Mom forgets her pills.", kind=args.kind), []
    svc = PrintingServices(args.quiet)
    llm_client = get_llm(args.llm, "sonnet") if args.llm == "on" else None
    opts = demo_options(args.kind, llm=args.llm, replay=answers or None, resume=args.resume, dailymed=args.dailymed, llm_client=llm_client)
    if args.resume:
        opts.clarify_wait_s = 600
    vid = kind_config(args.kind)["village_id"]

    async def stdin_feeder() -> None:
        from core.builder.founding import SESSIONS, answer

        loop = asyncio.get_running_loop()
        while True:
            s = SESSIONS.get(vid)
            if s and s.waiting and s.question is not None and s.answers.empty():
                q = s.question
                line = await loop.run_in_executor(None, lambda: input(f"\n{getattr(q, 'text', q)}\n> "))
                answer(vid, line)
            await asyncio.sleep(0.05)

    t0 = time.perf_counter()
    feeder = asyncio.create_task(stdin_feeder()) if args.resume else None
    run = await found(inp, village_id=vid, services=svc, options=opts)
    if feeder:
        feeder.cancel()
    total = time.perf_counter() - t0
    spec = svc.specs[vid]
    report = validate_spec(spec)
    out = args.out or ROOT / "data" / "builder" / "out" / args.kind
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    (out / "run.json").write_text(json.dumps(run.summary(), ensure_ascii=False, indent=1, default=str))
    (out / "frames.jsonl").write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in svc.frames))
    print(f"\nvalid={report.ok} views={list(spec['views'])} people={len(spec['blueprint']['people'])} needs={len(spec['blueprint']['needs'])} turns={len(run.turns)} ledger={len(run.ledger)} decisions={len(svc.decisions)}")
    print(f"roles={ {r: v.status for r, v in run.roles.items()} } llm={run.timings.get('llm')}")
    if not report.ok:
        print("\n".join(report.errors[:10]))
    if args.time:
        t = run.timings
        print(f"timings: blueprint_ttft_ms={t.get('blueprint_ttft_ms')} blueprint_ms={t.get('blueprint_ms')} render_role_ms={t.get('render_role_ms')} render_ms={t.get('render_ms')} dailymed_ms={t.get('dailymed_ms')} total_ms={t.get('total_ms')} wall_s={total:.1f}")
    if args.ask:
        res = await ask(vid, args.ask, services=svc, llm=llm_client)
        print(f"\nask: {args.ask}\n→ {res.answer}\n  citations={[c['id'] for c in res.citations]} dropped={res.dropped_citations}")
    print(f"wrote {out}/spec.json")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
