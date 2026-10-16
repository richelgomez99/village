# Quickstart: run the builder on the Reyes description

Goal: from a shell, turn Ana's sentence into a blueprint and three role specs, validate them against the contract, and print timings. No Core process, no SurrealDB, no WebSocket: the script drives `core.builder` directly with an in-memory `services` stub.

## Prerequisites
```bash
cp .env.example .env            # AWS_* (Mantle) or ANTHROPIC_API_KEY; ARIZE_* optional
uv run smoke/01_llm.py          # Sonnet/Haiku reachable, note TTFT
uv run --with jsonschema --with pyyaml --with openapi-spec-validator python contracts/validate.py   # OK contract 1.0.0
```

## Run
```bash
uv run scripts/build_village.py --description-from data/villages/reyes_family.json \
    --out data/builder/out/reyes --time
# flags: --text "…" (literal description) | --kind care|block | --mode full|fast|fixture
#        --warm (one call per tool to compile grammars; prints nothing else)
#        --strict (set strict:true on render_app; reports 400 and falls back)
#        --llm off (forces the template path)  --prompt local|hub
```
The script (`scripts/build_village.py`, ~80 lines):
```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["anthropic[bedrock]>=1.0", "pydantic>=2.7", "jsonschema", "python-dotenv", "arize>=8.59"]
# ///
import asyncio, json, sys, time, argparse
from core.builder import found, FoundingInput, FoundingOptions
from core.builder.validate import validate_spec
from core.services_stub import MemoryServices           # records control frames + decisions in memory

async def main(a):
    svc = MemoryServices()
    src = json.load(open(a.description_from)) if a.description_from else None
    inp = FoundingInput(description=a.text or src["demo_spoken_description"],
                        language="en", channel="text", members=[], needs=[])
    t0 = time.perf_counter()
    run = await found(inp, village_id=a.village_id, services=svc,
                      options=FoundingOptions(mode=a.mode, prompt=a.prompt, strict=a.strict))
    print(f"\n== blueprint ({run.blueprint.ms} ms, {len(svc.frames)} frames)")
    for f in svc.frames: print(f"  [{f['payload']['kind']}] {f['payload']['text']}")
    for role, r in run.roles.items():
        print(f"== {role}: {r.status} attempts={r.attempts} ttft={r.ttft_ms} total={r.ms} ms cache_read={r.cache_read_tokens}")
    report = validate_spec(run.spec)                      # pydantic + invariants
    print("== validate:", "OK" if report.ok else report.errors)
    (a.out / "spec.json").write_text(json.dumps(run.spec, indent=2, ensure_ascii=False))
    for role, view in run.spec["views"].items():
        (a.out / f"view_{role}.json").write_text(json.dumps(view, indent=2, ensure_ascii=False))
    (a.out / "decisions.jsonl").write_text("\n".join(json.dumps(d) for d in svc.decisions))
    (a.out / "reasoning.jsonl").write_text("\n".join(json.dumps(f) for f in svc.frames))
    print(f"== total {time.perf_counter()-t0:.1f}s  trace={run.trace_id}")
    sys.exit(0 if report.ok else 1)
```
Then run the contract oracle on the output:
```bash
uv run --with jsonschema python -c "
import json, jsonschema, pathlib
from referencing import Registry, Resource
root = pathlib.Path('contracts/schemas')
reg = Registry().with_resources([(p.name, Resource.from_contents(json.load(open(p)))) for p in root.glob('*.json')])
schema = json.load(open(root/'village_spec.schema.json'))
jsonschema.Draft202012Validator(schema, registry=reg).validate(json.load(open('data/builder/out/reyes/spec.json')))
print('schema OK')"
```

## Expected output (shape; numbers are `[MEASURE]`)
```
== blueprint (…, 11 frames)
  [plan] Listening: 3 people, 3 problems
  [note] Found Carmen, 78, mother, lives alone in Queens. Spanish first.
  [note] Problem: "mixes up her pills" → evening pills (health)
  [note] Problem: "almost wired money to someone pretending to be Marco" → money
  [decision] Carmen: phone line + lid stickers (flip phone, pill mix-ups)
  [decision] Marco: checks money asks in his name
  …
== elder: validated attempts=1 ttft=… total=… ms cache_read=…
== coordinator: validated attempts=1 …
== helper: repaired attempts=2 …
== validate: OK
== total …s  trace=…
```

## Ask Village why (after a run)
```bash
uv run scripts/build_village.py --ask "Why does Carmen get a phone line and not an app?" --from data/builder/out/reyes
# prints the answer and the cited decision ids; exits 1 if any citation id is not in decisions.jsonl
```

## Block village (V3 pre-generation)
```bash
uv run scripts/build_village.py --description-from data/villages/block_blackout.json --kind block \
    --out data/builder/out/block --time && diff <(jq -S .views.coordinator data/builder/out/block/spec.json) <(jq -S .views.coordinator contracts/fixtures/block_spec.json) | head
```
