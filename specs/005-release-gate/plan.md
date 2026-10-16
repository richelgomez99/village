# Implementation Plan: Release gate (FS-5)

**Branch**: `005-release-gate` | **Date**: 2026-10-16 | **Spec**: `specs/005-release-gate/spec.md` | **Version**: V3

## Summary

One entry point, `release.run(village, rev) -> Receipt`, drives six stages: validate spec → build + test the per-village bundle in a Daytona sandbox (snapshot `village-kit`, streamed logs) → download `dist.tgz` and serve the candidate from Core → Anchor QA at 390×844 over CDP against a shadow village → four in-process evals logged to Arize with a local mirror → blue/green switch of `published_rev`. Pre-warmed sandbox + Anchor session keep the live rebuild inside a 60 s budget; recorded receipts are the fallback. Everything is a span under `session.id=village-<id>`.

## Technical context

- **Language**: Python 3.13 (`uv`), FastAPI, httpx, pydantic v2, pytest. Kit side: Vite + React + TS + vitest (runs only inside the sandbox).
- **SDKs**: `daytona` (`AsyncDaytona`), `anchorbrowser>=1.0.1` (`AsyncAnchorbrowser`) + `playwright` (async, `connect_over_cdp`, no `playwright install`), `arize` + `arize-otel` + `openinference-instrumentation`, `pandas` (for `update_evaluations`), `anthropic` via `core/llm.py`.
- **Storage**: SurrealDB Cloud tables `release`, `eval_record`, `village.{spec_rev, published_rev}`; filesystem `var/releases/<village>/r<rev>/{bundle,dist,qa,build.log}`; `var/evals/releases/<rel>.json`.
- **Testing**: pytest with fakes (`FakeDaytona`, `FakeAnchor`, `FakeJudge`) so the pipeline test runs model-off and offline; one opt-in integration test per SDK (`-m live`).
- **Constraints**: pipeline ≤ 60 s with warm pool; sandbox never calls Core (egress); Free-plan Anchor concurrency 5; Tier-1 Daytona RAM ≈ 2 medium sandboxes (so the pool holds exactly one).
- **Flags**: `VILLAGE_LAYERS` must include `release`; `RELEASE_PREWARM=1`.

## Constitution check

- I: no imports from `core/gate/`; QA goes through public routes only. ✅
- II: `release.run` never publishes a `trigger=proposal` rev unless called with `publish=True` by FS-6 after approval; default for proposals is stop at `live: pending`. ✅
- III: receipt carries ids/urls/explanations; repairs are new receipts (`repair_of`). ✅
- IV: six stages; `published_rev` moves only on `released`. ✅
- V: floor tests generated from D8 constants in `sandbox/floor/`; `safety_copy` exact-match. ✅
- VI: consumes contracts unchanged; three additions requested in `contracts/README.md` (listing endpoint, manual run endpoint, candidate path). ✅
- VII: behind flag; `acceptance/v3.sh`. ✅
- VIII: spans everywhere; `[MEASURE]` placeholders. ✅
- IX: static from Core, in-process evals, deterministic Playwright. ✅

## Project structure

```text
specs/005-release-gate/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
└── contracts/README.md

core/release/                      # lane: release
├── __init__.py                    # run(), prewarm(), get_receipts()
├── pipeline.py                    # stage runner, per-village lock, budget timer, receipt streaming
├── bundle.py                      # VillageSpec → bundle files (theme, i18n, manifest, custom, floor tests)
├── daytona_svc.py                 # AsyncDaytona: pool, upload, session command, logs, download
├── anchor_svc.py                  # AsyncAnchorbrowser + Playwright: pool, QA flows, screenshots, recording
├── serve.py                       # /v/{id}/ and /v/{id}/r/{rev}/ static mounts; published_rev switch
├── receipts.py                    # Receipt pydantic model (= release.schema), persistence, ledger event
├── repair.py                      # floor autofix (tone → floor ink) + builder repair hook
└── tests/                         # pipeline_test.py (fakes), bundle_test.py, serve_test.py, receipts_test.py

sandbox/                           # lane: release (template copied into the sandbox per build)
├── build.sh                       # cp template → app, copy bundle, vite build, vitest --reporter=json, tar dist
├── vite.config.ts                 # base './', server.allowedHosts: true, vite-plugin-pwa
└── floor/                         # test templates rendered by bundle.py with the spec's values
    ├── contrast.test.ts  sizes.test.ts  safety_colors.test.ts  actions.test.ts  render.test.tsx
    └── floor.constants.ts         # D8: #A8331A #2E6F42 amber, 7:1 / 4.5:1, 88px / 28px / 48px

evals/release/                     # lane: evals
├── __init__.py                    # run(receipt, artifacts) -> list[EvalRecord]; log_to_arize(); mirror()
├── spec_coverage.py  safety_copy.py  translation_backcheck.py  elder_accessibility.py
├── judge.py                       # Claude judge with 20 s budget, Haiku retry, EVALUATOR spans
└── tests/                         # each eval with FakeJudge; exact-match tests against policy_cases.md

core/obs/                          # lane: evals (shared tracing helpers, already planned in FLEET.md)
scripts/caught_and_fixed.sh        # r3 (inject contrast) → repair → r4; then v_w147 rev 2
acceptance/v3.sh
```

