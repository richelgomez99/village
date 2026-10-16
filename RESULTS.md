# RESULTS.md: measured smoke-test results (Oct 16 2026). Overrides every other document on measured facts.

| # | Test | Result | Notes |
|---|------|--------|-------|
| 00 | env check (10:20) | PARTIAL | set: Daytona, Anchor, Arize, AWS_REGION. missing: SurrealDB (instance + memory), ElevenLabs, LLM creds (Anthropic key / AWS). TUNNEL_URL pending Funnel enable |
|| 01 | LLM (10:35) | PARTIAL | Bedrock Mantle us-west-2 lab account: **only `anthropic.claude-haiku-4-5` works** (TTFT ~520-600 ms). 404 for sonnet-5-5, sonnet-5, sonnet-4-5, haiku-5-5, opus-4-6. Decision: Haiku 4.5 on Bedrock for all roles until an Anthropic API key gives Sonnet 5.5 (fallback client). `output_config.effort` not accepted on Mantle |
|| 02 | Daytona egress (10:30) | PASS (as expected) | sandbox created, code_run ok. Sandbox egress BLOCKED to every tested host (anchor, surreal.cloud, bedrock-mantle, example.com, dailymed). Only build+test in the sandbox; Core pulls results |
| 03 | Daytona preview | not run | |
|| 04 | Daytona snapshot (10:30) | FAIL | `DaytonaForbiddenError: Failed to create snapshot: Access denied` (account tier). Fallback under test: sandbox from a public image / default image + npm install at runtime |
|| 05 | Anchor (10:30) | PASS | session, live view, NWS, cooling centers, web unlocker, agent.task all PASS; coned outage map WARN |
| 06 | SurrealDB Agent Memory (11:05) | PASS | context id `06gk9fu5…` (name `village`): whoami 445 ms; scopes registered; remember 5mg→10mg supersession PASS; query hybrid ~3.8–4.0 s; asOf 2026-09-15 returns 5 mg |
| 06b | SurrealDB Cloud LIVE (10:40) | PASS | instance `…aws-use1.surreal.cloud`, user `village` (ROOT OWNER). live() 110 ms; 10/10 notifications, **p50 22 ms, p95 77 ms, max 103 ms** insert→notify |
| 07 | Arize (10:42) | PASS (exporter) | register project=village; traced Bedrock haiku-4-5 call 1825 ms; CHAIN>AGENT>GUARDRAIL/TOOL spans; force_flush 326 ms. UI confirmation pending (operator) |
| 08 | tool server | RUNNING on :8787 | Funnel URL https://richel-macbook.tail8feae0.ts.net preset in .env; enable click pending |
| 09 | ElevenLabs (10:50) | PARTIAL | TTS PASS (50 KB mp3, 656 ms). Agent + tool + call blocked on TUNNEL_URL (Funnel not yet enabled by operator). Twilio number +1 848 257 9221 bought; upgrade + import pending |

## Spine (core lane, 10:37)
- 3 WS clients (elder/coordinator/helper snapshots from the Reyes fixture) → `POST /tools/log_dose` → gate → SurrealDB Cloud write → change feed → `event` frame on all 3 clients in **~130 ms** (tool call to last frame). Decision row written. `uv run pytest -q` 16 core tests + 49 gate tests green offline.

## Public URL (10:52–11:10)
- Funnel enabled; `https://richel-macbook.tail8feae0.ts.net/health` → 200 from Anchor's browser (external); Carmen's view opens on the operator's phone. The Mac itself cannot resolve `*.ts.net` (userspace tailscaled); test from outside only. Funnel verified → Core :8790.

