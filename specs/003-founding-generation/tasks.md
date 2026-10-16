# Tasks: FS-3 Founding & generation

Lanes: **builder** (core/builder/, scripts/build_village.py, data/builder/), **core** (routes, services seam, invites, acceptance), **kit-touchpoints** (what FS-4 must expose; listed so the kit lane can schedule them). `[P]` = parallelisable with the previous task. Minutes are estimates for one agent. Acceptance = the check the task satisfies (`acceptance/v2.sh` steps are named `A2-n`). Principle = constitution principle served.

## Phase 0 — scaffolding (11:00–11:20)
| ID | Lane | Ver | Task | Min | Deps | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T001 | builder | V2 | Create `core/builder/` package with the module layout in plan.md; `tools.py` parses `render_app`/`patch_app` JSON fences from `prompts/builder_system.md` and defines `extract_blueprint` + `cite_answer`; test pins tool names and `additionalProperties:false` | 15 | — | unit | IX |
| T002 [P] | builder | V2 | `validate.py`: pydantic mirror of `village_spec.schema.json` (discriminated union on `type`, per-type props) + invariants 1–5 + safety text scan; tests on `reyes_spec.json`, `block_spec.json` (pass) and 6 mutated specs (fail with named invariant) | 35 | — | A2-4 | V |
| T003 [P] | builder | V2 | `prompts.py`: Prompt Hub fetch (`village-builder`, `production`, 10 s TTL, lazy `arize` import) + local fallback; returns `{text, version_id, source}`; `--probe` CLI; test with the SDK mocked down and up | 20 | — | unit | VIII |
| T004 [P] | core | V2 | `core/services.py` stub additions: `store_spec`, `get_spec`, `set_status`, `broadcast_control`, `record_decision`, `decisions_for`, `facts_for` (seed-derived), `events_for`, `mint_invites`, `redeem_invite`; `core/services_stub.MemoryServices` for scripts/tests | 20 | — | unit | VI |

## Phase 1 — blueprint + renders (11:20–12:15)
| ID | Lane | Ver | Task | Min | Deps | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T005 | builder | V2 | `blueprint.py`: streamed `extract_blueprint` call via `core.llm.llm("sonnet")`, `allow_partial` parser, one `control{reasoning}` frame per finding + `counter people_found`; profiles typed per contract with `evidence[]`; ≤2 questions; test with a recorded delta stream (`core/builder/tests/data/reyes_blueprint_deltas.jsonl`) asserting frame order and no invented people on `gd_20` | 40 | T001, T004 | A2-2 | III, VIII |
| T006 [P] | builder | V2 | `mapping.py`: role mapping (care: elder/coordinator/helper; block: coordinator/resident/volunteer), builder→contract profile enums, channel derivation, printables derivation; tests against both fixtures | 20 | T001 | unit | V |
| T007 | builder | V2 | `render.py`: parallel `render_app` per role (`asyncio.gather`, 45 s per role, 60 s total), `cache_control` on the system block, `using_prompt_template`, merge (views, needs by id, primary village-level fields), per-role status; fake-LLM tests: all valid, one invalid→repaired, one failing→template, timeout→template | 45 | T002, T003, T005, T006 | A2-3, A2-4 | V, VII |
| T008 [P] | builder | V2 | `templates.py`: fixture view per `(kind, role)` with member id/name remap; `mode: fixture` loads the whole fixture; decision row "template <role>: <reason>" | 20 | T002 | A2-5 | VII |
| T009 | builder | V2 | `founding.py` + `__init__.found()`: session state machine, clarify pause (text) with 30 s proceed, decision rows per channel/role/contact/consent choice (`decisions.py`), `BuilderRun` record, spans (`spans.py`: AGENT `builder.found`, CHAIN `builder.blueprint`, EVALUATOR `builder.validate`, graph.node attrs, session/user ids) | 40 | T005, T007, T008 | A2-2..5 | I, III, VIII |
| T010 [P] | builder | V2 | `scripts/build_village.py` (quickstart) with `--time`, `--warm`, `--strict`, `--llm off`, `--ask`; record first real timings into `RESULTS.md` (`[MEASURE]` → numbers) | 25 | T009 | quickstart | VIII |

