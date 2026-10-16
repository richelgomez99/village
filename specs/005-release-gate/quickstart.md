# Quickstart: Release gate (FS-5)

For the release and evals lanes. Work in `../village-release` / `../village-evals` worktrees on `lane/release` / `lane/evals`. Build against fixtures; mock what isn't merged.

## 0. Prerequisites (from tonight)
```bash
uv run smoke/00_env_check.py                 # DAYTONA_API_KEY, ANCHORBROWSER_API_KEY, ARIZE_*, AWS_* or ANTHROPIC_API_KEY, TUNNEL_URL set
uv run smoke/04_daytona_snapshot.py          # snapshot village-kit exists (state=active)
uv run smoke/05_anchor.py --no-agent         # session create + live view work; note create latency
uv run smoke/07_arize.py                     # spans land in project `village`
```

## 1. Run the pipeline offline (fakes, model off)
```bash
uv run pytest core/release evals/release -q        # FakeDaytona / FakeAnchor / FakeJudge; receipts validate against release.schema.json
```

## 2. Run it for real against the fixture spec
```bash
uv run uvicorn core.app:app --port 8787            # VILLAGE_LAYERS=core,gate,kit,release  RELEASE_PREWARM=1
curl -s localhost:8787/health | jq .prewarm        # {"sandbox":"ready","anchor":"ready"} after ~10 s
curl -s -X POST localhost:8787/villages/v_reyes/releases -H "x-control-token: $CONTROL_TOKEN" -d '{"rev":4}'
# watch: Control Room /control → ReleaseStrip; or
curl -s localhost:8787/villages/v_reyes/releases -H "x-control-token: $CONTROL_TOKEN" | jq '.receipts[0] | {result, live_rev, stages: [.stages[] | {name, status, summary: .details.summary}]}'
open "$TUNNEL_URL/v/v_reyes/?m=$ELDER_TOKEN"      # rev 4 served from Core
```

## 3. Caught-and-fixed pair + second village (do this once before 13:40; it is the V3 fallback material)
```bash
scripts/caught_and_fixed.sh v_reyes                # POST rev 3 with inject_failure=contrast → blocked; repair → rev 4 released
scripts/caught_and_fixed.sh v_w147 --rev 2 --no-inject
ls var/releases/v_reyes/r4/qa/                     # report.json a1..a4 png, qa.mp4 (after ≤60 s)
cat var/evals/releases/rel_reyes_r4.json | jq '.[] | {name, label, score, passed}'
```

## 4. Pre-warm and budget check (13:30)
```bash
curl -s -X POST localhost:8787/release/prewarm -H "x-control-token: $CONTROL_TOKEN"   # or restart Core with RELEASE_PREWARM=1
time scripts/caught_and_fixed.sh v_reyes --rev 4 --no-inject      # expect [MEASURE] ≤ 45 s warm
```

## 5. Acceptance
```bash
acceptance/v3.sh        # see tasks.md T024 for what it checks; green → tag V3
```

## Where things are
- Receipts: `var/releases/<village>/r<rev>/`, SurrealDB `release` table, `GET /villages/{id}/releases`.
- Evals: `var/evals/releases/<rel>.json`, Arize project `village` → trace `receipt.trace_id` → `eval.*` columns.
- Anchor: the receipt's `live_view_url` (safe to show) and `video_url`.
- Logs: `var/releases/<village>/r<rev>/build.log` and the Control Room build log panel.

## Gotchas (from research and smoke results)
- The sandbox cannot call Core; never write a floor test that fetches `TUNNEL_URL`.
- `cdp_url` contains the API key: never log it; `live_view_url` is safe.
- `browser.close()` only disconnects: always `delete_session` in `finally`, or the Free plan's 5-session cap bites.
- Build Vite with `base: './'` and `server.allowedHosts`, bind `0.0.0.0`.
- `force_flush()` returning `True` does not prove Arize accepted spans; check the UI once.
- Never infer test results from an exit code; read `vitest.json`.
