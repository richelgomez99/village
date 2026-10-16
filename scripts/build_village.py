#!/usr/bin/env python
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

from core.builder import FoundingInput, FoundingOptions, ask, found
from core.builder.services_stub import MemoryServices
from core.builder.validate import validate_spec


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--description-from", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--kind", choices=["care", "block"], default="care")
    parser.add_argument("--mode", choices=["full", "fast", "fixture"], default="fixture")
    parser.add_argument("--out", type=Path, default=Path("data/builder/out/reyes"))
    parser.add_argument("--time", action="store_true")
    parser.add_argument("--warm", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--llm", choices=["off", "on"], default="off")
    parser.add_argument("--prompt", choices=["local", "hub"], default="local")
    parser.add_argument("--ask")
    parser.add_argument("--from", dest="from_dir", type=Path)
    parser.add_argument("--village-id", default="v_reyes")
    args = parser.parse_args()

    if args.warm:
        print("warm OK (fixture/model-off path)")
        return 0

    svc = MemoryServices()
    if args.ask:
        if args.from_dir:
            decisions_path = args.from_dir / "decisions.jsonl"
            if decisions_path.exists():
                for line in decisions_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        svc.decisions.append(json.loads(line))
        answer = await ask(args.ask, args.village_id, svc)
        print(answer.answer)
        for citation in answer.citations:
            print(f"- {citation['kind']}:{citation['id']} {citation.get('label', '')}")
        return 0 if answer.citations or "not have a record" in answer.answer or "cannot reveal" in answer.answer.lower() else 1

    source = json.loads(args.description_from.read_text(encoding="utf-8")) if args.description_from else {}
    description_obj = source.get("demo_spoken_description", "")
    description = args.text or (description_obj.get("text") if isinstance(description_obj, dict) else description_obj)
    if not description:
        raise SystemExit("--text or --description-from with demo_spoken_description is required")
    t0 = time.perf_counter()
    run = await found(
        FoundingInput(description=description, language="en", channel="text", kind=args.kind),
        village_id=args.village_id,
        services=svc,
        options=FoundingOptions(mode=args.mode, prompt=args.prompt, strict=args.strict, llm=args.llm),
    )
    report = validate_spec(run.spec)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "spec.json").write_text(json.dumps(run.spec, indent=2, ensure_ascii=False), encoding="utf-8")
    for role, view in run.spec["views"].items():
        (args.out / f"view_{role}.json").write_text(json.dumps(view, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / "decisions.jsonl").write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in svc.decisions), encoding="utf-8")
    (args.out / "reasoning.jsonl").write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in svc.frames), encoding="utf-8")
    print(f"== blueprint ({len(svc.frames)} frames)")
    for frame in svc.frames:
        payload = frame.get("payload", {})
        if payload.get("text"):
            print(f"  [{payload.get('kind')}] {payload['text']}")
    for role, result in run.roles.items():
        print(f"== {role}: {result.status} attempts={result.attempts} ttft={result.ttft_ms} total={result.ms} ms cache_read={result.cache_read_tokens}")
    print("== validate:", "OK" if report.ok else report.errors)
    print(f"== total {time.perf_counter() - t0:.1f}s trace={run.trace_id}")
    return 0 if report.ok else 1


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