## Stage-by-stage design with exact SDK sequences

### Stage 0 — `spec` (≈0.2 s)
1. Load spec rev from SurrealDB (`spec_rev` table); validate with the pydantic model + `contracts/validate.py` invariants.
2. `bundle.build(spec) -> dict[path, bytes]`: `spec.json`, `theme.json` (village layer only; floor tokens come from the kit), `i18n/{es,en}.json`, `manifest.webmanifest`, `custom/<Name>.tsx` (from `custom_components[].config`, PillOrganizer template), `tests/floor/*.test.ts(x)` rendered from `sandbox/floor/` with the spec's role keys, element ids, safety strings and languages.
3. `inject_failure="contrast"` (demo only): set elder `BigButton` tone to `info` in the bundle copy, not in the stored spec. Receipt stage summary: "VillageSpec valid (3 views, 1 custom component)".

### Stage 1 — `daytona_build` (warm ≈ 8–15 s · cold +3–6 s · `[MEASURE]`)
```python
d = AsyncDaytona()                                   # DAYTONA_API_KEY, DAYTONA_TARGET
sb = pool.take_sandbox() or await d.create(
    CreateSandboxFromSnapshotParams(snapshot=settings.DAYTONA_SNAPSHOT,   # "village-kit"
        auto_stop_interval=0, ttl_minutes=360,
        labels={"village": vid, "rev": str(rev), "release": rel}), timeout=120)
await sb.fs.upload_files([FileUpload(source=b, destination=f"/home/daytona/bundle/{p}") for p, b in bundle.items()]
                         + [FileUpload(source=BUILD_SH, destination="/home/daytona/bundle/build.sh")])
sid = f"build-{rel}"; await sb.process.create_session(sid)
cmd = await sb.process.execute_session_command(sid, SessionExecuteRequest(command="bash /home/daytona/bundle/build.sh", run_async=True))
await sb.process.get_session_command_logs_async(sid, cmd.cmd_id, on_stdout, on_stderr)   # non-blocking callbacks → hub.control(build_log)
st = await sb.process.get_session_command(sid, cmd.cmd_id)   # st.exit_code
```
`build.sh` (in `sandbox/`): `set -uo pipefail; rm -rf ~/app && cp -r /opt/kit-template ~/app && cp -r ~/bundle/. ~/app/ && cd ~/app && npx vite build --logLevel warn; echo BUILD_EXIT=$?; npx vitest run --reporter=json --outputFile=vitest.json --reporter=dot; echo VITEST_EXIT=$?; tar czf dist.tgz -C dist .` — exit codes are read from the log markers, so a failing vitest still leaves `vitest.json`. Stage `daytona_build` = `BUILD_EXIT=0`; details: `sandbox_id`, `duration_ms`, optional `preview_url` = `(await sb.create_signed_preview_url(4173, expires_in_seconds=86400)).url` only when `RELEASE_PREVIEW_URL=1` (talking point; not on the demo path).

### Stage 2 — `tests` (≈3–6 s, inside the same command)
`vitest.json = await sb.fs.download_file("/home/daytona/app/vitest.json")` → `tests_passed/failed`, `failures[]` (`"<file> › <name>"`, max 20, 300 chars each). Summary for the strip is the first failure's assertion message (e.g. "contrast 4.1:1 on elder view (needs 7:1)"). On failure: stop, mark the rest `skipped`, `result=blocked`, delete the sandbox (keep the log tail), and if `trigger != repair` and `attempt < 3` hand the failures to `repair.py` (floor autofix first, builder `patch_app` repair second) which returns a new rev for the caller to release as `trigger=repair`.

