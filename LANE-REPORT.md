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
READY FOR MERGE V2-CORE
READY FOR MERGE V1
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
T014 · done · `uv run pytest core/tests/test_verifications.py -q` · scheduler tick runs on boot/clock warp and closes pending verifications past deadline with a timeout event
T015 · done · `uv run pytest core -q` · WS prompt frames go only to the claimed member, terminal rows close the prompt, and live bindings resolve alerts, pending/mine verifications, and open incidents
LD-4: Core uses the merged `step_verification` state machine for app answers; a later different answer is persisted as `conflict` per the verification contract instead of being dropped as a terminal no-op.
T016 · done · `uv run pytest core/tests/test_verifications.py core/voice/tests/test_post_call.py -q` · real start/answer/await verification services, HTTP answer endpoint, app actions, and voice post-call path use the shared verification state machine; (the rev 5 / elder-dose failures were fixed by main 07680d9 on merge)
T017 · done · `uv run pytest core/tests/test_recovery.py -q` · boot runs `scheduler.recover()`: first tick closes past-deadline rows through the gate SM (timeout + incident), rows with `call_placed_at` are never redialed; `core/dialer.py` seam: `FakeDialer` in tests/acceptance, real = `core.voice.outbound.ElevenLabsDialer` via `OutboundService` (CAS on `call_placed_at`) only when consent `ai_calls` is true and ElevenLabs key + `ELEVENLABS_AGENT_CALLER_ID` + phone number id are configured · mocked: memory DB is reset on boot, so recovery is exercised on rows injected into the store (no Surreal reload yet)
T018 · done · `acceptance/run.sh V1 --lane core` (boots Core on :8792 with FakeDialer, real sockets via `acceptance/v1_flow.py`, then `uv run pytest -q`) · start+denied frames match `ws_sequence_scam.json` per client in order (type, event kind / control kind, prompt.closed, data keys bound by the view); every frame validates against `ws_messages.schema.json`; verbatim gate `say` for denied/timeout; duplicate webhook identical; timeout via `/clock/warp` · mocked: control `reasoning` lines not produced (skipped in the match)
T019(1.2.0) · done · `uv run pytest core/tests/test_contract_12.py -q` · `prescriptions:current` (bv_prescriptions) for helper/coordinator/control snapshots and `changed()` on med_change/shift; lisinopril 10 mg with superseded 5 mg valid_until 2026-10-03 changed_by Dr. Lee, apixaban, metformin, atorvastatin; never elder
T020(1.2.0) · done · same · `hello.view_as` honored for control/coordinator tokens only (others get `error{not_allowed}` and stay themselves); view_as sockets are read-only (actions/acks → `error{not_allowed}`)
T021(1.2.0) · done · same · `snapshot.identity {member_id, name, role, village_name}` (+`view_as: true`); snapshot now carries `spec` (view for members, whole VillageSpec for control) and `now` per contract; all snapshots validate
LD-5: Member tokens: `mt_<firstname>_<anything>` (QR/fixture form), the bare member id, or `control`/`CONTROL_TOKEN` resolve in `core/auth.py`; no token minting yet.
LD-6: `changed_by` for the lisinopril change follows `ws_sequence_scam.json` ("Dr. Lee"); the seed ledger row says "Dr. Elena Park" and reyes_family.json says p_park; flagged for contracts.
LD-7: Event frames are not tagged `contract_version` (schema forbids it); control sockets get events without `data`; `mode` rides on `control{gate}` payloads as an extra field (kit asked; contract to follow).
LD-8: Voice tools reach real services via `services.handle_voice_tool` (the ToolHandler prefers it), so `core/voice/tools.py` keeps its stub branch only for import failure; I did not edit core/voice (voice lane owns it).
T019 · done · `uv run pytest core/tests/test_messages.py -q` · `message` rows with `msg_<MMDD>_<HHMM>_<n>` ids (memory mirror + Surreal `message` table via db.create_message); reset_demo seeds the pre-14:02 rows of `messages_reyes_seed.json`
T020 · done · same · LIVE on message → hub `chat{village, message}` to every non-elder socket + control; `services.post_message`; `chat:village` (last 50) on non-elder snapshots
T021 · done · same · `POST /villages/{id}/messages` (Bearer member token; elder/control 403) + `GET …/messages?after=&limit=&kind=`; `@Village…` → `core.builder.ask(village, question)` when importable, else fixed fallback text with `refs` = last decisions from the log; answer posted as `kind answer, reply_to` · mocked: builder ask absent in this branch → fallback answer
T022 · done · same · incident upsert posts one `kind incident` village message (refs: incident event, verification, incident); 15:00 rota nudge for the on-duty member citing the `shift` row (scheduler; background ticker every 1 s also closes verifications at their deadline) · proposal/receipt hooks: not wired (watcher/release lanes own those rows)
T-hook · done · `uv run pytest -q` · `core/app.py` includes `router` and `admin_router` from `core.builder|release|memory|watcher.routes` when importable (`/health.lanes` shows which); lifespan: memory runtime start/stop (VILLAGE_MEMORY=off skips), release sandbox pre-warm in the background; `POST /admin/reset` scopes `events_today, verifications, proposals, tokens, counters` (+ `core.watcher.routes.on_reset`); `uv run python -m core.tools.warm` → release warm
T-kit · done · `uv run pytest -q`, `acceptance/run.sh V1 --lane core` · control snapshot binds every view key (per-member keys as Marco); `control{counter phones_live}` on member connect/drop; `control{reasoning}` with `mode`, `control{ledger}` rows (tool calls, dial, verification), `control{caption}` per phone-line utterance; `GET /villages/{id}/qr?kind=app|join&format=json` (control token) + `POST /auth/redeem` (sets consent/phone on the member; the dialer uses the redeemed phone); `/clock/warp {minutes}|{to}`; release POST guarded by the control token; `core/llm.py`: haiku roles → BEDROCK_HAIKU_MODEL, direct Anthropic only with ANTHROPIC_WORKSPACE_ID
T-live · done · own instance on :8791 (`VILLAGE_DIALER=fake VILLAGE_MEMORY=off SURREAL_DB_URL=`), `uv run python acceptance/v1_flow.py --url http://127.0.0.1:8791` → OK (3 runs). Start + denied frames as received:
- carmen: event:money_request → event:verification_pending{alerts:active} → event:pattern → event:verification_denied{alerts:active} → event:incident{alerts:active,incidents:open} → event:ack{incidents:open}
- ana: event:money_request → event:verification_pending{alerts:active} → event:pattern → event:verification_denied{alerts:active} → event:incident{alerts:active,blueprint:life_areas,incidents:open} → chat:incident → result → event:ack{incidents:open}
- marco: event:money_request → event:verification_pending{alerts:active,verifications:mine,verifications:pending?member=me} → event:pattern → prompt → prompt{closed} → event:verification_denied{alerts:active,verifications:mine,verifications:pending?member=me} → event:incident{alerts:active,incidents:open} → chat:incident → event:ack{incidents:open}
- control: control:counter → control:caption → control:gate → control:reasoning → event:money_request → event:verification_pending{alerts:active,verifications:mine,verifications:pending?member=me} → event:pattern → control:ledger → control:ledger → control:ledger → control:ledger → event:verification_denied{alerts:active,verifications:mine,verifications:pending?member=me} → event:incident{alerts:active,blueprint:life_areas,incidents:open} → control:gate → control:reasoning → control:ledger → control:counter → chat:incident → event:ack{incidents:open} → control:caption → control:ledger → control:caption → control:gate → control:reasoning
LD-9: Control frames go through the LIVE queue like events so the Control Room sees ledger order (gate/counter after the events they explain).
LD-10: Tests and acceptance force `SURREAL_DB_URL=` + `VILLAGE_MEMORY=off` + `VILLAGE_DIALER=fake` (core/conftest.py, v1.sh): reset_demo otherwise wipes the shared Surreal Cloud DB.
LD-11: Contract 1.2.1: decision rows carry top-level `mode` (no more `refs` mode); `control{gate}` stays schema-clean (kit derives mode); ledger `role`/caption `speaker` are lowercase enums.