## Phase 2 — routes, lifecycle, ask (12:15–13:00)
| ID | Lane | Ver | Task | Min | Deps | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T011 | core | V2 | `core/routes/villages.py`: `POST /villages` (202 + background `found`), `GET /villages/{id}` (ETag), `POST …/answers`, `POST …/draft` (allowed-path RFC 6902 + revalidate), `GET …/qr` 409 on draft; auth per openapi | 35 | T004, T009 | A2-1, A2-6 | II, VI |
| T012 [P] | core | V2 | Voice route: `POST /tools/create_village` handler in `core/voice/` calling the same `found()` in a background task; fixed `say` line; ≤2 s test with a slow fake builder; idempotent on `(conversation_id, tool_call_id)` | 20 | T009 | A2-1 | I, II |
| T013 | core | V2 | `POST /villages/{id}/activate`: status flip, `mint_invites` (hashed tokens, 24 h), printables `token_ref`, `village_activated` decision row + event, join list with SVG (`segno`); 409 on repeat; `POST /auth/redeem` consumes invite → consent event + `people[].consent` update | 35 | T011 | A2-6, A2-7 | II, III |
| T014 [P] | builder | V2 | `ask.py` + `POST /villages/{id}/ask`: gather material (decisions, facts, events; cap 60 rows), Sonnet 5.5 effort low, `cite_answer` tool, citation validation + redaction (family word, phones, account patterns), AGENT span; tests: seeded Reyes log answers the Marco/Lucía question with 2 citations; hallucinated id dropped; family-word question refused | 35 | T004, T009 | A2-8 | III, VIII |
| T015 [P] | builder | V2 | `patch.py`: `builder.patch(village, role, instruction, current_view)` → `PatchResult`; apply-to-copy + validate + one repair; tests with Examples 4–6 from the prompt | 20 | T002, T003 | unit (V4 consumer) | V |
| T021 | builder | V2 | Chat insertion: `mapping.ensure_chat()` adds one `VillageChat` (`bind: chat:village`, `allow_approve` for coordinator) to every non-elder view after merge and in templates; `validate.py` forbids it in elder views and >1 per view; tests on both fixtures | 15 | T006, T007 | A2-9 | V, IX |
| T022 | core | V2 | `core/chat.py`: `message` store (`msg_*`, refs, source), `POST/GET /villages/{id}/messages` (403 for elder members), WS `chat` fan-out to non-elder sockets, `chat:village` binding (last 50) in snapshots; ledger subscriber posts Village messages for `incident` (gate text), `spec_patch_proposed`, `release`, rota `reminder|escalation` nudges, each with ≥1 ref (asserted) | 35 | T004, T011 | A2-9, A2-10 | III, I |
| T023 | builder | V2 | "@Village" routing: `mention: village` → `builder.ask(channel="chat")` → `kind: answer` reply with citation refs; span metadata `channel=chat`; test S12 (answer ≥1 ref, redaction passed) | 15 | T014, T022 | A2-11 | III, VIII |
| T024 | builder | V4 | `chat_intent.py`: classify `@Village` text `why|change|other` (Haiku, effort low, tool `classify_intent`); `change` → `builder.patch()` per affected role → Proposal row (FS-6 pipeline) → `kind: proposal` message with inline Approve for the leader; unsure → answer + "Want me to propose a change?"; tests with 6 utterances incl. "Marco switched to days" | 30 | T015, T023 | V4 acceptance | I, II |
| T016 | builder | V2 | Record `data/builder/reyes_reasoning.jsonl` from a real run for the `mode: fixture` replay; wire replay in `founding.py` | 10 | T010 | A2-5 | VII |
| T017 | core | V2 | `acceptance/v2.sh` (see below) + `uv run pytest core/builder -q` green; report mocks and timings to the orchestrator | 20 | T011–T016 | A2-* | VII |

## Phase 3 — second village + hardening (13:00–13:40, V3)
| ID | Lane | Ver | Task | Min | Deps | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T018 | builder | V3 | Generate the block village from `block_blackout.json` (`--kind block`), validate, diff against `block_spec.json`, store `data/builder/block_spec.generated.json` + `build_time_ms` + `trace_id`; load it as `v_w147` at startup (`reset_demo` hook) | 25 | T010 | A3 reveal | VIII |
| T019 [P] | builder | V3 | Warm-up (`--warm`) at 12:30 and 13:30; re-measure TTFT/total; set `effort` per step; `BUILDER_PARALLEL=0` fallback tested | 15 | T010 | RESULTS.md | VIII |
| T020 [P] | builder | V3 | Builder spans verified in Arize: AGENT → CHAIN → 3 LLM → EVALUATOR under `session.id=village-v_reyes`, `llm.prompt_template.version` set | 15 | T009 | VIII check | VIII |

