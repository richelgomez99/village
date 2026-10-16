# Feature Specification: Release gate (FS-5)

**Feature Branch**: `005-release-gate` · **Created**: 2026-10-16 · **Status**: Draft · **Version**: V3 (cutoff 13:40) · **Lanes**: release, evals

**Input**: PRODUCT.md FS-5 row; US-15 (pipeline), US-17, US-19; ARCHITECTURE-VALIDATION.md edges 10–13, 15 and §4 decisions 1, 4, 5; DECISIONS.md D7, D8, D13 (receipts, caught-and-fixed build), D15 (live rebuild, pre-warm, receipts fallback); LAYERS.md V3 row; FLEET.md release + evals lanes; `contracts/schemas/release.schema.json`.

**Plain words for the stage**: "nothing reaches her untested."

## Why this exists

Village generates software for one group of people. Constitution IV says every generated version is built and tested in a sandbox, used by a real browser at phone size, scored by evals, and only then published blue/green. FS-5 is that gate. It is also the mechanism the V4 Rebuild climax reuses (`release.run(village, rev)` is the single entry point), so its timing budget and its fallbacks are part of this spec, not FS-6's.

## User Scenarios & Testing

### User Story 1 — A leader sees release receipts for every version (US-17, Priority P1)

Ana (or a judge at the Control Room) sees, for each spec revision, a six-stage receipt: spec → Daytona build → tests → Anchor QA → Arize evals → live. Each stage shows a one-line summary, timing, and evidence (build log, test counts, Anchor recording + live view, eval scores). One receipt shows a build that **failed** (contrast 4.1:1 on the elder view) and the repaired revision that was released after it.

**Why P1**: this is the V3 acceptance in LAYERS.md and the sponsor story for Daytona, Anchor and Arize (SPONSORS.md). Without receipts V3 doesn't exist.

**Independent test**: run `release.run("v_reyes", 3, inject_failure="contrast")` then `release.run("v_reyes", 4, trigger="repair", repair_of=...)` against the fixture spec; the two receipts validate against `release.schema.json` and match the shape of its two examples; the Control Room strip renders both from `control{kind: release}` frames.

**Acceptance scenarios**

1. **Given** the Reyes spec rev 4 (fixture) and a running Core with `VILLAGE_LAYERS` including `release`, **When** `release.run("v_reyes", 4)` is called, **Then** a receipt with `id=rel_reyes_r4`, six stages in order, `result=released`, `live_rev=4` is persisted, every stage transition is streamed as `control{kind: release, payload.receipt}` to the Control Room, and `event{kind: release}` is written to the ledger with `source{kind: system, ref: release}`.
2. **Given** a bundle whose elder view has a `BigButton` with `tone=info` (contrast 4.1:1), **When** the pipeline runs, **Then** `daytona_build` passes, `tests` fails with `tests_failed=1` and the failure line `floor/contrast.test.ts › elder BigButton tone=info contrast 4.1:1 < 7:1`, stages `anchor_qa`/`arize_evals`/`live` are `skipped`, `result=blocked`, `live_rev` stays `previous_live_rev`, and no file under `/v/v_reyes/` changes.
3. **Given** the blocked receipt `rel_reyes_r3`, **When** the repair attempt runs (`attempt=2, trigger=repair, repair_of=rel_reyes_r3`) with the tone mapped to the floor ink, **Then** all six stages pass and `result=released`; the two receipts are linked and visible together on the strip as "caught → fixed → released".
4. **Given** a receipt in progress, **When** the Control Room reconnects, **Then** `GET /villages/{id}/releases` returns every receipt for the village (latest first) so the strip can re-render without waiting for the next frame.

### User Story 2 — A real browser uses the app at phone size before anyone else (US-15 pipeline, Priority P1)

Before a revision goes live, an Anchor browser session at 390×844 opens the candidate app through the public Funnel URL, runs the lid-scan flow twice (first "Anotado", second "ya se anotó" report), runs the verification-prompt flow ("That wasn't me"), takes a screenshot after every assertion, and records the session. The Control Room shows the live view while it runs.

**Why P1**: Anchor is the gate's hands (SPONSORS.md); the elder-accessibility eval needs its screenshot.

**Independent test**: with Core up and the candidate dist served at `/v/v_reyes/r/4/`, run `anchor_qa.run(village="v_reyes", rev=4)`; the QA report lists ≥4 assertions each with a PNG; `live_view_url` is reachable and iframe-able; after `delete_session` the MP4 is fetched within 60 s.

**Acceptance scenarios**