## Release pipeline (release lane, 11:45; real Daytona + Anchor + Bedrock Haiku)
| Step (ms) | Cold, caught-and-fixed | Warm, caught-and-fixed | Warm, rev 5 |
|---|---|---|---|
| Sandbox create / reuse | 3444 | 149 | 108 |
| npm install | 2044 | — | — |
| Upload | 374 | 276 | 299 |
| vite build | 2192 / 2254 | 2103 / 2088 | 2083 |
| vitest (floor tests) | 1392 / 1461 | 1254 / 1160 | 1315 |
| dist download | 208 | 184 | 285 |
| Preview start | 1299 | 1420 | 1602 |
| Anchor QA (390×844) | 9101 | 5211 | 5359 |
| Evals | 3776 | 3249 | 3096 |
| **Total** | **29731** | **19908** | **14957** |
- Caught-and-fixed: r3 blocked "contrast 4.1:1 on elder Text (needs 7:1)" → model changed #4C80B4 → #2D5A8C → r4 live. Trace AGENT → TOOL daytona_build ✗ → LLM → TOOL daytona_build ✓.
- Second family (West 147th block): released in 13409 ms, 33 floor tests passing. 27 release tests offline.
- Anchor reached the build via the Daytona signed preview (Core's candidate route not yet mounted at run time); tunnel path is tried first once mounted.

## Agent Memory + nightly rounds (memory lane, 11:50; real context `village`)
- Writes p50 630 ms, p90 686 ms (n=31 Reyes facts; outbox drained in 20.8 s). History p50 248 ms; Fact view 303 ms; as-of 517 ms. Query 3.7 s (10 mg); asOf 2026-09-15 2.9 s (5 mg). Recall is never on a request path.
- Lisinopril Fact view: current 10 mg since Oct 3 (source call:conv_setup_0003 @88 s, quote, event ev_1003_1740_med_change); superseded 5 mg since Sep 1.
- Nightly round (seeded data, budget 3): **3 acted alone · 1 asked a person · 1 refused**. Refused: evening check-in at 9:40 PM, "Blocked by code: Carmen's rule, no calls after 9:30 PM" (P-QH-01, source welcome_call @108 s). Asked: "Ana has taken 9 of the last 12 nights. Ask Lucía to take the Sunday call?" Round through the core app: 519 ms. 37 memory/watcher tests offline.

## Scam eval experiment (evals lane, 12:00; 30 scam + 20 benign, `data/datasets/scam_eval_set.jsonl`)
| Run | Caught | False alarms | Exact decision match |
|---|---|---|---|
| Model on (Bedrock Haiku 4.5 extraction + pure gate) | **30/30** | **0/20** | 49/50 |
| Model off (rule-based extractor + pure gate) | 28/30 | 0/20 | 47/50 |
| Arize experiment `scam-model-20261016T153959Z` (dataset `village-scam-eval`) | 30/30 | 0/20 | 49/50 |
| Model off + Reyes incident set (D24 #11) | 29/31 | 0/20 | 48/51 |
- Caveat for the pitch: a 50-case hand-written set, say "on our 50-case eval set". Session eval labels the Oct 9 call `possible_fraud` (0.95); detector yields one pattern with 5 evidence rows.

## Platform (D30 sweep, 12:30)
- `grep -ri -E "carmen|marco|lucia|reyes" core --exclude-dir=tests` → 0 hits outside `core/watcher/fixtures/` (was 231 in 35 files). `data/villages/index.json` lists villages; `core/village.py` resolves people/roles/rules from the spec. One Core serves both villages (`/ws?village=v_w147&m=b_tanya` → Tanya's coordinator view; `v_reyes` → Familia Reyes). Two-village gate test: P-QH-01 suppresses a 21:50 reminder for Reyes (quiet hours 21:30–07:00), not for the block; R-MONEY-DEFAULT names each village's own coordinator. 249 tests.
- Voice: ElevenLabs mom-line calls failed instantly twice ("Missing required dynamic variables in first message") because the init webhook was not mounted on Core (405 at /) → webhooks grafted onto Core at /hooks/elevenlabs/{init,post-call}; agent now has default dynamic variables so a webhook failure can never drop a call.

## Evolve / live rebuild (evolve lane, 12:20; Core on 8793)
| Step | fakes | real pipeline (Daytona + Anchor + evals) |
|---|---|---|
| verification resolved → proposal (auto trigger, incl. 2 s delay) | 2169 ms | 2166 ms |
| **Ana's yes → every phone patched** | 108 ms | **7705 ms** (first run 13381 ms) |
| release inside that | 36 ms | 7632 ms (build 2065, floor tests 1180, Anchor 4106) |
| consider_options, model on | n/a | 5221 ms |
- Options weighed: "¿Es de verdad?" button (rejected: relies on her remembering under pressure), daily check-in call (helps; doesn't stop the call), **receptionist on her line** (chosen). Proposal validates against the contract with 5 evidence rows (Oct 9 + today). Receipt tests stage: "Scored on 52 calls (last night's included)" (50 base + 2 village). New voice tool `screen_caller` (hold → verify with the real member → refuse).

## First live call on the mom line (12:23; operator as Carmen, in English)
- Core log: `POST /hooks/elevenlabs/init` 200 (from 34.59.11.47) → `POST /tools/report_money_request` 200 → Marco's socket connected (operator's phone) → `POST /tools/await_verification` 200. Transcript: 1 s greeting; 18 s report → "Voy a confirmar con Marco ahora mismo. No mande dinero todavía."; 31 s await returned (Marco tapped "That wasn't me") → "Ese no era Marco. No mande dinero. Ana ya lo sabe."; 99 s `ask_family` → 404 (handler missing; fixed 12:55). Verification `ver_0001` state `denied`. Watcher auto-triggered at 12:23:58: weighed 3 options, proposed the receptionist (`asked_human`). Three prompt-guardrail events fired on Village's own refusal lines (passed; guardrail narrowed, D31). Call duration 109 s.

## Founding intake (builder lane, 12:40; Sonnet 5.5 via Anthropic API, full A0–A12 replay)
| Step | Time |
|---|---|
| Blueprint, first finding | 3.8 s |
| Blueprint, complete | 11.5 s |
| Render elder / coordinator / helper | 8.8 s / 9.7 s / 16.8 s (one repair) |
| DailyMed, 4 medications | 0.22 s |
| Whole 11-question intake | 65.8 s (~3.4 s per answer; earlier runs 59.4 s, 81.3 s) |
- Bedrock Haiku 4.5: first finding 1.1 s, blueprint 8.8 s. `--resume 8` through the routes: starts at 8/10, A10, A11, review edit (RefillCard for Lucía), "Draft ready · rev 5". Block village born through the same intake (`w147_intake.jsonl`).

## Live rebuild on the demo Core (13:00, operator tapped Approve on Ana's phone)
- Proposal created 13:00:22 (auto options + proposal) → Ana approved 13:00:44 → "Released rev 6 and patched every phone" 13:00:56: **12 s from the yes to every phone**, six stages passed (spec, daytona_build, tests, anchor_qa, arize_evals, live). Receipt: "Scored on 51 calls (last night's included)".

## Receptionist live (13:28; presenter's phone set to "unknown caller", receptionist mode applied at rev 6)
- Init webhook 200 with `receptionist=on, caller_known=false`. Luz answered "Carmen's phone, this is Village. Who's calling?"; the caller ("Richard from church") asked for Carmen twice; Village did not put the call through, asked the purpose, offered to pass a message, took a callback request; call ended by the caller at 76 s. No money/family claim → `screen_caller` was not needed (correct). Gaps: no AI disclosure in the receptionist greeting; the message was not relayed to the family chat; `calls:screened` stayed empty (post-call should log the screened call with outcome `message_taken`).

## Sponsor wow items confirmed (release lane real run 13:30; voice lane live push 13:20)
- **Anchor**: the receipt now carries the real MP4 recording (`recordings.fetch_primary_recording`, fetched 1.2 s after the session ends, 48,649 bytes, served by Core at `/releases/<rel>/qa/qa.mp4`); QA holds the screen 3 s so a recording exists (stage 5.3 s → 8.3 s).
- **Daytona**: receipt lines "sandbox 1172d474 · daytonaio/sandbox:0.8.0 · build 2.1 s" and "52/52 floor tests · 1.2 s"; blocked r3 reads "contrast 4.1:1 on elder Text (needs 7:1) · 50/52 floor tests".
- **Model chip**: evals stage "evals passed · Anthropic · claude-haiku-5-5 · 2686 ms TTFT" (provider/model read from the client; Bedrock Haiku 4.5 when the API key is absent).
- **Arize**: `human_approval` annotation (label approved, score 1, annotator = the approving member) written on the release span via `update_annotations` (1 span updated) + span attribute `human.approval`.
- **ElevenLabs**: live mom-line agent now has 4 evaluation criteria (safe_money_outcome, verified_with_real_member, usted_register, ai_disclosed) and data collection (claimed_identity, amount, outcome, caller_language); the model repair in the caught-and-fixed build is now done by the model (was silently falling back).

## Stage arc rehearsal (scripted, from a fresh reset; 13:58)
- reset 6–8 s → founding resumed at 8/10 (fixture mode) → 3 typed answers → draft rev 5 in ~11 s → scam reported (tool path) → Marco "no" → **auto proposal 7 s after the refusal** (14-day pattern window; the demo clock puts the Oct 9 seed 7.06 days back) → approve → **applied in 18.4 s** (real Daytona + Anchor with recording + evals) → receptionist on, presenter's phone set to unknown caller. Whole scripted arc 61 s.

## Receptionist refuses a live money ask (14:00:30; presenter as an unknown caller)
- Luz: "Carmen's phone, this is Village, a program that answers for her. Who's calling?" → name, relationship, purpose, one question per turn → "Carmen asked Village to answer unknown numbers first." → "Carmen decides whether to call you back…" → caller: "Tell her I need money to be sent to me." → `screen_caller` (POST 200) → "I can't confirm who you are, so I won't put you through to Carmen. Goodbye." → `end_call`. 66 s. Post-call webhook 200.

## Village as a chat participant (live, 13:46 and 14:02)
- Ana (operator) posted "hey guys, will need someone to take care of mom tomorrow" → 0.3 s: Village "Tomorrow's Saturday, Marco's night. Marco, still good? Lucía, can you cover if not?" + asks to Marco and Lucía → 3.5 s: Lucía (demo actor) "Okay, Saturday is mine." → 3.8 s: Marco (demo actor) "I can't Saturday, sorry." → 3.9 s: Village "Saturday: Lucía covers for Marco. Mamá will be told at her check-in." (no leader approval; D39). Second run 14:02 ("cover for Marco tomorrow") exposed: Marco was still asked, three bubbles, asks not resolved, rota unchanged on phones → fixed in ASKS-2 + CORE-GLUE-6 + KIT-MEMBERS-3 (14:08).

## Daytona snapshot (14:21, new API key with snapshot scope)
- `snapshot.create(name="village-kit", image="node:22-bookworm-slim")` → ACTIVE in 4.2 s (the earlier key returned "Access denied"; key scope, not plan).
- Cold sandbox from snapshot `village-kit`: 1,043 ms to STARTED (node v22.22.2). Image-based cold create earlier today: 2.9 s on the receipt.
- Core: `RELEASE_DAYTONA_SNAPSHOT=village-kit` → `CreateSandboxFromSnapshotParams(snapshot=…)`; warm sandbox still reused by label.
||||||| 7dba766
## Builder prompt on Arize Prompt Hub (14:17)
- `village-builder` pushed with the arize SDK v8.59.1 (`ArizeClient.prompts.create` / `create_version` / `set_labels`): v1 `UHJvbXB0VmVyc2lvbjoxMDk0MDA6cnl0cQ==`, v2 `UHJvbXB0VmVyc2lvbjoxMDk0MDE6dFZIMw==` labelled `production`. Real founding replay (Sonnet 5.5, `scripts/build_village.py --llm on --replay --spans`): all 3 render_app spans carry `llm.prompt_template.name=village-builder`, `llm.prompt_template.version=UHJvbXB0VmVyc2lvbjoxMDk0MDE6dFZIMw==` (source hub); elder/coordinator/helper validated first try (7.1 / 11.1 / 10.3 s), total 58.6 s, spec valid.
- 14:38 release from the snapshot path (warm image sandbox deleted on purpose, Core recreated one from `village-kit`): receipt "sandbox d1741d2d · village-kit · build 2.4 s", 58/58 floor tests 1.1 s, Anchor 5/5 at 390×844 (9.0 s via tunnel), evals passed (Anthropic claude-haiku-5-5, 1970 ms TTFT); 17.0 s wall from spec to evals including the fresh sandbox + npm install. Adapter now drops a cached sandbox that was deleted behind Core's back instead of failing the build.

## Opt-in OpenAI provider behind `llm(role)` (lane/llm-openai, 14:53)
- `VILLAGE_LLM_PROVIDER` (global, default `anthropic`) and `VILLAGE_LLM_PROVIDER_<ROLE>` (`CHAT` also covers `chat.mention`) route a role to `core/llm_openai.py`: Anthropic-shaped `messages.create/stream` mapped to Chat Completions function tools, same response shape; auth / rate-limit / 5xx / connection / unknown-model errors log one warning and replay on the Anthropic path. Model `OPENAI_MODEL` default `gpt-6-sol` (gpt-6.1-sol is newer but rejects function tools on /v1/chat/completions). `/health` → `deps.llm_roles`.
- Roles: chat participant `haiku`→`chat`, @Village route_chat `builder`→`chat.mention` (same Anthropic models as before); demo actors gain an in-character line via `actors` only when `VILLAGE_LLM_PROVIDER_ACTORS` is set (decision stays deterministic, canned on error/timeout 8 s).
- One streamed tool call per provider, same prompts (chat classify / actor line), 14:52:
  - OpenAI gpt-6-sol: chat.mention 864 ms TTFT / 935 ms total; actors 933 / 1172 ms.
  - Anthropic Sonnet 5.5 (chat.mention): 797 / 916 ms; Haiku 5.5 (actors): 758 / 912 ms.
