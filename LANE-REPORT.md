READY FOR MERGE V1
# Lane reports (merged; each lane's LANE-REPORT.md is appended by a union merge)

## contracts
READY FOR MERGE 1.2.0
C001 · done · `uv run --with jsonschema --with pyyaml --with openapi-spec-validator python contracts/validate.py` · `OK contract 1.2.0: 13 schemas, 30 examples, 7 fixtures, openapi 3.1.0 with 33 paths`

Core/kit follow-up required:
- core must serve `prescriptions:current` data for helper/coordinator `RefillCard` bindings.
- core must accept `hello.view_as` only for coordinator/control tokens and keep view-as sockets read-only.
- core must send optional `snapshot.identity {member_id, name, role, village_name}`.
- core must read the contract version from `contracts/VERSION` instead of hardcoding `1.1.0` in `core/tests/test_spine.py`.
- kit must render the contract catalog types `RefillCard` and `TonightCard` from `village_spec.schema.json`.

LD-1: Contracts 1.2.0 is additive: D22 changes are expressed as catalog/binding additions plus Reyes rev 5 fixture changes; no existing schema field or fixture id was renamed.

## gate
READY FOR MERGE V0
G001 · done · uv run pytest core/gate -k roundtrip -q · mocked none
G002 · done · uv run pytest core/gate -k say -q · mocked none
G003 · done · uv run pytest core/gate -k "T0 or T1 or T2 or spec_patch or kill_switch" -q · mocked core write/id minting only
G004 · done · uv run pytest core/gate -k "T3 or T4 or T5" -q · mocked core idempotency cache and persisted verification rows
G005 · done · uv run pytest core/gate -k verification -q · mocked core CAS commit only
G006 · done · uv run pytest core/gate -k dose_window -q · mocked dialer/action execution only
G007 · done · uv run pytest core/gate -q · mocked none
LD-1: Gate models stay contract-shaped dict wrappers so Core can pass schema JSON without translation.

## core
READY FOR MERGE V0
T001 · done · `uv run python - <<'PY' ... TestClient(app).get('/health') ... PY` · health deps use stubs; DB/live not wired yet; `uv run pytest core -q` currently collects no tests
T002 · done · `uv run python - <<'PY' ... TestClient(app).post('/tools/log_dose') ... PY` · services seam replays contract examples/fixtures and log-only broadcast/post_message
T003 · done · `uv run pytest core -q` · clock warp broadcasts to in-process WS hub; scheduler tick not wired yet
T004 · done · `uv run python -m core.db --apply`; `uv run pytest core/tests/test_ids.py -q` · `ids.py` done; DB uses SurrealDB Cloud when `SURREAL_DB_URL` is set and keeps the in-process mirror/fallback when URL is empty; CAS-compatible return shape implemented
T005 · done · `uv run python -m core.tools.seed`; `uv run pytest core/tests/test_fixtures.py -q` · fixture seed resets app tables, loads Reyes spec/events/views/members, and generated member tokens; no hashed slot tokens because D22 cuts lid scans from V0
T006 · done · `uv run pytest core/tests/test_spine.py -q` · one WebSocket hub and DB change-feed fan-out work; SurrealDB Cloud writes are mirrored, and the local asyncio feed is the fallback/live source for demo acceptance
T007 · done · `uv run pytest core/tests/test_bindings.py -q` · V0 dose-day and rota bindings are role-aware; elder hides med names; helper receives no dose payload on D22 check-in path
T008 · done · `uv run pytest core/tests/test_spine.py -q` · `services.decide` loads state, mints alloc ids, calls merged gate or `core/gate_fallback.py`, persists/broadcasts decision rows, writes returned drafts, and records caused event ids
T009 · done · `uv run pytest core/tests/test_spine.py -q` · `/tools/{name}` dispatch handles D22 `log_dose`; `/s/{slot_token}` remains cut/optional per D22
T010 · done · `uv run pytest core/tests/test_spine.py -q` · HTTP actions and WS inbound actions share the same `services.handle_action`; decisions endpoint returns caused event ids
T011 · done · `acceptance/run.sh V0 --lane core` · acceptance covers D22 check-in tool path, prescriptions, clock warp and core tests; gate lane tests not present in this worktree yet
LD-1: D22 addendum makes `/s/{slot_token}` optional for V0; core V0 acceptance will use `POST /tools/log_dose` for check-in → event log stub until T004-T008 replace persistence.
LD-2: Decision `mode` is recorded under `refs` as `{"kind":"mode","id":"acted_alone"}` because the decision schema has no first-class `mode` field.
LD-3: `core.llm.llm()` keeps `VILLAGE_LLM=off` deterministic for tests; when enabled it uses Anthropic Sonnet (`claude-sonnet-5-5`) for sonnet-class roles if `ANTHROPIC_API_KEY` is set, otherwise Bedrock Mantle with env-provided model ids.
T012 · done · `uv run pytest core/tests/test_verifications.py -q` · verification rows persist with version 0 and answers commit through CAS; duplicate terminal answers are ignored
T013 · done · `uv run pytest core/tests/test_verifications.py -q` · tool idempotency caches exact response bodies by `(conversation_id, tool_call_id)` and duplicate money webhooks create one verification