1. **Given** a pre-warmed Anchor session and the candidate dist served, **When** QA runs, **Then** the `anchor_qa` stage records `viewport=390x844`, `anchor_session_id`, `live_view_url` (no API key in it), and `evidence_url` pointing at the QA report; the shadow village `v_reyes_qa` has exactly the events the flow created and the demo village `v_reyes` has none.
2. **Given** the candidate app URL is not reachable from the Anchor browser (Funnel down, DNS blocked, or 5xx) within 15 s, **When** QA runs, **Then** the stage fails with `error=app_unreachable:<status|timeout>`, a screenshot of what the browser saw is kept, `result=blocked`, and the previous live rev stays live; the receipt summary says "Anchor couldn't reach the app", never "tests failed".
3. **Given** the Anchor session create or CDP connect fails (429 concurrency cap, expired pre-warm), **When** QA runs, **Then** one fresh session is attempted (≤5 s budget); if that also fails the stage is `failed` with `error=anchor_unavailable`, and the rest is `skipped`.

### User Story 3 — Evals score every version and a human can read why (Priority P2)

Four release evals run in-process and are logged to Arize against the release trace, with a local mirror: `spec_coverage` (judge), `safety_copy` (deterministic exact-match on reviewed safety lines + judge on free text), `translation_backcheck` (es safety lines back-translated and compared to the reviewed en originals), `elder_accessibility` (vision judge over the Anchor elder screenshot).

**Independent test**: `evals.release.run(receipt, screenshots)` over the fixture produces four `EvalRecord`s with scores in [0,1], thresholds, and explanations; `update_evaluations` is called once with four `eval.<name>.*` columns on the `anchor_qa`/`release.run` span ids; the same records are in `var/evals/releases/rel_reyes_r4.json`.

**Acceptance scenarios**

1. **Given** a passing bundle, **When** evals run, **Then** `eval_scores` and `eval_thresholds` appear in the `arize_evals` stage details, `trace_id` is set, and `evidence_url` links to the Arize trace.
2. **Given** an es safety line whose back-translation drifts from the reviewed en original (score < 0.9), **When** evals run, **Then** the stage fails with the line's `say_key` in `failures[]`, and the repair path substitutes the simpler reviewed text for that key (D8).
3. **Given** a judge call that exceeds its 20 s budget, **When** evals run, **Then** it is retried once on the Haiku model (10 s); if that also times out the eval is recorded as `label=judge_timeout, score=null`; the stage passes only if every deterministic check passed and `RELEASE_EVALS_STRICT=0` (demo default), and the strip says "judge timed out ×2"; with `RELEASE_EVALS_STRICT=1` the stage fails.

### User Story 4 — The same engine releases a different village (US-19, Priority P2)

The blackout block (`block_spec.json`, `v_w147`, rev 2) goes through the identical pipeline during the day; its receipt, build time and trace are shown in the 15 s "Anyone" reveal.

**Acceptance scenarios**

1. **Given** `block_spec.json`, **When** `release.run("v_w147", 2)` runs, **Then** a `released` receipt exists, `/v/v_w147/` serves three role views (coordinator, resident, volunteer), and the floor tests used the block's own i18n (en/es/zh) without any Reyes-specific fixture.

### User Story 5 — Pre-warm keeps the live rebuild under budget (Priority P2)

At 13:30 (`release.prewarm()`), one Daytona sandbox from `village-kit` and one Anchor session are created and kept alive by heartbeat so the V4 rebuild spends no time on cold starts.

**Acceptance scenarios**

1. **Given** pre-warm ran, **When** a release starts, **Then** the `daytona_build` stage starts within 1 s (no `create` call in the trace) and the `anchor_qa` stage connects over CDP within 1 s; a replacement sandbox/session is created in the background right after each is consumed.
2. **Given** the warm pool is empty or expired, **When** a release starts, **Then** it creates cold resources and the receipt notes `prewarm=miss` in the stage summary; the budget rises by ≈5–8 s but nothing else changes.
3. **Given** the whole pipeline exceeds `RELEASE_BUDGET_S=60`, **When** the Control Room is on the Rebuild beat, **Then** it switches the strip to the last recorded receipt pair (fallback) while the real run continues; when the real run ends its receipt replaces the fallback and the live patch (FS-6) still lands.

### Edge cases