## Kit touchpoints (owned by FS-4; scheduled there, listed for dependency)
| ID | Lane | Ver | Task | Min | Deps |
|---|---|---|---|---|---|
| K01 | kit-touchpoints | V2 | Founding box: textarea → `POST /villages`; shows follow-up question from reasoning `note` frames → `POST …/answers` | 20 | T011 |
| K02 | kit-touchpoints | V2 | Control Room blueprint panel from reasoning frames + control snapshot (`spec.blueprint`): people chips with profile evidence on tap, needs with quoted spans, life areas, rules, group type | 40 | T005 |
| K03 | kit-touchpoints | V2 | Draft review page: people/channels/rules/views; edits → `POST …/draft`; "Invite everyone" → `/activate` → invite sheet with per-member QR (`svg`) | 35 | T013 |
| K04 | kit-touchpoints | V2 | Ask box: `POST …/ask` → answer + citation chips (tap → decision/fact detail) | 20 | T014 |
| K05 | kit-touchpoints | V2 | Join page `/join?i=` → `POST /auth/redeem` (already in FS-2/FS-4 scope; consent text version `join_v1`) | — | T013 |
| K06 | kit-touchpoints | V2 | `VillageChat` catalog component: feed rows by `kind` (chat/incident with source chip/proposal with Approve-Not now for leaders/receipt/nudge/answer with citation chips), composer with "@Village" affordance → `POST …/messages`, applies WS `chat` frames; absent from elder theme | 45 | T022 |
| K07 | kit-touchpoints | V4 | Proposal message updates to "approved by Ana" on `spec_patch_applied`; change-request reply flow | 15 | T024 |

## `acceptance/v2.sh` (builder/core part; run by `acceptance/run.sh V2 --lane builder|core`)
```bash
#!/usr/bin/env bash
set -euo pipefail
H=${CORE_URL:-http://localhost:8787}; T=${CONTROL_TOKEN:?}
j() { curl -sS -H "Authorization: Bearer $T" -H 'Content-Type: application/json' "$@"; }
DESC=$(jq -r .demo_spoken_description data/villages/reyes_family.json)
# A2-1 found by text → 202
VID=$(j -X POST $H/villages -d "{\"description\": $(jq -Rn --arg d "$DESC" '$d'), \"language\": \"en\"}" | jq -r .village_id); [ -n "$VID" ]
# A2-2 reasoning frames arrive (≤8 s to ≥5 frames) via the control socket
uv run scripts/ws_tail.py --village "$VID" --token "$T" --kind reasoning --min 5 --timeout 8
# A2-3 draft with 3 views within 60 s, status draft
for i in $(seq 1 60); do S=$(j $H/villages/$VID); [ "$(echo "$S" | jq '.views|length')" = 3 ] && break; sleep 1; done
echo "$S" | jq -e '.views.elder and .views.coordinator and .views.helper' >/dev/null
# A2-4 validates against the contract oracle
echo "$S" > /tmp/v2_spec.json && uv run --with jsonschema python scripts/validate_spec.py /tmp/v2_spec.json
# A2-5 template fallback with the model off
VILLAGE_LLM=off j -X POST $H/villages -d '{"description":"Mom forgets her pills","mode":"full"}' | jq -e .village_id >/dev/null
# A2-6 nothing before activation; activate once
[ "$(j -o /dev/null -w '%{http_code}' "$H/villages/$VID/qr?kind=join&format=json")" = 409 ]
INV=$(j -X POST $H/villages/$VID/activate); echo "$INV" | jq -e '.invites|length>=2' >/dev/null
[ "$(j -o /dev/null -w '%{http_code}' -X POST $H/villages/$VID/activate)" = 409 ]
# A2-7 join with consent → consent event + token
I=$(echo "$INV" | jq -r '.invites[]|select(.member_id=="m_marco").url' | sed 's/.*i=//')
curl -sS -X POST $H/auth/redeem -H 'Content-Type: application/json' -d "{\"invite\":\"$I\",\"first_name\":\"Judge\",\"consent\":{\"ai_calls\":true,\"text_version\":\"join_v1\"}}" | jq -e '.member_token and .consent_event.kind=="consent"' >/dev/null
# A2-8 ask why with citations
j -X POST $H/villages/$VID/ask -d '{"question":"Why does Carmen get a phone line and not an app?","lang":"en"}' | jq -e '.answer and (.citations|length>=1)' >/dev/null
# A2-9 chat present in coordinator + helper, absent in elder
echo "$S" | jq -e '[.views.coordinator,.views.helper|.elements[]|select(.type=="VillageChat")]|length==2' >/dev/null
echo "$S" | jq -e '[.views.elder.elements[]|select(.type=="VillageChat")]|length==0' >/dev/null
# A2-10 Village posts an incident into the chat (seeded incident → chat frame on Ana's socket)
uv run scripts/ws_tail.py --village "$VID" --token "$T" --as m_ana --type chat --kind incident --min 1 --timeout 5
# A2-11 @Village why → answer with refs
MT=$(curl -sS -X POST $H/auth/redeem -H 'Content-Type: application/json' -d "{\"invite\":\"$(echo "$INV" | jq -r '.invites[]|select(.member_id=="m_ana").url' | sed 's/.*i=//')\",\"first_name\":\"Ana\",\"consent\":{\"ai_calls\":true,\"text_version\":\"join_v1\"}}" | jq -r .member_token)
curl -sS -X POST $H/villages/$VID/messages -H "Authorization: Bearer $MT" -H 'Content-Type: application/json' -d '{"text":"@Village why does Carmen get a phone line?","mention":"village"}' | jq -e '.routed=="ask"' >/dev/null
uv run scripts/ws_tail.py --village "$VID" --token "$MT" --type chat --kind answer --min 1 --timeout 10
echo "V2 builder/core acceptance: PASS"
```

