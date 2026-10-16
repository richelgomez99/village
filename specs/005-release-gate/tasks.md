# Tasks: Release gate (FS-5)

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/README.md`. **Window**: 10:00–13:40 (V3 cutoff). Lanes: `release`, `evals` (core tasks are requests to the orchestrator). Minutes are estimates for one subagent; if a task runs > 20 min over, stop and report (CLAUDE.md).

Format: `[ID] [P?] lane · version · minutes · deps · description · acceptance · principle`. `[P]` = can run in parallel with its neighbours (different files).

## Phase 1 — Setup (10:00–10:30)

- [ ] **T001** release · V3 · 10 min · — · Create `core/release/` and `sandbox/` skeletons with the interfaces in `contracts/README.md` (`run`, `publish`, `rollback`, `repair`, `prewarm`, `pool_status`, `get_receipts`) returning fixture-shaped `Receipt`s from `release.schema.json` examples. · `uv run pytest core/release -q` passes with the stub; receipts validate. · VI
- [ ] **T002** [P] evals · V3 · 10 min · — · Create `evals/release/` skeleton: `EvalRecord`, `thresholds()`, `run()` returning FakeJudge records, `mirror()` writing `var/evals/releases/<rel>.json`. · `uv run pytest evals/release -q`. · VIII
- [ ] **T003** [P] release · V3 · 25 min · kit lane's first green `npm run build` · Rebuild snapshot `village-kit-v2`: smoke 04 image + `add_local_dir("kit", "/opt/kit-template")`, `npm ci`, warm `vite build` once; set `DAYTONA_SNAPSHOT`. · `smoke/04_daytona_snapshot.py --name village-kit-v2` → `state=active`; a sandbox from it builds the kit offline. · IV, IX
- [ ] **T004** [P] release · V3 · 15 min · T003 · Measure in the sandbox: `bash build.sh` wall time, `vitest` time, `dist.tgz` size + `download_file` latency; record in `research.md` R-01/R-02/R-03 as `[MEASURE]` values. · Numbers in research.md; none invented. · VIII

## Phase 2 — Foundational (10:30–11:30)

- [ ] **T005** release · V3 · 35 min · T001 · `sandbox/floor/*.test.ts(x)` templates + `floor.constants.ts` (D8 values) and `core/release/bundle.py` that renders them from a VillageSpec (contrast via a small WCAG helper, sizes from rendered DOM, safety colors, actions routed via `/v/{id}/actions/*` or WS `action`, render per role with unknown types → nothing). · Against `reyes_spec.json`: bundle has all files; the elder `tone=info` injection makes `contrast.test.ts` fail with the schema example's failure line. · V
- [ ] **T006** [P] release · V3 · 30 min · T003 · `core/release/daytona_svc.py`: `AsyncDaytona` create-from-snapshot, `upload_files`, session command with `get_session_command_logs_async` (non-blocking callbacks → `control{kind: build_log}`), exit markers, `download_file` for `vitest.json` + `dist.tgz`, delete. `FakeDaytona` for tests. · Real run: build log streams; blocked and released outcomes both produce correct stage details. · IV, VIII
- [ ] **T007** [P] release · V3 · 25 min · T001 · `core/release/serve.py`: static mounts `/v/{id}/` and `/v/{id}/r/{rev}/` from `var/releases`, atomic `published_rev` switch (symlink swap + CAS via `services.set_published_rev`), `rollback`. · `serve_test.py`: candidate served, published unchanged until `live`; swap is atomic. · IV
- [ ] **T008** [P] core (request) · V3 · 20 min · — · `services.reset_village(<id>_qa, spec_rev, seed)`, `services.start_verification(...)` with `source{system, release-qa}`, `services.set_published_rev`, `services.snapshot_all`; outbox and detector ignore `*_qa`. · Fixture-shaped stubs committed by 10:30; real by 11:30. · I, III
- [ ] **T009** [P] evals · V3 · 25 min · T002 · `core/obs/` span helpers for the pipeline: `release.run` CHAIN root with `session.id`, TOOL spans for `daytona_build`/`vitest`/`anchor_qa`, EVALUATOR parent + child per eval, `graph.node.*`; expose `span_ids` to evals. · smoke-07-style run shows the tree in Arize. · VIII

## Phase 3 — User Story 2: Anchor QA (11:30–12:30)

- [ ] **T010** release · V3 · 15 min · — · Measure Anchor: `create_session`, `connect_over_cdp`, `goto($TUNNEL_URL/health)` from the Anchor browser (R-04), live view iframe on the Control Room origin. · `[MEASURE]` values in research.md; iframe renders. · VIII
- [ ] **T011** release · V3 · 40 min · T007, T008, T010 · `core/release/anchor_svc.py`: session create (390×844, recording on), Playwright flows A1–A4 from `plan.md`, `expect_text` with screenshots, QA report JSON, `app_unreachable` / `anchor_unavailable` / `assertion:*` errors, `delete_session` in `finally`, background recording fetch → `video_url` + receipt re-stream. `FakeAnchor` for tests. · Against the served fixture: report has 4 ok assertions + PNGs; shadow village has the QA events, `v_reyes` none; MP4 arrives ≤ 60 s. · IV, I
- [ ] **T012** [P] kit (request) · V3 · 10 min · — · Kit reads `?village=` to point the WS at the shadow village; result strings carry stable aria-labels/roles for the QA selectors (`button "No fui yo"/"That wasn't me"`, result text). · Selectors in T011 pass on the real kit. · VI

## Phase 4 — User Story 3: release evals (11:30–12:45)

- [ ] **T013** [P] evals · V3 · 10 min · — · `smoke/01_llm.py --vision`: send a 390×844 PNG to `BEDROCK_SONNET_MODEL` on Mantle; fallback `Anthropic()` (R-05). · PASS/FAIL recorded; fallback chosen. · VIII
- [ ] **T014** [P] evals · V3 · 15 min · — · Extend smoke 07 with `ArizeClient().spans.update_evaluations` on the emitted span and an `ax.spans.list(filter="eval.smoke.label = 'x'")` read (R-06); note visibility delay. · `[MEASURE]` delay in research.md. · VIII
- [ ] **T015** evals · V3 · 45 min · T002, T009, T013 · Implement the four evals: `spec_coverage` (judge), `safety_copy` (exact-match vs `policy_cases.md` say lines + judge on free text), `translation_backcheck` (Haiku back-translate → Sonnet equivalence), `elder_accessibility` (vision judge on A4 PNG); `judge.py` with 20 s budget, Haiku retry, `judge_timeout`/`judge_unavailable` labels; thresholds. · Unit tests with FakeJudge: a changed `money_denied` line fails `safety_copy` deterministically; a timeout yields `score=None` and the strict/soft rule. · V, VIII
- [ ] **T016** evals · V3 · 15 min · T014, T015 · `log_to_arize()` (dataframe → `update_evaluations`, 5 s timeout, never raises) + `mirror()` (`eval_record` rows + JSON). · Real run shows four `eval.*` columns on the release trace; mirror file matches. · VIII, III

## Phase 5 — User Story 1 + 5: pipeline, receipts, pre-warm (12:00–13:15)

- [ ] **T017** release · V3 · 30 min · T006, T011 · Warm pool: `prewarm()` (sandbox + Anchor session), heartbeats (`refresh_activity` 5 min; CDP `page.evaluate("1")` 60 s), take/replace, `/health.prewarm`; R-08 hold test (10 min). · Pool reports ready; a release after 10 min idle starts build < 1 s and connects CDP < 1 s. · IX
- [ ] **T018** release · V3 · 45 min · T005–T007, T011, T016 · `core/release/pipeline.py`: six stages, per-village lock, stage timing, `control{kind: release}` on every transition, `build_log` + `qa` frames, blocked → skipped rest, `publish=False` path for proposals, budget timer → `reasoning` note at `RELEASE_BUDGET_S`, `receipts.py` persistence + ledger `release` event. · `pipeline_test.py` with fakes: released, blocked-at-tests, app_unreachable, anchor_unavailable, judge_timeout (strict/soft), no_report, overlap lock, already-live no-op; receipts validate against the schema. · IV, VIII, III
- [ ] **T019** [P] release · V3 · 20 min · T018 · `core/release/repair.py`: floor autofix (`tone=info` → floor ink mapping, translation drift → simpler reviewed text) then builder `patch_app` repair hook (mocked until builder merges); returns the new rev. · r3 failures → autofix produces the r4 spec diff from the schema example ("elder info tone mapped to floor ink"). · V
- [ ] **T020** [P] core (request) · V3 · 15 min · T018 · Routes `GET/POST /villages/{id}/releases`, `GET /releases/{rel}/qa/{file}`, `POST /release/prewarm` (control token) → orchestrator bumps contracts to 1.1.0. · OpenAPI validates; routes answer. · VI
- [ ] **T021** [P] kit (request) · V3 · — · — · ReleaseStrip renders `control{kind: release}` receipts incl. the linked blocked→repair pair, live view iframe (`pointer-events:none`), build log panel; "recorded receipts" fallback mode. · Strip shows r3/r4 from `release.schema.json` examples via the fake WS. · VIII

## Phase 6 — User Story 4 + demo material (13:00–13:35)

- [ ] **T022** release · V3 · 15 min · T018, T019, T020 · `scripts/caught_and_fixed.sh`: POST rev 3 `inject_failure=contrast` → blocked; `repair` → rev 4 released; prints both receipt ids + trace ids. Run it; keep artifacts. · Two receipts match the schema examples' shape; `/v/v_reyes/` serves rev 4; Arize has both traces. · IV, VIII
- [ ] **T023** release · V3 · 15 min · T022 · Second village: `release.run("v_w147", 2)` from `block_spec.json` (coordinator/resident/volunteer, en/es/zh i18n). Note `duration_ms` for the Anyone reveal. · Released receipt; `/v/v_w147/` serves three views. · V (any language), IX
- [ ] **T024** release · V3 · 20 min · T022, T023 · **`acceptance/v3.sh`**: (1) `contracts/validate.py` OK; (2) `pytest core/release evals/release -q`; (3) `GET /villages/v_reyes/releases` has `rel_reyes_r3 blocked` and `rel_reyes_r4 released live_rev=4`, both schema-valid (jsonschema); (4) `curl $TUNNEL_URL/v/v_reyes/` returns the rev-4 `index.html`; (5) `var/releases/v_reyes/r4/qa/report.json` has ≥ 4 ok assertions and PNGs; (6) `var/evals/releases/rel_reyes_r4.json` has 4 records with `passed=true` (or `judge_timeout` noted and strict off); (7) `GET /villages/v_w147/releases` has a released receipt; (8) `/health.prewarm` both `ready`; (9) zero QA events in `v_reyes` (`events?kind=dose_repeat_scan&source.ref=release-qa` empty). Exit 0 → tag V3. · Script green on the Mac. · VII
- [ ] **T025** [P] evals · V3 · 10 min · T016 · Record measured numbers (pipeline total warm/cold, eval durations, Anchor create) into `research.md` and hand to pitch lane; replace every `[MEASURE]` touched. · No placeholders remain for measured items. · VIII
- [ ] **T026** [P] release · V3 · 10 min · T017 · 13:30: run `prewarm()`, verify `/health`, hold until V4; document the "re-create at T-60 s" operator button in the Control Room notes. · Pool ready at 13:35. · VII

## Dependencies summary
T001 → T005/T007/T018; T003 → T004/T006; T008 + T010 → T011; T002 + T009 + T013 → T015 → T016; T006 + T011 + T016 → T018 → T019/T022 → T023 → T024. Requests to core/kit (T008, T012, T020, T021) must land by 12:30 or the lane mocks them and reports the mock in the merge note.

## Parallel execution guide
- 10:00: T001 ‖ T002 ‖ T003; then T004 ‖ T005 ‖ T006 ‖ T007 ‖ T009.
- 11:30: T010→T011 ‖ T013→T015 ‖ T014.
- 12:30: T017 ‖ T018 → T019 ‖ T020 ‖ T021.
- 13:00: T022 → T023 → T024; T025 ‖ T026.

## Addendum (D23): the Builder fixes its own build
- T025 [release/builder, V3, 30 min] On a failing stage (tests or evals), `release.run` hands the failure (test name, assertion, file) to the Builder role with `patch_bundle` tool; one repair attempt, then re-run; receipts record both attempts; the caught-and-fixed demo bundle (elder theme contrast 4.1:1) is fixed by the agent patching the theme token, not by a human. Acceptance: trace shows AGENT builder → TOOL daytona_build (fail) → LLM → TOOL daytona_build (pass).