- Daytona sandbox create fails (quota, rate limit, snapshot inactive): stage `daytona_build` fails with `error=sandbox_create:<reason>`; `result=blocked`; the on-call fix is `uv run smoke/04_daytona_snapshot.py`.
- `vite build` succeeds but `vitest.json` is missing (crash before the reporter wrote): `tests` fails with `error=no_report`; never infer "passed" from an exit code alone.
- The `dist.tgz` download is truncated or `index.html` missing after extraction: `live` fails, `published_rev` unchanged.
- Two releases for the same village overlap: the second waits on a per-village lock (max 90 s) then runs with `previous_live_rev` re-read; receipts never interleave.
- Anchor session's recording is not ready within 60 s after `delete_session`: the receipt is released without `video_url`; a background job patches it in and re-streams the receipt (`control{kind: release}`) when it arrives.
- Sandbox never calls Core (egress blocked on Tier 1/2): all logs and files are pulled by Core; a test that tries to reach Core fails by design and is listed as a bundle bug.
- Spec rev being released is already `published_rev`: the run is a no-op `released` receipt with `summary="already live"`.

## Requirements

### Functional requirements

- **FR-001** The release lane MUST expose `release.run(village_id, rev, *, trigger, repair_of=None, inject_failure=None) -> Receipt` and `release.prewarm()`; FS-6 calls the former for proposals and nothing else.
- **FR-002** The pipeline MUST execute exactly the six stages of `release.schema.json` in order; a failed stage marks the rest `skipped`; `attempt ≤ 3`; `max 2 repair attempts` (D7).
- **FR-003** The per-village bundle MUST contain: `spec.json` (the VillageSpec rev), `theme.json` (village layer tokens), `i18n/<lang>.json`, `manifest.webmanifest`, `custom/*.tsx` (custom components, if any), and **generated floor tests** in `tests/floor/`: `contrast.test.ts` (≥7:1 elder, ≥4.5:1 others), `sizes.test.ts` (elder `BigButton` ≥88 px, text ≥28 px, tap targets ≥48 px), `safety_colors.test.ts` (the three floor colors unchanged), `actions.test.ts` (every component action routes through `/v/{id}/actions/{name}` or the WS `action`, never a direct write), `render.test.tsx` (each role view renders from `spec.json` with zero unknown types). (D8; Constitution V.)
- **FR-004** Build and tests MUST run inside a Daytona sandbox created from snapshot `village-kit` via a session command with streamed logs; log lines MUST be forwarded as `control{kind: build_log}` and persisted (tail 200 lines) with the receipt. The sandbox MUST NOT call Core.
- **FR-005** On tests passing, Core MUST download `dist` (as `dist.tgz`) and serve it at `/v/{id}/r/{rev}/` (candidate) and, on `live`, at `/v/{id}/` by switching the village's `published_rev` pointer atomically (blue/green). A failing version never replaces `published_rev` (Constitution IV).
- **FR-006** Anchor QA MUST use a session at viewport 390×844 with recording on, drive the app through the public Funnel URL with deterministic Playwright over CDP (no agent tasks), run the scan flow twice and the verification-prompt flow, capture a PNG per assertion, store `live_view_url` and the MP4, and operate only on the shadow village `<id>_qa`.
- **FR-007** Release evals MUST run in-process (Claude via `core/llm.py`), be logged with `ArizeClient().spans.update_evaluations` against the release trace spans, and be mirrored to `var/evals/releases/<release_id>.json` and the `eval_record` table (ARCHITECTURE-VALIDATION §4.4).
- **FR-008** The deterministic part of `safety_copy` MUST compare every `say_key` text in `spec.voice_lines` and the kit's result strings byte-for-byte with the reviewed lines in `data/datasets/policy_cases.md`; any difference fails the stage regardless of judge output (Constitution V: safety wording is never generated).
- **FR-009** Every stage MUST be a span (`release.run` CHAIN root; `daytona_build`, `vitest`, `anchor_qa` TOOL; `release_evals` EVALUATOR with one child per eval; `live` CHAIN) with `session.id=village-<id>`, `graph.node.id`/`parent_id`, and the receipt's `trace_id` = the root trace (Constitution VIII).
- **FR-010** Receipts MUST be persisted (SurrealDB `release` table) and listable via `GET /villages/{id}/releases`; the final receipt MUST also be a ledger `event{kind: release}`.
- **FR-011** The lane MUST ship a scripted "caught and fixed" run (`scripts/caught_and_fixed.sh`) that produces the r3/r4 pair with `inject_failure=contrast`, and a second-village run for `v_w147`, both before 13:40, both traced.
- **FR-012** `release.prewarm()` MUST keep one sandbox (`auto_stop_interval=0`, `refresh_activity()` every 5 min) and one Anchor session (CDP keep-alive every 60 s, `max_duration` 60 min) ready, replacing each after use; pool state is visible at `GET /health` (`prewarm: {sandbox: ready|miss, anchor: ready|miss}`).
- **FR-013** The whole pipeline MUST respect `RELEASE_BUDGET_S` (default 60): at the budget the Control Room is told (`control{kind: reasoning, source: release, kind: note}`) so it can show the recorded receipts; the run itself continues to completion.
- **FR-014** All timing numbers shown anywhere MUST be measured from the receipt (`duration_ms`); documentation uses `[MEASURE: …]` until then.