## pitch
READY FOR MERGE V0
P001 · done · README.md (identity, arc, architecture, run, sponsors, safety rules with test names, real vs mocked, measured numbers, D25 pointer, team) · numbers only from RESULTS.md; 3 [MEASURE] rows
P002 · done · docs/DEVPOST.md (V0 ready; V1–V4 [PENDING Vn]; numbers table; video shot list; 10 Q&A) · [MEASURE]/[PENDING] left in V1–V4 and shared tables only
P003 · done · `CORE_URL=http://127.0.0.1:8799 scripts/reset_demo.sh` twice against a throwaway Core (SURREAL_DB_URL empty): exit 0, identical checklists; wrong ADMIN_KEY → exit 1 with manual command · warm is a stub
LD-1 (mismatch): `POST /admin/reset` ignores `scopes` and runs the full `core.fixtures.reset_demo("v_reyes")`, so step 3 (`core.tools.seed`) repeats the same reset in a separate process. With `SURREAL_DB_URL` set, seed clears and reloads SurrealDB Cloud but cannot touch the running Core's in-process mirror; harmless today, but the scopes are cosmetic.
LD-2 (mismatch): `core.tools.warm` is a stub (`print("warm OK (stub)")`); reset_demo.sh flags it as STUB in the checklist until the release lane replaces it.
LD-3 (mismatch): `/clock/warp` takes `{"to": iso}` (also `minutes`, `reset`); reset uses `to`, which is absolute, so repeated runs land on the same clock.
LD-4: `kit/` is not in main yet; README's `cd kit && npm run dev` says so.
## voice
READY FOR MERGE V1
T001 · done · `elevenlabs agents push --dry-run` · mocked: no live push; API key now present but live operations stay dry-run until orchestrator says otherwise
T002 · done · `uv run python scripts/check_tool_schemas.py`; `elevenlabs tools push --dry-run` · mocked: tool ids, workspace env values
T003 · done · `python -m json.tool agents/agent_configs/mom-line.json >/dev/null` · mocked: voices and dashboard init hook enablement
T004 · done · `uv run python scripts/push_procedures.py --dry-run --all` · mocked: live procedure publish disabled until procedure API shape is approved
T005 · done · `uv run pytest core/voice/tests/test_mock_core.py -q` · mocked: Core answers from contracts/fixtures/scam_call_tool_requests.json
T006 · consumed · merged from core on main; voice imports core.services lazily and falls back to fixture stubs when a service is missing
T010 · done · `uv run pytest core/voice/tests/test_tools.py -q` · mocked: fixture fallback for exact scam variants; real core delegation covered by test
T011 · done · `uv run pytest core/voice/tests/test_init_hook.py -q` · mocked: call rows kept in in-memory voice-call log
T012 · done · `uv run pytest core/voice/tests/test_outbound.py -q` · mocked: FakeDialer; live outbound remains blocked by Twilio geo-permissions
T014 · done · `uv run pytest core/voice/tests/test_post_call.py -q` · mocked: memory handoff writes local outbox file; post-call signatures use local HMAC verifier
T013/T015 · core-owned · merged core has verification persistence/idempotency; remaining WS prompt/incident binding is core acceptance surface
LD-1: Live ElevenLabs agent, tool, and procedure operations remain dry-run despite credentials being present.
LD-2: `VILLAGE_PHONE_NUMBER=+18482579221` is Carmen's Village line; fridge card display format is +1 848 257 9221.
LD-3: Receptionist mode from D19 remains V4-only behind a future flag.
READY FOR MERGE V0
READY FOR MERGE V1