## pitch
READY FOR MERGE PITCH-2
READY FOR MERGE V0
P001 · done · README.md (identity, arc, architecture, run, sponsors, safety rules with test names, real vs mocked, measured numbers, D25 pointer, team) · numbers only from RESULTS.md; 3 [MEASURE] rows
P002 · done · docs/DEVPOST.md (V0 ready; V1–V4 [PENDING Vn]; numbers table; video shot list; 10 Q&A) · [MEASURE]/[PENDING] left in V1–V4 and shared tables only
P003 · done · `CORE_URL=http://127.0.0.1:8799 scripts/reset_demo.sh` twice against a throwaway Core (SURREAL_DB_URL empty): exit 0, identical checklists; wrong ADMIN_KEY → exit 1 with manual command · warm is a stub
LD-1 (resolved after merge: admin reset now honours scopes): `POST /admin/reset` ignored `scopes` and runs the full `core.fixtures.reset_demo("v_reyes")`, so step 3 (`core.tools.seed`) repeats the same reset in a separate process. With `SURREAL_DB_URL` set, seed clears and reloads SurrealDB Cloud but cannot touch the running Core's in-process mirror; harmless today, but the scopes are cosmetic.
LD-2 (resolved: warm now calls the release lane; reset flags absent/failed): `core.tools.warm` was a stub (`print("warm OK (stub)")`); reset_demo.sh flags it as STUB in the checklist until the release lane replaces it.
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
P007 · done · PITCH-2: merged main; README + DEVPOST "How Village builds any group" with both villages' numbers; every [MEASURE] RESULTS answers filled; challenges and team per D26/D28; SLIDES + shot list per D29/D30; CHECKPOINTS 12:15 filled; reset_demo.sh defaults to :8790 (D27)
LD-6: "245 Python tests" measured by the pitch lane: `SURREAL_DB_URL= VILLAGE_LLM=off VILLAGE_MEMORY=off uv run pytest -q` → 245 passed at 2c8c3db. Not yet in RESULTS.md.
LD-7: Spine is "about 130 ms" (RESULTS); the brief's "100–130 ms" has no source, so the pages say about 130 ms.
LD-8: "Sonnet 5.5 + Haiku 5.5 via the Anthropic API" has no measured run in RESULTS/LANE-REPORT (release LD-3: key 400 without workspace id). Pages say Core uses them with Bedrock Haiku 4.5 fallback, and that every measured run used Haiku 4.5.