### Stage 3 — `live` staging and `anchor_qa` (warm ≈ 10–14 s · `[MEASURE]`)
1. `tgz = await sb.fs.download_file("/home/daytona/app/dist.tgz")` → extract to `var/releases/<vid>/r<rev>/dist`; verify `index.html`. Mount `/v/{id}/r/{rev}/` (candidate) immediately. Sandbox: `await sb.delete()` unless `RELEASE_KEEP_SANDBOX=1`; pool refills in the background.
2. Shadow village: `services.reset_village(f"{vid}_qa", spec_rev=rev, seed="lid_scan_sequence")` → returns `qa_slot_url`, `qa_elder_token`, `qa_helper_token`. Events written there carry `source{kind: system, ref: release-qa}`. FS-6's detector and the Control Room counters ignore `*_qa`.
3. Anchor:
```python
ab = AsyncAnchorbrowser()                           # ANCHORBROWSER_API_KEY
s = pool.take_anchor() or (await ab.sessions.create_session(
        browser={"viewport": {"width": 390, "height": 844}},
        session={"recording": {"active": True}, "timeout": {"max_duration": 30, "idle_timeout": 10}, "tags": ["village-release", vid]})).data
hub.control(vid, "qa", {release_id, rev, stage: "anchor_qa", status: "running", live_view_url: s.live_view_url + "&show_cursor=1"})
async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp(s.cdp_url)          # never log cdp_url
    ctx = browser.contexts[0]; page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    base = f"{settings.TUNNEL_URL}"
    await page.goto(f"{base}/s/{qa_slot}", wait_until="networkidle", timeout=15_000)      # A1 first scan
    await expect_text(page, "Anotado");                       await shot("a1_scan_recorded")
    await page.goto(f"{base}/s/{qa_slot}", wait_until="networkidle")                       # A2 second scan
    await expect_text(page, "ya se anotó");                   await shot("a2_scan_report")
    await page.goto(f"{base}/v/{vid}/r/{rev}/?village={vid}_qa&m={qa_helper_token}", wait_until="networkidle")
    ver = await services.start_verification(f"{vid}_qa", claimed_member="m_marco", amount=2000, source={"kind":"system","ref":"release-qa"})
    await page.get_by_role("button", name=re.compile("wasn't me|No fui yo")).click(timeout=8_000)   # A3 prompt answered
    await expect_text(page, re.compile("denied|No era"));     await shot("a3_prompt_denied")
    await page.goto(f"{base}/v/{vid}/r/{rev}/?village={vid}_qa&m={qa_elder_token}", wait_until="networkidle")
    elder_png = await page.screenshot(full_page=True);        await shot("a4_elder_view")          # A4 for the vision judge
await ab.sessions.delete_session(s.id)                       # stops billing; recording becomes available after this
asyncio.create_task(fetch_recording(s.id, rel))              # poll recordings.fetch_primary_recording ≤ 60 s → qa.mp4 → receipt update
```
Assertion helper: `expect_text` waits ≤ 8 s; on timeout it screenshots and raises `QAAssertion(name, seen_text[:200])`. Unreachable app (HTTP ≥ 500, DNS, or 15 s timeout on the first `goto`) → `error=app_unreachable:<detail>`. Session create 429/connect failure → one retry (≤ 5 s) → `error=anchor_unavailable`.
QA report `var/releases/<vid>/r<rev>/qa/report.json` + PNGs, served at `/releases/{rel}/qa/` (= `evidence_url`).

### Stage 4 — `arize_evals` (≈5–10 s, evals in parallel · `[MEASURE]`)
```python
with tracer.start_as_current_span("release_evals", openinference_span_kind="EVALUATOR"):
    recs = await asyncio.gather(spec_coverage(spec), safety_copy(spec, kit_strings), translation_backcheck(spec), elder_accessibility(elder_png))
df = pd.DataFrame([{"context.span_id": span_ids["anchor_qa" if r.name == "elder_accessibility" else "release.run"],
                    f"eval.{r.name}.label": r.label, f"eval.{r.name}.score": r.score, f"eval.{r.name}.explanation": r.explanation} for r in recs])
ArizeClient().spans.update_evaluations(space_id=SPACE, project_name=PROJECT, dataframe=df)   # 5 s timeout, failure is logged not fatal
mirror(rel, recs)   # var/evals/releases/<rel>.json + eval_record rows
```
- `spec_coverage`: judge prompt from `research/arize-bedrock.md §2`: description + views → `covered|missing`; threshold 1.0 (label-level). Model `BEDROCK_SONNET_MODEL`.
- `safety_copy`: (a) deterministic: every `say_key` text in `spec.voice_lines` and the kit's `result` strings == `policy_cases.md` lines (parsed table) → any diff = fail; (b) judge over all other visible strings: no dosing advice, no money movement, no account details → `safe|unsafe`; threshold 1.0.
- `translation_backcheck`: for each es safety line, Haiku back-translates to en; Sonnet judge scores equivalence 0..1 against the reviewed en line; stage score = min; threshold 0.9; failing keys → `failures[]` and the repair substitutes the simpler reviewed text.
- `elder_accessibility`: Sonnet with an image block (base64 PNG from A4) scores: one primary action, large text, visible contrast, no clutter → 0..1; threshold 0.8.
- Judge budget: 20 s → retry Haiku 10 s → `label=judge_timeout, score=None`; stage passes iff deterministic checks pass and `RELEASE_EVALS_STRICT=0`.