## Definition of done (lane report to the orchestrator)
`acceptance/v2.sh` passes locally against the stub services; `uv run pytest core/builder -q` green; measured TTFT/total per role in `RESULTS.md`; mocked: `core.obs` tracer (until evals merges), `facts_for` (until memory merges), SurrealDB (MemoryServices); contract additions requested in `contracts/README.md` of this spec.

## Addendum (D20): capabilities + critique
- T025 [builder, V2, 30 min] `core/agent/capabilities.yaml` with 6–8 capabilities (lid_qr_logging, phone_line, receptionist_line, is_it_my_turn, dashboard, village_chat, fridge_card, rumor_check) each with applies_when, fits, cost_to_person, risk_class, implements; Founder tool `capabilities.list`; the draft records per-person capability choices with reasons into `decision` rows. Acceptance: Reyes draft shows lid_qr_logging + phone_line for Carmen with the reason text; Wei/blackout drafts choose differently. Principle VIII.
- T026 [builder, V2, 20 min] Critique pass: one extra call with the critique prompt before render; diffs applied; Control Room shows "second opinion: 2 changes". Acceptance: critique output logged as EVALUATOR span. 

## Addendum (D23): the Founder does work
- T027 [builder/voice, V2, 30 min] During founding, after people/meds are extracted: (a) DailyMed REST lookup of each medication (interaction/warning sections) → facts with url provenance, surfaced in the draft as "checked"; (b) if a caregiver has a phone, place the availability + consent call (village-caller agent, T3 script variant) and show "Marco confirmed Tue/Thu/Fri/Sat; agreed to calls" on the draft. Both are decisions with `mode: acted_alone`. Fallback: mark as "will check after you invite".

## Addendum (D24): Carmen's rules
- T028 [builder/voice, V2, copy+data, 10 min] `quiet_hours` on the Reyes spec comes from Carmen's welcome-call answer with provenance (`source.kind=call, ref=welcome_call, secs=108`, her words "Después de las nueve y media, no."). The gate's P-QH-01 reads it from the spec. Decision records refused under it carry `rule: P-QH-01, source: welcome_call`. Surfaces: WelcomeCall row "Quiet hours · after 9:30 PM, no calls (her words)"; Rounds/RoundsCard "Blocked by code: Carmen's rule, no calls after 9:30 PM". Acceptance: existing quiet-hours gate test reads the fixture value; the refused record names the source.