## builder
READY FOR MERGE V2
T001 · done · `uv run pytest core/builder -q` · tool registry (extract_blueprint, render_app, patch_app, cite_answer, classify_intent; record_answer + critique_plan local) closed schemas
T002 · done · `uv run pytest core/builder -q` · pydantic mirror + invariants; `contract_errors()` validates any contract $ref (frames tested against ws_messages control)
T003 · done · `uv run python -m core.builder.prompts --probe --prompt local` · Prompt Hub path untested (arize SDK not installed) → local prompt
T005 · done · `uv run pytest core/builder/tests/test_blueprint.py -q` · streamed extract_blueprint, partial-JSON (jiter) → one reasoning + blueprint frame per finding, invented people dropped; deltas recorded from a REAL Bedrock Haiku 4.5 stream (`core/builder/tests/data/reyes_blueprint_deltas.jsonl`)
T006 · done · `uv run pytest core/builder/tests/test_mapping.py -q` · roles per kind, profile enums, channels without lid_qr, fridge card only, ensure_chat, D22 elder check (TonightCard + 3 BigButtons + 911)
T007 · done · `uv run pytest core/builder/tests/test_render.py -q` · gather per role, 45 s/role, 60 s total, one repair, template fallback, per-role frames + ledger rows; fake LLM: valid / repaired / template / timeout
T008 · done · `uv run pytest core/builder/tests/test_templates.py -q` · fixture per (kind, role) with id/name remap, `mode: fixture`, decision "template <role>: <reason>"
T009 · done · `uv run pytest core/builder/tests/test_founding.py -q` · found(): listening → clarify (intake turns) → working → draft → review; BuilderRun; spans via tracer port (no-op until core.obs)
T010 · done · `uv run python scripts/build_village.py --llm off --replay --time` · `--kind block`, `--resume 8` (stdin), `--llm on`, `--ask`; `scripts/validate_spec.py <file>`
T011 · done · `uv run pytest core/builder/tests/test_routes.py -q` · `core/builder/routes.py` router (core already lists it in LANE_ROUTER_MODULES): POST /villages (202, `?resume=N`, `replay`, `mode: fixture`), GET (ETag, `builder` summary with question/meter/gaps), POST answers (meter + next_question preview), PATCH draft (allowed paths or word edit), POST activate, POST ask
T013 · partial · test_routes · activate mints per-member invites (sha256 at rest, 24 h, 409 on repeat); QR SVG via `segno` only if installed (not in pyproject → `svg: null`); redeem lives at `POST /builder/auth/redeem` because core already owns `/auth/redeem`
T014 · done · `uv run pytest core/builder/tests/test_ask.py -q` · material cap 60, cite_answer, hallucinated ids dropped, redaction (family word, phones, account numbers), family-word question refused; "why Marco and not Lucía" → 2+ citations model-off
T015 · done · `uv run pytest core/builder/tests/test_patch.py -q` · RFC 6902 (add/remove/replace/move/copy/test) on a copy, needs_added merged, one repair, safety refusal; prompt Examples 4–6
T016 · done · `uv run python scripts/build_village.py --llm off --replay` · `data/builder/reyes_intake.jsonl` = A0–A12 verbatim from docs/FOUNDING-INTAKE.md; replay runs REAL DailyMed (live) + the consent call through the Dialer port (scripted answer)
T018 · done · `uv run python scripts/build_village.py --llm off --replay --kind block` · block village born through the same intake (`data/builder/w147_intake.jsonl`, `data/intake/plan_block.json`); names/roles/views match block_spec.json
T021 · done · test_mapping / test_render · one VillageChat per non-elder view after merge and in templates
T025 · done · `uv run pytest core/builder/tests/test_capabilities.py -q` · `core/agent/capabilities.yaml` 8 capabilities; Reyes Carmen → phone_line + check_in_call + fridge_card, Marco → is_it_my_turn + refill_day, Ana → dashboard + village_chat; block differs; decision rows with reasons
T026 · done · `uv run pytest core/builder/tests/test_critique.py -q` · one critique call before render, diff applied (unsafe adds refused), EVALUATOR span
T027 · done · test_founding · DailyMed per med (httpx, url provenance, live in scripts / recorded in tests) and the helper's availability+consent call via Dialer port, as 1.2.1 ledger rows updated in place
T028 · done · test_founding · P-QH-01 21:30–07:00: `pending_her_words` + welcome call 13:30 after the intake (D29); confirmed form with `source{call, welcome_call, 108}` + her words when the welcome call is on record; `founding.confirm_quiet_hours()` for the voice lane
D29 · done · `uv run pytest core/builder/tests/test_conversation.py -q` · `data/intake/plan.json` (10 topics), record_answer (rules model-off; model merged when on), meter "N of 10 covered · gaps" (A0→1 … A11→10 exactly as the doc), "I don't know" → unknown gap, review word edit → RefillCard in Lucía's (helper) view, family word never in frames/decisions/spec/summary
D30 · done · `grep -ri -E "carmen|marco|lucia|reyes" core/builder --exclude-dir=tests` → empty · per-kind data in `data/builder/villages.json`
LD-1: Sonnet 5.5 rejects forced `tool_choice` ("tool"/"any") and thinking `disabled`; the port sends `tool_choice: auto` + "respond only by calling <tool>" + `thinking: between_tools` on Anthropic, forced tool_choice on Bedrock.
LD-2: decision rows carry top-level `mode` (1.2.1); questions/answers/review are `asked_human`, work is `acted_alone`.
LD-3: the draft starts from the kind's template (fixture) and the intake overwrites what the conversation said (days, notes, contacts, consent, needs' spans, P-QH-01); views are rendered by the model when on, template when off. People not in the words are kept from the record with a decision note "confirm on review".
LD-4: `blueprint.description.text` = opener + the founder's answers (family-word answer and review edit excluded), ≤ 2000 chars, so every need's source_span points at words the founder said.
LD-5: contacts (neighbor, super) stay role labels in the center's notes, not people (D29 "four people").
LD-6: the helper view starts without RefillCard so the review edit ("Lucía should see the refill list too") is a real patch; Marco and Lucía share the `helper` view key.
LD-7: the family word stays in IntakeState/BuilderRun only (never in frames, decisions, the spec's printables, or `summary()`); core must fetch it from the run if it prints the fridge card.
LD-8: `uv run pytest core` in ONE session errors in the gate's forbidden-import guard (httpx loaded by another suite); each suite passes alone (gate 110, core/tests 40, voice 31, builder 44).
Mocked: consent-call ANSWER (ScriptedConsentDialer; real ElevenLabsDialer only with FOUNDER_LIVE_CALLS=1), tracer (no core.obs yet), Prompt Hub, services (MemoryServices / CoreServices write-through), segno.
Timings (real, Sonnet 5.5 direct via core.llm, `uv run --with boto3 python scripts/build_village.py --llm on --replay --time`, final run): blueprint TTFT 3.8 s, blueprint 11.5 s, render elder 8.8 s / coordinator 9.7 s / helper 16.8 s (repaired once), render wall 16.9 s, DailyMed 4 meds live 0.22 s, total 65.8 s for the full 11-question intake (≈3.4 s per record_answer turn) + critique; meter sequence 1,2,2,3,4,5,6,6,7,8,9,10 = the doc; spec valid; critique applied 1 change; family word absent from frames/run/spec. Earlier runs: 59.4 s / 81.3 s. Bedrock Haiku 4.5 blueprint stream: TTFT 1.1 s, 8.8 s. Model-off replay: 0.27 s. Receipts: `data/builder/out/care_llm_on/{spec.json,run.json,frames.jsonl}`.
`--resume 8` through core's app (TestClient over `core.app`): POST /villages?resume=8 → 202; GET shows "8 of 10 covered · 2 gaps | Her phone and her language…"; 3 POST answers → 9/10, 10/10, review patch "RefillCard added to Lucía's view (helper)"; activate 200.
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
## kit
READY FOR MERGE V2c
Acceptance: `kit/scripts/acceptance_v2.sh` (npm test 57/57 + build + Control Room suites). Offline: `cd kit && npm run dev` → `/control.html?fake=control&seq=founding|scam|release|evolve` (`&tail=denied|timeout|confirmed`, `&speed=<x>`); real: `/control.html?t=<CONTROL_TOKEN>`. All frames (sent + received) on `window.__frames`; `window.__fake.warp(30)`.
S1 · done · `cd kit && npm test` · contract 1.2.0: RefillCard/TonightCard are contract types (strict props per schema), `prescriptions:current` in the bind grammar, hello `contract_version:"1.2.0"` (+ optional `view_as`), identity chip reads `snapshot.identity`; D22 overlay, `withRefill` and `?demo=refill` removed — fake Core sends rev-5 views unchanged and the fixture's real `bv_prescriptions` · mocked: nothing new
T020 · done · `npx vitest run tests/control.scene.test.ts tests/control.room.test.tsx` · `theme/a.css` Direction A tokens (phones light #FBF6EE in #2C2621 bezels), header (tabs Reyes/West 147th, phones-counter dots from `control{counter phones_live}`, demo clock from `control{clock}` + `+30m` → `POST /clock/warp`), 12-col grid, pure `control/scene.ts` reducer over every frame (snapshot/event/control reasoning|blueprint|gate|release|qa|build_log|counter|clock|proposal|caption|ledger) · warp mocked offline
T021 · done · control.room "Blueprint region" (reyes + block fixtures) · quote with need `source_span` highlights by life area, area chips, people cards (channels from `spec.channels`, capability reasons from profile/consent), rules in plain words, group type from `village.kind`; founding stream (`control{blueprint}` stages) overrides snapshot · none
T022 · done · control.room scam test · quote (es + English), 5-bar waveform, 45 s conic ring from `verification.deadline` on server clock, Village node + flow lines, collapses to the outcome on denied/confirmed/timeout; motion off under reduced-motion · none
T023 · done · control.room phones test · three read-only Renderers (buttons disabled, captions on) from the control snapshot's whole spec under "village.app/v/reyes · one site · three people"; View as opens a second read-only `hello{view_as}` socket so the main stream keeps flowing, focused phone morphs to the live member snapshot, others dim · control snapshot `data` = merged fixture data offline
T024 · done · control.room scam test · gate feed newest first with rule ids + Spanish say captioned; DecisionsLog with D23 role names (Founder/Watcher/Verifier/Builder/Explainer) and mode chips; running counts acted_alone/asked_human/refused · mode derived (LD-10)
T025 · done · control.room ask tests · `POST /villages/{id}/ask {question, lang}` bearer control token → answer + citation chips; disabled in flight; empty ignored; failure = plain words · offline answers canned
T026 · done · control.room QR test · `GET /villages/{id}/qr?kind=app&format=json` (svg if given, else `qrcode.react` from url); Be Marco first + sage; 409/failed → "Join codes appear once the village is live" · offline URLs point at `?fake=<member>`
T042 · done · control.room captions test · every `[data-say]` on the elder mirror has an English caption sibling; glossary = live `control{caption}` pairs + kit es/en tables (reverse) + reviewed elder copy + patterns; captions layer at the bottom of the projector · live ASR captions need Core (LD-9)
Founder ledger · done · control.scene tests · 6 states (queued/running+elapsed/done/retrying/fallback/refused), rows update in place, never vanish; derived from blueprint stages, reasoning plans/notes, verification lifecycle (pending→done/fallback), release/qa stages, proposals
T027 · partial · roles test · RefillCard on bv_prescriptions (schedule, superseded struck through, source), TonightCard template; LifeAreas/PillOrganizer unchanged from V0 · none
T028 · partial · `npm run build` · vite-plugin-pwa manifest + denylist from V0; no icons / offline last-snapshot shell yet
T029 · done · `kit/scripts/acceptance_v2.sh` · PASS
LD-9: Two control kinds the kit accepts that are NOT in contract 1.2.0: `caption {es, en, speaker?, final?}` (D18 live call captions) and `ledger {id, status, what, result?, role?, attempt?}` (explicit founder work-log rows). Unknown kinds are ignored, so Core can start sending them any time; contracts should add them (or core sends them anyway).
LD-10: D23 `mode` isn't on `control{reasoning}` (payload is additionalProperties:false; core LD-2 stores it in decision `refs`). Kit uses `payload.mode` if present, else gate decision → mode (deny/advise_do_not_send/refuse_medical_advice/report_already_logged = refused; verify_with_member/escalate/require_approval/advise_talk_to_coordinator/verify_with_source = asked_human; rest acted_alone) and words for non-gate reasoning. Gate reasoning rows aren't double counted; the window-closing tick (allow + empty say) isn't counted.
LD-11: Reasoning source → role: builder = Founder while a founding blueprint stream is open, else Builder; release = Builder; evolve/memory = Watcher; gate/voice = Verifier; Ask box = Explainer.
LD-12: The West 147th tab opens its own control socket (`hello{village:"v_w147"}`) once and keeps it; switching tabs doesn't reconnect the main socket.
LD-13: `VillageSocket.onFrame` replays the control socket's last 500 frames to late subscribers (the snapshot arrives before React mounts).
Open risks / core asks:
- Core: control snapshot `data` should carry every bind any view uses (elder `rota:current.on_duty`, coordinator binds, helper `rota:current?member=me` has no "me" for control) or the three phones show empty cards.
- Core: send `control{counter name:"phones_live"}` on each socket connect/drop (one dot per socket); otherwise the counter shows 0.
- Core: honour `hello.view_as` for the control token on a second socket and keep it read-only; send `snapshot.identity`.
- Core/contracts: `mode` on reasoning payloads (LD-10) and the caption/ledger kinds (LD-9).
- Core: `GET /villages/{id}/qr?format=json` with the control bearer, `POST /villages/{id}/ask`, `POST /clock/warp` — all coded against openapi, not run against a live Core.
- Bundle: control entry 48 kB (17.5 kB gz) + shared chunk 243 kB (65 kB gz, includes fixtures for offline mode).
## memory
READY FOR MERGE V4-MEMORY
T001/T002 · done · `uv run pytest core/memory/tests/test_client.py -q` · `core/memory/client.py` async httpx client (remember_fact, remember_transcript, fact_history, entity_facts, facts_for, uncertainties, resolve_uncertainty, query, forget_scope); labels src=/secs=/url=/agent=/village=/event=/quote=; 2 s connect / 8 s read (25 s for query + infer:full); `degraded: true` + reason on any failure, never raises; scopes `village` → `village/<v>` → `village/<v>/<member>` registered once per process (201/409 OK) · mocked: HTTP via `core/memory/fake.py` (FakeAgentMemory MockTransport, shapes from the live probe)
T005 · done · `uv run pytest core/memory/tests/test_outbox_subscriber.py -q` · `outbox.py` JSONL log at `var/memory/outbox.jsonl` (enqueue/sent/retry/dead, folded on restart), ordered flusher every 2 s, backoff 1 s…10 min, 4xx → dead; enqueue adds < 5 ms and makes no network call; `ledger_subscriber.py` maps dose, dose_repeat*, med_change (prior 5 mg + 10 mg on `lisinopril_dose`, in order, correct observed_at), money_request, verification_*, incident, consent, shift, call_*, release; consumes the voice post-call outbox (`core/voice/memory_outbox/*.json` → infer:full transcript with session_id + `last_call` fact; consumed once); `runtime.py` start/stop/health for core's lifespan · mocked: HTTP
T009 · done · `uv run pytest core/memory/tests/test_views_routes.py -q` · `views.py` + `routes.py`: GET facts (subject, as_of), GET history, GET uncertainties, POST resolve (X-Member-Id, default m_ana; writes an asked_human decision row); every response validated against `facts.schema.json` in tests; memory down → same shape from the ledger mirror with `degraded: true` in < 2 s; memory up but empty → `degraded_reason: outbox_backlog`; resolve with memory down → 503 `{degraded: true}` · mocked: HTTP
T-seed · done · `uv run python scripts/memory_seed.py` (REAL, Agent Memory context `village`) · forgets `village/v_reyes`, writes 31 facts via subscriber → outbox → client from `events_reyes_seed.json` + `reyes_family.json`; prints the lisinopril Fact view · mocked: nothing
T033/T036 · done · `uv run pytest core/watcher -q` · `core/watcher/rounds.py` `run_round(village_id, clock, services, memory, budget, ports)`: check-in call (Dialer port), missed-evening-pills nudge, "you're on tomorrow" nudge, refill-due (prescriptions + village meds), uncertainty re-ask, scam eval re-run (evals port), pattern → proposal (evals port, local fallback), carer-load (D24 #2, outside the budget). Budget default 3 autonomous actions; over budget → asked_human. Decision row per action with `mode`; refused rows cite P-QH-01 with source `call:welcome_call@108` and her words · mocked: Dialer = RecordingDialer (voice lane owns outbound), evals port absent on this branch (step skipped, local pattern fallback)
T-rounds-routes · done · `uv run pytest core/watcher/tests/test_rounds.py -k "routes or scheduler" -q` · `core/watcher/routes.py`: POST /villages/{id}/rounds/run (X-Admin-Key), GET /villages/{id}/rounds/latest, POST /admin/rounds/run, `on_reset(village)` hook, `RoundsScheduler` clock tick at 21:40 once per day; control{kind: reasoning, payload {source: evolve, kind: decision, text, village}} per action via services.control (validated against ws_messages control in tests) · mocked: none in the default deps (core.db, core.services, core.clock)

Measured (real Agent Memory, 2026-10-16 11:36 ET, `var/memory/seed_report.json`):
- write (infer:triples) p50 630 ms, p90 686 ms, max 814 ms, n=31; outbox drained 31 facts in 20.8 s (sequential, ordered)
- history p50 248 ms (3 runs: 248/266/227); facts view (m_carmen, 12 facts) 303 ms; facts view as_of 517 ms
- query (hybrid recall) now 3669 ms → "lisinopril dose is 10 mg"; asOf 2026-09-15 2900 ms → "5 mg"
- Fact view: CURRENT 10 mg since 2026-10-03, source call:conv_setup_0003 @88s "The doctor changed her lisinopril from five to ten on October third.", event ev_1003_1740_med_change; superseded 5 mg since 2026-09-01, source system:seed "Prior bottle in cabinet"; as_of 2026-10-02 → 5 mg
- integration (core app + both routers, real Agent Memory, in-memory ledger): POST /admin/rounds/run 519 ms; GET facts 268 ms; GET history 206 ms
- Real rounds counts on the seeded Reyes village (round at 21:40): **3 acted alone / 1 asked / 1 refused**: refused "Wanted to call Carmen for the evening check-in at 9:40 PM. Blocked by code: Carmen's rule, no calls after 9:30 PM."; acted: evening pills nudge to Marco, "you're on tomorrow" to Marco, metformin refill due 2026-10-18 to Lucía; asked: "Ana has taken 9 of the last 12 nights. Ask Lucía to take the Sunday call?" With the evals port wired (29/30 stub) + one open uncertainty, the test measures 4 / 3 / 1.

LD-1: Lenses are not hierarchical (verified live): `[["village/v_reyes"]]` misses facts in `village/v_reyes/m_carmen`, so `query()` ORs the village scope with every member scope.
LD-2: AM attribute rows carry `createdAt` = our observed_at and no separate transaction time; `recorded_at` comes from the ledger row (`event.at`) when matched, else observed_at.
LD-3: `facts_for(village)` reads one entity GET per entity known from the ledger mirror and filters on label `village=`; no list-all endpoint is used.
LD-4: decision.schema.json (1.2.0) has no `mode`; rounds rows carry top-level `mode` (tests validate against the schema plus `mode`). Contracts should add `mode: acted_alone|asked_human|refused` (core's services.py currently puts it in refs).
LD-5: Rounds evaluate "tonight" at 21:40 (after the evening dose window) regardless of when they are triggered, so the demo trigger at 14:00 gives the same measured counts.
LD-6: Carer load counts who covered each of the last 14 evenings: last `shift` row (assigned/swapped) for that date, else the rota. Oct 2–13 history is a watcher fixture (`core/watcher/fixtures/reyes_nights.json`, schema-valid shift events: Oct 4 and Oct 8 have nobody); the contracts seed only starts Oct 12. Without it the rota alone is balanced (Ana 2 / Marco 2) and no row appears (tested).
LD-7: med_change prior value (5 mg) takes observed_at from the matching prescription's valid_from (2026-09-01 in core.fixtures), else effective − 30 days.

Core must mount / call:
- `app.include_router(core.memory.routes.router)`; `app.include_router(core.watcher.routes.router)`; `app.include_router(core.watcher.routes.admin_router)`
- lifespan: `await core.memory.runtime.start(db)` after reset_demo; `await core.memory.runtime.stop()` on shutdown; optional `core.watcher.routes.RoundsScheduler(["v_reyes"]).start()`
- reset_demo / `POST /admin/reset`: `await core.watcher.routes.on_reset("v_reyes")` to run tonight's round on the fresh seed
- `/health.outbox`: `core.memory.runtime.health()`
- evals lane: expose `evals.rounds_port` with `async rerun_scam_set(village) -> {caught, total}` and `async detect_patterns(village, events) -> [{claimed_member_id, event_ids, count, text?}]`

## evals
READY FOR MERGE EVALS

Measured (Oct 16, eval clock 2026-10-16T14:02:09-04:00, Reyes fixture state with the Oct 9 seed request; numbers only from these runs):

| run | extraction | caught | false alarms | exact match | extraction p50 / p95 | output |
|---|---|---|---|---|---|---|
| local, model on | Bedrock `anthropic.claude-haiku-4-5` (50/50 model extractions) | **30/30** | **0/20** | 49/50 | 1206 / 1407 ms | `evals/out/scam_experiment_20261016T153025Z_model.{json,md}` |
| local, model off | deterministic rules | **28/30** | **0/20** | 47/50 | <1 ms | `evals/out/scam_experiment_20261016T154953Z_rules.{json,md}` |
| Arize experiment, model on | Haiku 4.5, task run by Arize SDK runner | **30/30** | **0/20** | 49/50 | — | dataset `village-scam-eval` id `RGF0YXNldDozNzAyMTc6SEFDcA==`, experiment `scam-model-20261016T153959Z` id `RXhwZXJpbWVudDoxNjIyNDM6aU1KYg==`; mirror `evals/out/arize_experiment_20261016T153959Z.json` |
| local, model off, `--village v_reyes` | rules | 29/31 | 0/20 | 48/51 | <1 ms | n_base 50 + n_village 1 (`evals/out/scam_experiment_20261016T154556Z_rules_v_reyes.*`) |

Definitions: caught = scam case mapped to verify_with_member / advise_do_not_send / deny. False alarm = benign case mapped to advise_do_not_send / deny, or to verify_with_member where the dataset expects record (3 benign rows expect verify_with_member: rent cash to Ana, $50 to Marco, Medicare number to Ana). Gate→dataset mapping is written out for all 14 gate decisions in `evals/scam_experiment.py` `DECISION_MAP`; no tool call = record. Haiku's one miss on exact match: se_b07 (Ana asks for rent cash) → no tool call → record (expected verify_with_member; still not a false alarm). Rules misses: se_s03 and se_s27 (no "ask" verb matched) → record.

- LD-1 scam experiment: `evals/scam_experiment.py` (+ `extract.py`, `reyes.py`): Haiku forced tool call (`report_money_request` | `not_a_money_request`) → claimed member resolved against Reyes members (unknown → None → R-MONEY-UNKNOWN; "asks Village to pay" → `money_transfer_request` → R-MONEY-NEVER) → GateInput (validated against gate.schema `gate_input` in tests) → pure `core.gate.decide` → score. JSON+MD report with per-case rows and timings. DONE.
- LD-2 Arize experiment: `evals/arize_experiment.py`, `arize[Datasets]<8` (`ArizeDatasetsClient.create_dataset` + `run_experiment`, evaluators `caught`, `false_alarm`, `decision_match`). DONE (ids above). Two earlier experiments (`scam-rules-20261016T153717Z`, `scam-model-20261016T153825Z`) are WRONG: Arize returns `is_scam` as a string, so benign rows were scored as scams. Fixed; see `evals/out/discarded/README.txt`. Ignore those two in the UI.
- LD-3 session eval + detector: `evals/session_eval.py` (`session_possible_fraud`, Haiku judge, rules fallback, EVALUATOR span, `update_evaluations` on the call root span, mirror `var/evals/sessions/<conv>.json`). Real run: conv_seed_1009 → possible_fraud 0.95 (Haiku), trace `a33eeac183244e9ccd30aff7e6fb7db6`; Arize shows the EVALUATOR span and `eval.session_possible_fraud` on the `call.session` root. `evals/detector.py` `detect_patterns(village_id, events)`: ≥2 money requests claiming the same member within 7 days → pattern with `evidence` (call_moment, trace, fact), schema-valid per proposal.schema `evidence`; seed Oct 9 + today → 1 pattern, 5 evidence rows. DONE.
- LD-4 incident → test (D24 #11): `evals/incident_to_test.py` appends `{utterance, expected_decision, …}` to `evals/sets/<village>.jsonl` on verification_denied/timeout (idempotent per verification id); `scam_experiment --village v_reyes` reports n_base + n_village. `evals/sets/v_reyes.jsonl` has 1 row (the Oct 9 timeout). DONE.
- LD-5 tracing: `core/obs/tracing.py` (`init_tracing` = arize-otel `register` + Anthropic instrumentor when ARIZE keys exist, else no-op; `span()` + `agent/tool/guardrail/chain/evaluator` decorators with session.id, graph.node.id, graph.node.parent_id, user.id). Real trace `9ea6655bab35c397925b58fcc13bf70d` in project `village`: CHAIN scam_eval.case > AGENT mom_line.extract > LLM messages.create, GUARDRAIL gate.decide (verified by span export). DONE.
- LD-6 tests: `uv run pytest evals -q` → 33 passed offline (model off, Arize mocked); full `uv run pytest -q` → 222 passed. Includes T007 import ban (core/gate, core/voice/tools*.py import no evals/arize/core.memory/core.obs). DONE.
- LD-7 rounds port: `evals/rounds_port.py` `async rerun_scam_set(village)` → {n_caught, n_total, n_false_alarms, n_benign, n_base, n_village, caught, total, …} (rules unless VILLAGE_LLM on; report to `var/evals/rounds/`), `async detect_patterns(village, events)` → patterns with `claimed_member_id, event_ids, count, text, evidence` (the shape rounds.py reads; evidence rows inside). DONE.

Commands:
- `VILLAGE_LLM=on uv run --with boto3 python -m evals.scam_experiment --mode model`
- `uv run python -m evals.scam_experiment --mode rules [--village v_reyes]`
- `VILLAGE_LLM=on uv run --with boto3 --with 'arize[Datasets]<8' python -m evals.arize_experiment`
- `VILLAGE_LLM=on uv run --with boto3 --with arize python -m evals.session_eval conv_seed_1009`
- `VILLAGE_LLM=on uv run --with boto3 python -m evals.trace_smoke`; `uv run python -m evals.detector`; `uv run python -m evals.incident_to_test v_reyes`

Notes for core / orchestrator:
- `core.llm` Bedrock path needs `boto3` (not in pyproject; evals uses `uv run --with boto3`). An empty `AWS_BEARER_TOKEN_BEDROCK=` in .env makes Mantle send `Bearer ` and fail with "Connection error"; `evals/env.py` drops empty AWS_/ARIZE_ vars. Core should do the same or remove the empty line.
- `llm("haiku")` maps to the Sonnet slot (role not in {watcher, verifier, explainer}); evals pins `BEDROCK_HAIKU_MODEL`. Harmless today (both are haiku-4-5).
- The `arize` SDK (v7 and v8) shadows `arize.otel` from arize-otel when layered on; `core/obs/tracing.py` re-exposes it.
- Mantle rejects `temperature`; the extraction runs without it (Haiku extractions are not guaranteed deterministic across runs).

Open risks:
- The rules extractor was written with the 50 cases visible: treat 28/30 as a regression baseline, not a generalization claim. The Haiku prompt names the Reyes family; same caveat, smaller.
- Dataset is 50 hand-written cases (30/20); a perfect score on it is not a field rate. Pitch should say "on our 50-case eval set".
- The detector's `fact` refs are synthesized keys (`fact:money_request:<subject>:<date>`), not read back from Agent Memory.

## platform
READY FOR MERGE PLATFORM

Branch `platform-sweep` (worktree `/Users/rgomez/village-platform`), D30 sweep: no village names or ids live in `core/` anymore.

- **Grep** `grep -ri -E "carmen|marco|lucia|lucía|reyes|ana\b" core --exclude-dir=tests`: **231 hits in 35 files before** (185 of them outside the allowed `core/watcher/fixtures/`; the 265 figure was from 12:05), **46 hits in 1 file after**, all of them in `core/watcher/fixtures/reyes_nights.json`, which is an allowed home. Outside the fixtures it returns nothing.
- **Tests**: `SURREAL_DB_URL= VILLAGE_MEMORY=off VILLAGE_DIALER=fake uv run pytest -q` → 249 passed (245 + 4 new). `acceptance/run.sh V0 --lane core` and `acceptance/run.sh V1 --lane core` (real-socket scam flow) both pass.
- **Village registry**: `data/villages/index.json` maps each village id to its contract spec, data file, seed events, seed messages and seed prescriptions. `core/village.py` holds every lookup: default village, spec (live `db.specs` first, else the fixture), people, coordinator, care recipient, verifier, on-duty fallback, relationship word, family word, quiet hours. It also has the pure `state_from_spec()`, which builds GateInput.village_state from a spec (P-QH-01, R-MONEY-DEFAULT and R-MONEY-VERIFY params, pronoun from relation).
- **Files changed**: `core/village.py` (new), `core/settings.py` (`DEMO_VILLAGE_ID`), `.env.example`, `data/villages/index.json` (new), `core/fixtures.py`, `core/app.py`, `core/bindings.py`, `core/ws_hub.py`, `core/services.py`, `core/gate_fallback.py`, `core/db.py`, `core/dialer.py`, `core/auth.py`, `core/routes/{ws,clock,admin,verifications,join}.py`, `core/gate/say.py`, `core/gate/rules/{common,money}.py`, `core/gate/sm_verification.py`, `core/voice/{init_hook,tools,outbound,post_call}.py`, `core/memory/{client,conventions,ledger_subscriber,views}.py`, `core/watcher/{rounds,routes}.py`, `core/release/{service,evals,floor_tests}.py`, `core/obs/tracing.py`, `core/tools/{seed,wsclient}.py`, and the new test `core/gate/tests/test_two_villages.py`.
- **Two-village gate test** (`core/gate/tests/test_two_villages.py`, 4 passed): it builds village_state from `reyes_spec.json` and `block_spec.json` with the same `state_from_spec`, then runs the same rules on both.
  - P-QH-01: a dose-window tick at 21:50 sends no reminder in the care village (its quiet hours are 21:30-07:00) and sends `remind` in the block (its spec has no P-QH-01).
  - R-MONEY-DEFAULT: a verification answer of `no` or `unsure` gives `advise_do_not_send` in both villages. The notify goes to that village's own coordinator (`m_ana` vs `b_tanya`), and the `say` text names that coordinator, so the two decisions differ.
- **Both villages served at once**: one Core process, one `reset_demo()`.
  - `/ws?village=v_w147&m=b_tanya` → snapshot `{"village": "v_w147", "role": "coordinator", "member_id": "b_tanya"}`, identity Tanya / "West 147th Block — Heat & Blackout", 10-element coordinator view from `block_spec.json`. `m=b_tanya` with no village resolves to v_w147 as well.
  - `/ws?village=v_reyes&m=m_ana` → `{"village": "v_reyes", "role": "coordinator", "member_id": "m_ana"}`, identity "Familia Reyes".
  - `/ws?village=v_reyes&m=m_carmen` → `role: "elder"`.
  - `uv run python -m core.tools.seed --village v_w147` (or `--village v_reyes`, plus `--keep`) seeds any registered village.

### Lane decisions
- LD-P1: `DEMO_VILLAGE_ID` defaults to an empty string in `core/settings.py`. When it is empty, the default comes from `data/villages/index.json` `"default"`, so `v_reyes` appears only in `.env.example` and `data/`. A settings default of `v_reyes` would itself trip the grep.
- LD-P2: `reset_demo(village)` resets everything, seeds the chosen village, and also seeds every other registered village, so both villages are always live. `keep_others=True` re-seeds just one village.
- LD-P3: say templates take `{coordinator_name}` and `{recipient_name}`. `finish()` fills them from village_state. If a village has no such member, neutral words are used (es "su familia", en "your family").
- LD-P4: the live gate's quiet hours now come from the spec's P-QH-01 (`21:30-07:00`). `services._village_state` used to hardcode `22:30`. No test depended on the old value.
- LD-P5: the default money verifier is the first consented `money_verifier` who is not the coordinator. This is read from village_state members, because the gate schema forbids extra keys such as `trusted_contacts`. The default on-duty member is the first caregiver, helper or volunteer in the spec.
- LD-P6: the voice init hook finds the caller by phone among the village's spec people, and an unknown or empty caller resolves to the care recipient. The demo override is `DEMO_ELDER_CALLER_ID`. A spec-derived `DEMO_<RECIPIENT FIRST NAME>_CALLER_ID` is also accepted, so existing `.env` files keep working.
- LD-P7: slot words in the Spanish timeline come from `dose_slots[slot].spoken_es` in the village data file. Any word ending in "ana", such as "mañana", trips the `ana\b` grep.
- LD-P8: `outbound` `family_label` is now the spec's village name ("Familia Reyes"), not "the Reyes family".

### Open risks
- `db.events` and `db.verifications` are global lists. The bindings filter alerts, shifts, chat and money requests by village, but `open_incidents()`, `timeline()` and dose facts filter only by subject. They do not leak between the two villages today (the block has no incidents), but a block incident would show in any Reyes view that binds `incidents:open`.
- The block's own binds (needs, resources, rumors) have no bindings in core yet. Tanya's snapshot carries her view but its data is only `alerts:active` and `chat:village`.
- `step_verification`'s incident `notified` reads `current["coordinator_id"]`, and that is empty unless the caller sets it. In practice services overwrites it through `_enrich_incident`.
- The `core/memory/routes.py` header default still uses the default village's coordinator.
V2b (contract 1.2.1, D30) · `kit/scripts/acceptance_v2.sh` → npm test 67/67 + build + Control Room suites PASS
B1 village switch · done · control.room "switching village re-keys every region" · one control socket + one scene per village; the room remounts on switch (`key={village}`) so work log, Live, captions, decisions, gate counts, phones-live all clear; frames naming another village (`payload.village`, `event.village`, receipt/proposal village, snapshot.village) are dropped by the reducer; fake sequences are per village (Reyes scam never reaches the v_w147 socket); switching back rebuilds Reyes from its socket's frame log
B2 names · done · Blueprint region test (block) · `displayName` = `display_name`, else the full name (family surname dropped only when the village is "Familia X"/"X family"); never split on spaces ("Mrs. Gloria Alvarez", "The Okafor family (Ngozi & Daniel)")
B3 headline · done · control.room "live headline uses the proper-cased member name" · names from the member record (spec people → `member:<id>` → proper-cased id)
B4 caption bar · done · control.room "captions bar pads the room" · ResizeObserver pads `main` by the bar height + 32 px
F1 header · done · control.room header test · "Village ·" + switcher pills labelled `village.name` (snapshot spec, or `identity.village_name` before the spec exists) + "+ New village"; tagline always under the logo
F2 founding · done · control.room "New village …" + "founding replay" · empty state "No village yet. Describe your people." with a text box → `POST /villages {description}` → follows the returned `village_id` socket; later answers → `POST /villages/{id}/answers {answers:[{question,text}]}`; transcript left (caption speaker "ana" = coordinator's words, Founder `reasoning{kind:note}` = "now I know" + question), work log middle (ledger frames), blueprint right with coverage meter "N of 10 covered · M gaps" + gap list, phone skeletons ("Building <name>'s app…") until the spec snapshot arrives, then the live room · offline replay = docs/FOUNDING-INTAKE.md transcript (A0–A12 compressed)
F3 phones · done · control.room phones test · "<display_name>'s phone · right now" (care recipient) / "<display_name>'s phone"; join QR under each (`GET /villages/{id}/qr`), "Be <name>" sage on the helper the judge plays
1.2.1 frames · done · control.scene "1.2.1" test · `ledger` rows update in place by id (contract role/at/mode/elapsed_ms), `caption` → caption bar (speaker enum proper-cased), `mode` read from reasoning, ledger and gate (`decision.mode`/`payload.mode`) before falling back to the derived mode (LD-10 now only a fallback)
Phone bug · done · roles "call affordances" tests · every call is `<a href="tel:…">` (BigButton call_member/call_number, ContactCard); numbers from `member:<id>.phone` / any bv_person with that id / `identity.village_number` for "village"; unknown → disabled button with "no number"; read-only mirrors just disabled
SW update · done · ws "contract_mismatch → Updating…" tests · first contract_mismatch shows "Updating…", runs `registration.update()`, re-hellos once within 2 s; a second mismatch stops as before
Dead-man fix · done · founding replay test · the ping dead-man timer was armed after sending, so a synchronous pong (fake server) left it armed and the socket reconnected every 25 s; now armed before the ping
D30 grep · `grep -riE "carmen|marco|lucia|lucía|reyes|tanya" kit/src --exclude-dir=dev` → **0 hits** (fixture wording, fake Ask answers, fake QR, fixture caption lines and the fake village list live in `kit/src/dev/`); relationship words no longer hard-coded ("Here is what she was told", join page `?care=`)
LD-14: the switcher's village list = `?villages=a,b` (no list endpoint in openapi), offline = `dev/FAKE_VILLAGES`, plus any village created with New village. The member app's village = `?village` → `VITE_VILLAGE` → (offline) the first fake village.
LD-15: coverage meter = `control{counter name:"intake_coverage", value, of}`; gap list = `control{blueprint stage:"questions"}` items' `gap|topic|question` (builder lane: please emit these; no new contract kinds needed).
LD-16: member-app View-as options come from the coordinator's own `member:<id>` records (then the rota), cached while viewing as someone else.
Core asks (V2b): send `member:<id>` (bv_person with `phone`) for every call target in a view (Carmen for helpers, Ana for the elder) and `identity.village_number`, or the call buttons render "no number"; tag control frames with `payload.village` (caption/ledger/reasoning/blueprint do in 1.2.1; gate/counter/clock frames don't carry it, so Core must only send a village's gate/counter/clock frames on that village's control socket); emit `intake_coverage` + `questions` during founding.


## core-glue
READY FOR MERGE CORE-GLUE
Suite: `SURREAL_DB_URL= VILLAGE_MEMORY=off VILLAGE_DIALER=fake uv run pytest -q --import-mode=importlib` → 305 passed (default import mode fails collection on main too: `core/builder/tests/test_tools.py` vs `core/voice/tests/test_tools.py` share a basename, no `__init__.py`; not this lane's files). Acceptance: `./acceptance/v2.sh` (own Core on 8795, `VILLAGE_LLM=off`, FakeDialer) → 17/17 PASS, A2-10 skipped.
T1 · done · `pytest core/tests/test_core_glue.py -k member` + v2 "T1" step · `member:<id>` = bv_person `{member_id, name, phone}` + `{id, display_name, role}` for every call target (elder → coordinator; helper/coordinator → care recipient; control → everyone; plus any member id the view references); phone = live member row (redeemed judge phone) else spec person, E.164 only; `identity.village_number` from `VILLAGE_PHONE_NUMBER` else spec fridge card / `village.village_number` when E.164 · mocked: nothing
T2 · done · `pytest … -k control_frames` (two control sockets) + v2 "T2" step · `hub.control` adds `village` to reasoning/caption/ledger/blueprint payloads (the kinds whose schema allows it); delivery was already per village + control role only; member sockets never get control frames · gate/counter/clock/release/proposal payloads are additionalProperties:false, so they stay unkeyed in the payload (routing is by socket)
T3 · done · `pytest … -k intake_covered` + v2 "T3" step · on the builder's `counter{intake_covered}` Core derives `counter{intake_coverage, value, of}` + `blueprint{stage:questions, items:[{question:next}, {question:gap, gap:true}…]}` from `SESSIONS/RUNS` (`core/founding_glue.py`); family word never included · none
T4 · done · `pytest … -k get_villages` + v2 "T4" step · `GET /villages` (control bearer or `?t=`) → `[{id,name,status,kind,people_count,rev}]` from the registry + `db.specs` + builder runs (status `founding` until the spec is stored) · none
T5 · done · `pytest … -k redeem_falls_back` + v2 A2-7/A2-11 · `/auth/redeem` tries core invites, then the builder's `redeem()`; registers the builder token → (member, village) in `core.auth.ISSUED` so `/ws?m=` and hello pick the right village; judge phone written to the member row (or the spec person on id collision) → `member_phone` / snapshots; returns `consent_event`; views fall back to `db.specs[vid].views` · none
T6 · partial · `pytest … -k builder_spans` · `core.obs.builder_tracer()` adapts `obs.tracing.span` to the builder's Tracer port (session.id `village-<id>`, graph.node ids, nesting); `init_tracing()` at app start. One builder trace exported with `mode=arize`, flush ok: trace id `0eedbb372ad57b872b8b01247259d04e` (session `village-v_glue_trace`, spans builder.found → builder.blueprint) · landing in project `village` not confirmed from here (`ax` has no profile on this machine)
T7 · done · `pytest … -k fridge` + v2 "T7" step · `GET /villages/{id}/print/fridge` (control or that village's coordinator) → HTML following design/FridgeCard: Village line, 911 first, contacts with phones, family word only from `BuilderRun.family_word` (blank line otherwise, never the spec) · minimal styling
T8 · done · `./acceptance/v2.sh` · A2-1..9, A2-11 PASS; A2-6a: core's `/qr?kind=join` on a draft answers 200 `[]` (no codes) rather than 409 · A2-10 skipped (needs a seeded incident in a new village); model off (templates + heuristic answers)
LD-1: `member:<id>` carries both shapes (bv_person keys the kit reads + the requested id/display_name/role); the `member:` pattern has no schema shape, so this validates.
LD-2: Founding frames are derived in core from builder state rather than editing core/builder (lane boundary); trigger = the builder's existing `intake_covered` counter, so they arrive right after each processed answer.
LD-3: Builder-minted member tokens resolve through a core registry (`core.auth.register_token`) before the first-name `mt_` heuristic.
Open risks:
- Builder templates reuse the fixture member ids (`m_<first>`); `db.members` is keyed by id globally, so a new village's member with the same id as a seeded one is not written to `db.members` (the registry village keeps its row). Role/view still resolve, phone override lands in the new spec person; verification calls that read `db.members[id].phone` would dial the seeded member's number for that village. Fix = village-scoped member keys or builder ids that are unique per village.
- In-memory only: `ISSUED` tokens and builder `INVITES` are lost on restart (redeem before restarting the live Core).
- `.env` holds ARIZE keys, so a TestClient lifespan now registers the Arize exporter during tests (it already did lazily on first span).

## evolve
READY FOR MERGE V4

Branch `lane/evolve`. Owns `core/evolve/**`, `core/routes/proposals.py`, `acceptance/v4.sh` + `v4_flow.py`. Seams outside: `core/app.py` (+1 line: `core.routes.proposals` in LANE_ROUTER_MODULES), `core/services.py` (+24 lines: `approve_proposal` action seam, `_evolve_port` in `apply_verification_step`, `screen_caller` branch in `_handle_tool`), `core/village.py` (`receptionist_mode()`), `core/voice/init_hook.py` (`receptionist` init var), `core/voice/tools.py` (`screen_caller` in the standalone tool model).

Tests: `SURREAL_DB_URL= VILLAGE_MEMORY=off VILLAGE_DIALER=fake uv run pytest -q core/evolve` → 5 passed. Whole suite: main's `uv run pytest -q` already fails at **collection** (pre-existing on main at 12:40, not this lane: `core/gate/tests` import-ban trips when collected with other packages (httpx already imported), and `core/voice/tests/test_tools.py` clashes with `core/builder/tests/test_tools.py` basename). Split runs are green: `pytest -q core/gate core/voice/tests/test_tools.py` → 125 passed; `pytest -q --ignore=core/gate --ignore=core/voice/tests/test_tools.py` → 175 passed (170 before + 5 evolve).

- T030 · done · `pytest -q core/evolve -k options` · `consider_options` via `llm("watcher")` forced tool call (12 s timeout); model off/err/disagrees → canned (same 3 candidates, names from the spec). Stored in the decision row (`actor evolve, mode asked_human, options{...}`); emitted as `control{reasoning}` + 3 `control{ledger}` rows `opt:<dc>:<key>` (losers `refused` + one-line reason, winner `running` / result "testing" → `done` "passed the release gate" after release).
- T017a · done · `acceptance/v4.sh` · `propose()`: schema-valid Proposal (validated with `proposal.schema.json`), evidence from `evals.detector.detect_patterns` (Oct 9 seed + today's call: 5 rows), ops per role through `core.builder.patch` (elder: Spanish Text "Village contesta primero…" at children/1, keeps "Llamar a Village"; coordinator/helper: Text "Village answers unknown calls…" + Timeline "Calls Village screened"; catalog types only), `spec_ops` fridge card `family_word_first: true`, chat post `kind: proposal` (refs `{kind: proposal}`), `control{proposal}`, decision rows.
- T017b · done · `acceptance/v4.sh` · routes `GET /villages/{id}/proposals`, `GET …/proposals/{pid}`, `POST …/approve` (202; leader member token or control; `?wait=true` for tests), `…/reject`, `…/undo` (10 s window), WS action `approve_proposal|reject_proposal` (leader only). Approve → `verifying` → `run_release(trigger=proposal, proposal_id)` with the shared ReleaseService adapters (real Daytona/Anchor/evals when configured; fakes when `VILLAGE_EVOLVE_RELEASE=fake` or no Daytona key) → on `released`: store spec + views as rev N+1 (or the Builder's repaired rev), `patch{rev, base_rev, role, ops, proposal_id, highlight}` to every member socket of each role, fresh snapshot to control/other sockets, `control{proposal applied}`, chat `kind: receipt` (refs `{kind: release}`), decision rows; on `blocked`: status `failed`, rev N stays, receipt chat "Not published: …".
- T017c · done · `pytest -q core/evolve` · Undo: within 10 s restores rev N's spec as a new monotonic rev (N+2), resnapshots every phone, repoints the published bundle if rev N's dist exists, proposal → `rejected` (remembered).
- T017d · done · `acceptance/v4.sh` (auto path) · Watcher trigger: `services.apply_verification_step` → `_evolve_port` → `core.evolve.trigger.on_verification_resolved` (background, 2 s delay so the incident post lands first) when `detect_patterns` finds ≥2 money requests claiming that member within 7 days; `POST /villages/{id}/evolve/trigger` (control token; forced pattern from every money request on record when <2). One proposal per pattern (declined ones remembered); a demo reset (decision log cleared) forgets them.
- T019r · done · `acceptance/v4.sh` step 6 · Receptionist data side: `policies[R-MONEY-UNKNOWN].params.receptionist_mode = true` → `village.receptionist_mode()` → init webhook var `receptionist: "on"|"off"` (+ unknown-caller `today_summary` with the screening script) → voice tool `screen_caller` (contract below).
- T035 · done · `acceptance/v4.sh` (tests stage) · before the release `evals.incident_to_test.sync_from_events` runs over the live ledger, then `scam_experiment.load_cases(village)`: tests stage summary reads "Scored on 52 calls (last night's included) · N floor tests passed" (n_base 50 + n_village 2). Wrapped broadcast only (release lane's pipeline untouched).
- T024e · done · `acceptance/v4.sh` (fakes) and `ENV_FILE=~/village/.env acceptance/v4.sh --real` (real pipeline) · both green.

Mocked: fake release ports in tests and the default `acceptance/v4.sh` (FakeDaytona/FakeAnchor/FakeEvals); FakeDialer in both runs; model off in tests (canned options). The `--real` run used real Daytona build + floor tests + Anchor QA + release evals from `~/village/.env` (TUNNEL_URL blanked, RELEASE_LOCAL_BASE=8793).

### Measured (Oct 16, this Mac, Core on 8793)
| step | fakes | real pipeline |
|---|---|---|
| verification resolved → proposal on control (auto trigger, incl. 2 s delay) | 2169 ms | 2166 ms (first run 2148) |
| Ana's yes (approve) → every phone patched (carmen/ana/marco `patch`) | 108 ms | **7705 ms** (warm sandbox; first run 13381 ms) |
| release inside that (run_release) | 36 ms | 7632 ms (spec 23 · build 2065 · tests 1180 · Anchor 4106 · evals 2 · live 2) |
| spec store + patch fan-out after the release | 1 ms | 1 ms |
| consider_options, model on (Haiku 5.5 via `llm("watcher")`) | n/a | 5221 ms (canned: 0 ms) |

### LD-evolve
- LD-1: the contract's `spec_ops` only allow `/printables/`, and `village_spec` has no voice-line flag field. The receptionist flag lives in the spec as `policies[R-MONEY-UNKNOWN].params.receptionist_mode` (schema-valid: `params` is free props) and travels on the stored proposal record as a core-side `voice_ops` sidecar (not on the wire). `options` likewise is sidecar + decision row (proposal has `additionalProperties: false`). Contract follow-up: `spec_ops` path pattern `^/(printables|policies)/` and `proposal.options[]`.
- LD-2: `llm("watcher")` maps to **Haiku 5.5** in `core/llm.py` (`HAIKU_ROLES`), not Sonnet; options are good on Haiku (5.2 s). Model on needs `VILLAGE_LLM=on` (settings default off; `~/village/.env` doesn't set it).
- LD-3: undo publishes rev N's spec as rev N+2 (revs stay monotonic for the kit's base_rev check) and sends snapshots, not inverse ops. Proposal status after undo is `rejected` (contract has no `reverted`).
- LD-4: auto trigger defaults on, except inside unrelated pytest runs (`PYTEST_CURRENT_TEST`); force with `VILLAGE_EVOLVE_AUTO=on|off`. Delay `VILLAGE_EVOLVE_DELAY_S` (2 s).
- LD-5: release ports: `VILLAGE_EVOLVE_RELEASE=fake` forces fakes; otherwise the shared `ReleaseService` adapters (fakes only when no Daytona key).
- LD-6: `screen_caller` responses speak English to the caller (projector captions); Carmen's Spanish lines stay with the gate's `await_verification`.

### Voice tool contract for voice2 (`screen_caller`, Core side implemented)
`POST /tools/screen_caller` (same auth/headers as the other tools; idempotent on `conversation_id` + `tool_call_id` + phase). Only meaningful when the init webhook returned `receptionist: "on"` (else `data.status = "receptionist_off"`, `next: "connect"`).
Request: `{conversation_id*, caller_id*, utterance*, claimed_identity?, call_secs?, tool_call_id?, village_id?, amount?, method?, red_flags?, verification_id?, max_wait_s?}` (* required).
Phase 1 (no `verification_id`): agent opens with "<Name>'s phone, this is Village. Who's calling?" then calls with what the caller claims.
Phase 2 (with `verification_id` from phase 1): call again while the caller holds; Core waits ≤30 s for the real member.
Response: `{decision, say, say_key: "screen_<status>", rule_id, lang: "en", decision_id?, data: {status, next, verification_id?, claimed_member_id?, deadline?, state?, member_id?}}`. Speak `say` verbatim.
| data.status | when | say (example) | next |
|---|---|---|---|
| `pass_through` | known caller id + family word, no money ask; or phase 2 confirmed | "Thanks, Ana. Putting you through to Carmen." / "Marco confirmed it's him. Putting you through to Carmen. Village never sends money." | `connect` |
| `held` | claims a family member or asks for money → gate R-MONEY-VERIFY → app prompt + outbound call to the real member | "Thanks. I'm checking with Marco now on his own phone. Please hold." | `screen_caller` (phase 2) |
| `refused` | phase 2 denied / no answer, or gate R-MONEY-UNKNOWN (no member to verify) | "Marco says this isn't him. I won't put you through." / "I couldn't reach Marco, so I won't put you through. If this is really family, call back from a number we know." | `end_call` |
| `ask_purpose` | no claim, no money words | "Thanks. What is this about? Carmen asked me to take a message for callers I don't know." | `screen_caller` |
| `receptionist_off` | spec flag off | "" | `connect` |
ElevenLabs: add `screen_caller` (webhook, params above) to the mom-line agent; prompt branch on `{{receptionist}} == "on"` for callers whose `member_id` is `m_unknown`.

### Open risks
- Live server on 8790: the auto trigger fires on the first resolved scam call today (Oct 9 seed + today's = 2). If Act 2 is rehearsed twice without a reset, the second run says "already proposed" (by design); `POST /admin/reset` clears it.
- `run_release` holds the per-village release lock: a manual release running at approve time queues the proposal release behind it.
- Kit must apply `patch` frames for roles and render the elder Text/coordinator Timeline (catalog types only); control gets a fresh snapshot, not a patch.
- Core lane: please add `core.evolve.proposals.reset()` to `reset_demo` (today the prune-on-reset rule covers it).
V2c · `cd kit && npm test` 72/72 + `npm run build` · new suite `tests/village.patch.test.tsx`
Village on reconnect · done · village.patch "learns the village…" + "persists…" · the socket rebuilds its URL on every connect with the village it knows (snapshot.village, else configured) and always sends it in `hello`, so a reconnect is never `/ws?village=&m=…`; the member app stores the village next to the token (`village_id` beside `village_member_token`) and writes `?village=` into the address bar; `liveConfig` reads URL → stored village for that same token → `VITE_VILLAGE`; join stores `village` from the `/auth/redeem` response
Patch per role · done · village.patch "approve → release → patch" · Core's receptionist ops (copied from `core/evolve/proposals.py build_ops`) apply on the elder (Text at index 1) and helper (Text + Timeline) at `base_rev`, flash NEW from `highlight`, no reconnect, unknown-types=0 / invalid-props=0; a patch for another role or a stale `base_rev` is not applied and the client re-hellos with `last_rev` for a fresh snapshot
LD-17: a role-mismatched patch triggers a resync (re-hello) instead of being applied or silently skipped, so the rev never drifts.