### Stage 5 — `live` (≈0.2 s)
`village.published_rev = rev` (CAS on the previous value), remount `/v/{id}/` → `r<rev>/dist` (symlink swap), `hub.snapshot_all(vid)` so connected phones reload the view spec with `rev`, write `event{kind: release}`, stream the final receipt. For `trigger=proposal` and `publish=False` the stage stays `pending` and the receipt `result=in_progress`; FS-6 calls `release.publish(rel)` after approval.

## Timing budget (warm pool)

| Stage | Budget | Fallback if exceeded |
|---|---|---|
| spec + bundle + upload | 1.5 s | — |
| daytona_build (vite) | 15 s | log says "slow build"; continue |
| tests (vitest) | 6 s | — |
| download + mount + shadow reset | 2 s | — |
| anchor_qa | 14 s | after 25 s abort with `app_unreachable|timeout` |
| arize_evals | 10 s | judge timeout rules |
| live | 0.5 s | — |
| **Total** | **≈ 49 s** (hard `RELEASE_BUDGET_S=60`) | at 60 s: `control{reasoning, source: release, note: "over budget; showing recorded receipts"}`; Control Room shows the r3/r4 pair; the run finishes anyway |

## Live vs recorded

| Live on stage | Recorded before 13:40 |
|---|---|
| Daytona build + tests (logs stream), Anchor live view iframe (`show_cursor=1`), eval scores arriving, `published_rev` flip, phones re-snapshot | Anchor MP4 (always after session end), the caught-and-fixed r3/r4 receipts, the `v_w147` receipt, draft video of the strip |

## Pre-warm routine (13:30, `release.prewarm()`; also at Core boot when `RELEASE_PREWARM=1`)
- Sandbox: `d.create(... labels={"village": "prewarm"})`; heartbeat task `await sb.refresh_activity()` every 5 min (`auto_stop_interval=0` anyway); pool size 1; after `take_sandbox()` a new one is created in the background.
- Anchor: `create_session(... timeout={"max_duration": 60, "idle_timeout": 30})`; keep one CDP connection open and run `page.evaluate("1")` every 60 s; `take_anchor()` hands over the session id; replacement created in the background. Kill both on shutdown.
- `GET /health` reports `prewarm: {sandbox: "ready"|"miss", anchor: "ready"|"miss", ages_s}`.

## Environment variables (added to `.env.example` by the orchestrator)

```
DAYTONA_API_KEY DAYTONA_TARGET DAYTONA_SNAPSHOT=village-kit
ANCHORBROWSER_API_KEY
ARIZE_SPACE_ID ARIZE_API_KEY ARIZE_PROJECT_NAME=village
AWS_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN BEDROCK_SONNET_MODEL BEDROCK_HAIKU_MODEL ANTHROPIC_API_KEY
TUNNEL_URL                       # public base the Anchor browser opens
RELEASE_DIR=var/releases  RELEASE_PREWARM=1  RELEASE_BUDGET_S=60  RELEASE_EVALS_STRICT=0
RELEASE_KEEP_SANDBOX=0  RELEASE_PREVIEW_URL=0  RELEASE_JUDGE_TIMEOUT_S=20
VILLAGE_LAYERS=…,release
```

## Risks and mitigations
- Snapshot without the real kit source → T003 rebuilds `village-kit-v2` with `kit/` at `/opt/kit-template`; `DAYTONA_SNAPSHOT` switches.
- Vision on Mantle unverified → `elder_accessibility` tries Mantle, falls back to `Anthropic()`; if both fail it is `judge_timeout`-shaped (`label=judge_unavailable`).
- Anchor can't reach the Funnel at the venue → stage fails honestly; the demo shows recorded receipts; FS-6's live patch still works because publishing after approval does not require QA to have run live (receipt would be `blocked`, so the fallback is to publish the pre-verified r5 from the afternoon run, see FS-6 plan).