# Kit lane report (004-kit-control-room)

Acceptance: `kit/scripts/acceptance_v0.sh` (= `npm ci && npm test && npm run build` + headless jsdom render of carmen/ana/marco through the fake Core). Offline demo: `cd kit && npm run dev` then `/?fake=carmen|ana|marco|lucia|control` (`&start=<s>|off`, `&tail=denied|timeout|confirmed`, `&speed=<x>`, `&demo=refill`); `window.__fake.play("start")`; sent frames on `window.__frames`.

## Tasks
- T001 · done · `npm run build` → dist/index.html, join.html, control.html · scan.html deleted (D22)
- T002 · done · `npx vitest run tests/patch.rev.test.ts` · fixture proposal ops on elder; bad op throws, view unchanged
- T003 · done · `npx vitest run tests/renderer.unknown.test.tsx` · unknown + invalid-props counters, children only Screen/Stack, `data-id`/`data-type` wrapper
- T004 · done · `npx vitest run tests/props.schema.test.ts` · hand-written strict zod mirror of all 27 `props_*` (no generator, LD-2); both fixtures parse; danger w/o confirm fails; type list == contract enum
- T005 · done · `npx vitest run tests/elder.floor.smoke.test.tsx` · exact plan.md tokens; Google Fonts link + system fallbacks (not self-hosted)
- T006 · done · roles test · Screen (+ReadAloud on every screen), Stack, Header, Text, BigButton (icons, tones, ConfirmSheet), ContactCard (tel:), StatusGrid
- T007 · done · roles test · Alert (severity, countdown, escalation), DoseTracker (meds hidden on elder), HelperAnswer, Timeline (provenance + superseded), CareRota, LifeAreas, PillOrganizer
- T008 · done · `npx vitest run tests/ws.reconnect.test.ts` · hello/snapshot/patch rev gate/event merge/prompt/result/ping-pong dead-man/backoff 0.5→8 s/stop on contract_mismatch|bad_token
- T009 · done · `npx vitest run tests/scam.replay.test.tsx` · fake Core (`src/dev/fakeWs.ts`), BroadcastChannel between tabs so Marco's answer drives every tab's tail · mocks: Core, all `data` not in fixtures (LD-6)
- T010 · cut · — · scan page removed per D22 (no lid stickers on the demo path)
- T011 · done · `kit/scripts/acceptance_v0.sh` · jsdom, not a real browser (manual Playwright screenshots at 390×844 looked right)
- D22 RefillCard · done · roles test · kit-extension type bound to `prescriptions:current` (not in contract); fake Core adds it to helper/coordinator; `?demo=refill` injects it on a real-Core session
- D22 TonightCard · done · roles test · kit-extension type bound to `rota:current.on_duty`; fake Core's D22 overlay puts it on the elder view
- T044 IdentityChip · done · roles test · "You're Marco · Reyes village" / "Eres Carmen · familia Reyes" / "You're family"
- T045 View-as · partial · scam.replay test · coordinator + control switcher sends `hello{view_as}` and disables buttons; works with the fake Core; **real Core needs to accept `view_as` (LD-5)**
- T042 captions (D18) · partial · — · `ctx.captions` adds the English line under Spanish on control/projector surfaces (Control Room phone mirror + gate say); live call captions (`control{caption}`) not done
- T012 VerificationPrompt · done · scam.replay test · yes/no/unsure, countdown to `deadline`, pending → thanks from `result.decision.say`
- T013 PromptOverlay · done · scam.replay test · "Village is calling you · AI assistant"; `closed:true` dismisses
- T014 IncidentCard · done · scam.replay test · 3 outcomes by `verification_status`, red flags, provenance, ack → `ack{event_id}` (falls back to action `ack_incident`)
- T015 ScamCheck · done · `npx vitest run tests/scamcheck.states.test.tsx` · idle/choosing/checking/denied/timeout/confirmed; only gate `say` text
- T016 join.html · done · `npx vitest run tests/join.test.tsx` · body per openapi `redeemInvite` {invite (?i= or #i=), first_name, phone?, consent{ai_calls, text_version:"join_v1"}}; token in localStorage; invite scrubbed from the URL
- T017 i18n · done · `npx vitest run tests/i18n.rtl.test.tsx` · `src/i18n/strings.ts` es/en (TS module instead of es.json/en.json)
- T018 read-aloud · partial · manual · speaks every `[data-say]` node of the screen via speechSynthesis; tap again stops; no per-component summaries
- T019 · partial · — · not run against the real Core `/ws` yet (Core not merged in this worktree)
- T020–T041 (Control Room V2+) · partial · — · `control.html` shell only: gate feed, decisions log, counters, View-as phone mirror with captions

## Lane decisions
- LD-1 The D22 view changes (drop "Ya me la tomé"/`log_dose` and the elder DoseTracker, add "Llamar a Village" = `call_number` arg `village`, TonightCard, RefillCard) live in the **fake Core** (`src/dev/fixtureData.ts#d22Overlay`), not in the renderer. The renderer draws whatever Core sends. `reyes_spec.json` rev 4 still has the pre-D22 elder view, so Core/builder needs the same overlay or a rev 5 fixture.
- LD-2 Props schemas are written by hand (strict = `additionalProperties:false`, plus the danger-confirm and parallel-array rules). A test checks the type list against the contract enum. There is no generator script.
- LD-3 `RefillCard` and `TonightCard` are kit-extension catalog types (they aren't in contract 1.1.0, and `prescriptions:current` isn't in the bind grammar). The contract needs them (orchestrator) before the builder can emit them.
- LD-4 Countdowns use the contract's `deadline` (45 s after creation in the fixture), not a hard-coded 35 s. The client clock syncs to `snapshot.now` and moves forward with `event.at`.
- LD-5 `hello.view_as` is sent even though contract 1.1.0 `hello` has `additionalProperties:false`. The real Core must accept it (only for coordinator/control tokens), or the contract must add it.
- LD-6 Fake data that isn't in the fixtures: med schedule per slot, refill doses other than lisinopril, rota week, dose week, the "lisinopril 5 mg" superseded timeline row, and the initial life-area chips. Rota follows D17 (Marco on duty Friday).
- LD-7 Event `data` merges keep `null` values (they aren't deleted), so components can tell "nobody" apart from "unknown".
- LD-8 The Control Room `a.css` tokens are scoped to `.control` so they don't override the floor tokens.

## Open risks
- Real-Core integration not exercised (no core in this worktree). The client needs Core to send `role`, `member_id`, `now`, and `spec` = the view.
- Bundle size: the fixtures are bundled for offline fake mode (~70 kB gz per entry).
P004 · done · `scripts/acceptance_summary.sh --list` and full run (SURREAL_DB_URL empty): V0 PASS, V1–V4 absent; tags gate-v0, spine-v0, voice-v1; V*-green not tagged yet
P005 · done · docs/CHECKPOINTS.md template (11:00/12:15/13:00/13:40/14:15/14:20)
P006 · done · docs/SLIDES.md (6 slides, stage lines, fallbacks; [MEASURE] where numbers go)
LD-5: merged main (voice-v1) into 007-pitch-kit; README "real vs mocked" updated: voice code merged, live ElevenLabs pushes dry-run, outbound via FakeDialer (Twilio geo permissions).
## gate
READY FOR MERGE V1
G008 · done · deadline-during-await closes TIMED_OUT; consent-revoked dial is no-op; T32/T33 and ignored terminal answer covered.
G009 · done · tick{dose_window} returns reminder/escalation decisions with event_draft-valid writes; T04 uncertain prior dose escalates with dose_uncertain.
G010 · done · say_vars is always present; deciding R-id remains rules_fired[0] (T28 asserts R-DOUBLE).
Audit · T01-T51 have gate test status; deferred to later lanes: T21-T26 rumor/resource matching source-verification cases.
Verify · uv run pytest core/gate -q · 110 passed offline.
LD-2: Scheduler-facing dose ticks use R-MISSED as the gate rule and policy IDs P-ME-01/P-ME-02 for reminder/escalation attribution.
LD-3: T21-T26 are tracked but deferred because rumor verification/resource matching are not in G008-G010 and require non-gate source/matching services.

## release
READY FOR MERGE V3
Offline: `uv run pytest core/release -q` → 27 passed (model OFF, fakes for Daytona/Anchor/evals). Real: `VILLAGE_LLM=on uv run --with daytona --with anchorbrowser --with playwright --with boto3 --with arize-otel python scripts/release_smoke.py [--break-contrast] [--cold] [--spec contracts/fixtures/block_spec.json]`, run 4× after the main merge (contract 1.2.0, Reyes rev 5), all real Daytona + real Anchor + Arize export on.
T001 · done · `uv run pytest core/release -q` · ports.py + fakes.py (FakeDaytona/FakeAnchor/FakeEvals/FakeLLMClient)
T003 · cut · — · snapshots denied on this account; default image + one warm sandbox (label `village-release=warm`, auto_stop 0, `npm ci` once, `.deps_key`) instead
T005 · done · `uv run pytest core/release -k "floor or bundle" -q` + real r3 run · floor_tests.py generates `tests/floor/floor.test.ts` per village/rev (elder ≥28 px, nothing <22, buttons ≥88, contrast ≥7:1 computed, safety colors, catalog-only incl. RefillCard/TonightCard, ≤3 BigButtons, 911 ContactCard) · bundle = `sandbox/template/` (not kit, LD-1)
T006 · done · smoke run · daytona_svc.py: upload_files → `vite build` → `vitest --reporter=json` → download vitest.json + dist.tgz; build logs as `control{build_log}` (exec output, not streamed session logs)
T007 · done · `uv run pytest core/release -k routes -q` · serve.py LocalPublisher: candidate `/v/{id}/r/{rev}/`, `published.json` blue/green; core's `set_published_rev` not used (LD-3)
T010/T011 · done · smoke run · anchor_qa.py: Anchor session 390×844 + recording, `connect_over_cdp`, measures buttons/911/font, screenshot + report.json + live view URL in evidence_urls; targets TUNNEL_URL candidate first, else Daytona signed preview, else local Playwright = `degraded` · flows A1–A4 (scan/scam taps) not run, only the static view assertions
T015/T016 · partial · smoke run · evals.py: needs_coverage + no_medical_advice (code), translation_backcheck + elder judge (core.llm "verifier" → Haiku); EVALUATOR spans with `eval.*` attrs + `var/evals/releases/<rel>.json` mirror · `update_evaluations` not called; no vision judge
T017 · partial · `uv run --with daytona python -m core.release.warm` · sandbox reused by label across processes; Anchor pre-warm exists but sessions are per-release (≈2 s); no 10-min hold test
T018 · done · `uv run pytest core/release -k pipeline -q` · pipeline.py 6 stages, per-village lock, every frame validated against ws_messages `control{kind: release}`, blocked keeps last good rev, max 2 repairs
T019/T025 · done · `release_smoke.py --break-contrast` · Builder repair: LLM proposes a token patch, code recomputes contrast, 1 retry with the measured ratio, then deterministic fallback; real run: r3 blocked "contrast 4.1:1 on elder Text (needs 7:1)" → LLM "#4C80B4→#2D5A8C" → r4 released; spans AGENT builder.release → TOOL daytona_build ✗ → LLM builder.repair_theme → TOOL daytona_build ✓ (`test_spans.py`)
T020 · done · `uv run pytest core/release -k routes -q` · routes.py: `GET /v/{id}/r/{rev}/{path}`, `GET /v/{id}/`, `GET /releases/{rel}/qa/{file}`, `GET|POST /villages/{id}/releases` (202/404/409/422/503) via service.py · no control-token auth (core's middleware)
T022 · done · `release_smoke.py --break-contrast` · script instead of caught_and_fixed.sh
T023 · done · `release_smoke.py --spec contracts/fixtures/block_spec.json` · rel_w147_r2 released, 33 floor tests, Anchor on the coordinator view
T024 · cut · — · acceptance/v3.sh not written; the smoke output + receipts are the evidence
LD-1: Bundle = `sandbox/template/` (catalog renderer sharing `styleFor()` with the generated floor tests). kit/ needs WS + Core data to render and has no styleFor seam; `RELEASE_BUNDLE_SOURCE=kit` only switches once `kit/src/catalog.ts` exists.
LD-2: Anchor reaches the candidate via the Daytona signed preview (`vite preview` in the sandbox, inbound only) because Core on :8790 does not mount the release router yet; once mounted, TUNNEL_URL is tried first automatically. Receipt summary says which ("via daytona preview|tunnel|local").
LD-3: core.llm sends role "haiku" to the Sonnet model on Bedrock and prefers ANTHROPIC_API_KEY for Sonnet roles; that key returns 400 (needs anthropic-workspace-id). Release uses role "verifier" for the judge and repair falls back builder → verifier.
LD-4: `daytona_build` TOOL span covers build + vitest in the sandbox (one tool call), so a floor failure marks it ✗.

| Measured (ms) | cold `--cold --break-contrast` | warm `--break-contrast` | warm rev 5 | warm v_w147 r2 |
|---|---|---|---|---|
| sandbox create / get | 3444 | 149 | 108 | 75 |
| npm install | 2044 | — | — | — |
| upload template + village | 274 + 100 | 178 + 98 | 163 + 136 | 229 + 99 |
| vite build (attempt 1 / 2) | 2192 / 2254 | 2103 / 2088 | 2083 | 2072 |
| vitest (attempt 1 / 2) | 1392 / 1461 | 1254 / 1160 | 1315 | 1276 |
| dist download | 208 | 184 | 285 | 211 |
| signed preview start | 1299 | 1420 | 1602 | 1495 |
| Anchor QA (session+CDP+flow) | 9101 | 5211 | 5359 | 5398 |
| evals (Haiku judge) | 3776 | 3249 | 3096 | 1667 |
| **total** | **29731** (r3 blocked + repair + r4 live) | **19908** | **14957** | **13409** |
Warm live rebuild = 15.0 s (target ≤ 60 s). Anchor create alone 1.8–2.3 s (earlier runs).
Core must mount: `from core.release.routes import router as release_router; app.include_router(release_router)`; optional in lifespan `await core.release.service.get_service().startup()`. Broadcast goes through `core.services.control(village, kind, payload)`; specs come from `core.db.db.specs` with fixture fallback.
Open risks: Anchor-via-tunnel not exercised end to end (router not mounted on the live Core); `published_rev` is a local file, not core state; only static view assertions in QA (no scam/scan taps); ANTHROPIC_API_KEY 400 in core.llm (LD-3).