### Key entities

- **Receipt** (`release.schema.json`): one attempt to release a rev; six stages; `result`; blue/green `previous_live_rev`/`live_rev`.
- **Bundle**: files uploaded to the sandbox for one rev; derived from the VillageSpec + kit template; includes generated floor tests.
- **Candidate** / **Published**: `releases/<village>/r<rev>/dist` on disk; `village.spec_rev` (latest validated) vs `village.published_rev` (what `/v/{id}/` serves and what `snapshot.rev` reports).
- **QA report**: assertions with PNGs, `live_view_url`, MP4, shadow-village event ids.
- **EvalRecord**: name, label, score, explanation, threshold, span id, judge model, duration.
- **Warm pool**: one sandbox id + one Anchor session id with heartbeat timestamps.

## Constitution check

| Principle | How this spec serves it |
|---|---|
| I (gate draws the lines) | The release gate never touches `core/gate/`; the Anchor QA flows exercise the gate through the same public routes as a phone; `actions.test.ts` proves generated UI only acts via gated routes. |
| II (right person's say-so) | A release triggered by a proposal only publishes after the coordinator's approval (FS-6); FS-5 exposes the hook, it never auto-publishes a proposal rev. |
| **III (every fact keeps its source)** | Every receipt carries `trace_id`, stage `evidence_url`s, sandbox id, Anchor session id, eval explanations; the ledger `release` event has `source{system, release}`; nothing is overwritten: a repair is a new receipt with `repair_of`. |
| **IV (nothing reaches a person untested)** | FR-002/005/006/007: six stages, blue/green pointer, QA in a real phone-size browser, evals with thresholds; a blocked receipt never moves `published_rev`. |
| V (built for the person) | Generated floor tests enforce D8 (contrast, sizes, safety colors, catalog-only render); `safety_copy` exact-match keeps safety wording reviewed. |
| VI (contracts first) | Consumes `release`, `village_spec`, `ws_messages`, `lid_scan` schemas; additions listed in `contracts/README.md` are requested from the orchestrator, not forked. |
| VII (always a working version) | Behind `VILLAGE_LAYERS=release`; V3 tag only when `acceptance/v3.sh` is green; the receipts fallback exists before the live rebuild is attempted. |
| **VIII (observable and honest)** | FR-009 spans; FR-014 measured durations only; judge timeouts are shown as such, never hidden as a pass. |
| IX (simplicity) | Core serves static dist (no proxy); evals in-process; one WebSocket; deterministic Playwright instead of agent tasks. |

## Success criteria

- **SC-001** `acceptance/v3.sh` passes: two receipts (blocked r3, released r4) validate against the schema and are listed by `GET /villages/v_reyes/releases`; `/v/v_reyes/` serves rev 4; `v_w147` has a released receipt.
- **SC-002** A full pipeline on the Reyes bundle with warm pool completes in `[MEASURE: s]` (target ≤ 45 s; hard budget 60 s with fallback).
- **SC-003** Anchor QA report has ≥ 4 assertions with screenshots and an MP4 for every released receipt produced after 13:00.
- **SC-004** Arize shows, for `rel_reyes_r4`, the release trace with TOOL/EVALUATOR spans and four `eval.*` columns; the local mirror has the same four records.
- **SC-005** Zero events from QA runs appear in `v_reyes` (only in `v_reyes_qa`).

## Assumptions

- Snapshot `village-kit` was built tonight by `smoke/04_daytona_snapshot.py` and will be rebuilt as `village-kit-v2` with the real `kit/` source once the kit lane's first build is green (T003).
- The Funnel URL is reachable by Anchor's browsers (same as by judges' phones); if the venue blocks `ts.net`, the Worker front door is used for both.
- The Anchor plan allows ≥ 2 concurrent sessions (one warm, one in use); the Free plan allows 5.
- Claude vision input works on the Mantle endpoint for the Sonnet/Haiku models in use (open item R-05 in `research.md`); otherwise `elder_accessibility` falls back to the Anthropic API client.
