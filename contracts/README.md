# Village contracts (v1.1.0)

The shared interfaces every lane builds against today. If your code and a contract disagree, the contract wins until the orchestrator changes it.

```
uv run --with jsonschema --with pyyaml --with openapi-spec-validator python contracts/validate.py
```
must print `OK contract 1.1.0 …`. It checks every schema (JSON Schema 2020-12), every schema `examples` entry, every fixture, the cross-field invariants below, and `openapi.yaml` (OpenAPI 3.1, all `$ref`s resolve).

## Versioning rule
- The version lives in `contracts/VERSION`, in every schema's `x-contract-version`, in `common.schema.json#/$defs/contract_version`, and in `openapi.yaml` `info.version`. `validate.py` fails if they differ.
- **Only the orchestrator edits `contracts/`.** Any change, however small (a new enum value, a renamed field), bumps the version (patch for additive, minor for anything that can break a consumer), re-runs `validate.py`, and is announced to the main session and every lane. **Never change a contract silently**, and never fork a private copy in your lane.
- If a contract looks wrong, stop and tell the orchestrator. Don't work around it.
- WS clients send `contract_version` in `hello`; core answers `error{code: contract_mismatch}` and closes if it differs.

## Files

| File | What it is | Produced by | Consumed by |
|---|---|---|---|
| `schemas/common.schema.json` | Leaf defs: ids, datetime, `say{es,en}`, `source`, `actor`, decision vocabulary, rule ids, say keys, channels, money enums, actions, RFC 6902 ops | — | everyone |
| `schemas/village_spec.schema.json` | **VillageSpec**: `village.status` (draft \| active), blueprint (people + capability profiles + consent, edges, needs with source spans, rules, life areas), channels per member, views per role (flat adjacency, per-type props for all 27 catalog types incl. `VillageChat`), policies, voice lines, printables, custom components, `invites` (ids only) | builder (or fixture) → core stores | kit (renders), release (build pack + floor tests), gate (policies), voice (voice_lines), evals (spec_coverage) |
| `schemas/event.schema.json` | Ledger row `{id, village, kind, payload, actor, source, am?, decision_id?, at}` with a typed payload per kind (1.1.0: + `call_failed`, `village_activated`, `invite_redeemed`); `$defs/event_draft` = what the gate asks core to write | core (only writer, after the gate) | kit (Timeline, cards), memory (facts), evals (traces, detector), control room |
| `schemas/message.schema.json` | **Village chat row** (D16): `{id: msg_*, village, author: member_id \| village \| system, kind: chat \| incident \| proposal \| receipt \| nudge \| answer, text, text_i18n?, mention?, reply_to?, refs[] (event / decision / fact / trace / proposal / release / member / incident / verification / rule), routed?, source, trace_id?, at}`. Not a ledger row; Village posts cite ledger rows in `refs` | core (`post_message`; members via `POST /villages/{id}/messages`) | kit (`VillageChat`), Control Room chat mirror, builder (ask / change request) |
| `schemas/decision.schema.json` | **Decision log row** `{id: dc_*, village_id, at, actor: builder \| gate \| evolve \| voice:setup \| release, kind: plan \| decision \| note, text, rule_id?, refs[], source, trace_id?, gate?, rev?}`; gate rows carry the full gate Decision under `gate` | core (from each gate Decision), builder, evolve, release | Control Room DecisionsLog, `/ask` citations, chat answers |
| `schemas/facts.schema.json` | **Fact views** (Agent Memory read model): `fact_card`, `fact_version`, `uncertainty`, and the four endpoint responses, each with `degraded: bool` | memory lane (core `facts_for`, `fact_history`, `uncertainties`, `resolve_uncertainty`) | kit (Fact card, Uncertainty card), builder (`/ask`), evals (proposal evidence) |
| `schemas/gate.schema.json` | `GateInput{village_state, event, alloc}` → `Decision{id, rule_id, decision, say, say_key, escalate?, notify[], verification?, writes[], flags, rules_fired}`. Root = one test case | gate (`decide()`) | core (executes writes/notify/escalate), voice (say), kit (result), evals (GUARDRAIL spans) |
| `schemas/verification.schema.json` | Money verification record: fine `state` + coarse `status`, channels, answers, timers, transitions; `x-state-machine` is the transition table | gate (`step_verification`) + core (persists, CAS) | voice (await), kit (VerificationPrompt, ScamCheck, IncidentCard), evals |
| `schemas/ws_messages.schema.json` | The ONE WebSocket protocol. C→S `hello / ack / action / ping`; S→C `snapshot / patch / event / control / prompt / result / pong / error / chat`; typed binding values (`$defs/bv_*`, incl. `chat:village` → `[message]`); `control.kind` incl. `proposal`, `blueprint` | core (`ws_hub`) | kit, Control Room, release (Anchor QA), acceptance tests |
| `schemas/voice_tools.schema.json` | ElevenLabs server tools: request per tool (all carry `conversation_id, caller_id, call_secs, utterance`), response `{decision, say, say_key?, rule_id, lang, data?}` with typed `data` per tool; `$defs/verification_answer_request` for the village-caller answer; optional `answer_proposal` (1.1.0) | voice (agent configs) / core (handlers) | voice, core, evals (scam experiment) |
| `schemas/release.schema.json` | Release receipt: exactly 6 stages `spec → daytona_build → tests → anchor_qa → arize_evals → live`, result, blue/green live_rev; `candidate_path` (`/v/{id}/r/{rev}/`) and per-stage `evidence_urls[]` (1.1.0) | release | kit (ReleaseStrip), core (control stream), evals, pitch |
| `schemas/proposal.schema.json` | Evolve proposal: `detected_by`, evidence (trace / fact / call_moment), `ops` per role (patch_app rules), optional `spec_ops` on printables, status flow; approve on `proposed` or `ready`, `rejected_by/at`, `message_id` (1.1.0) | evals (detector + evidence) + builder (ops) | release (verifies), kit (Proposal card, chat), core (approve → WS patch) |
| `schemas/lid_scan.schema.json` | What `GET /s/{slot_token}` decided (JSON form of the scan page) | core | kit (scan page), release (Anchor QA), acceptance |
| `openapi.yaml` | Core HTTP API (33 paths incl. `/ws` documented as 101) referencing the schemas | core | every lane that calls core; voice (tool URLs) |
| `fixtures/reyes_spec.json` | Complete Reyes VillageSpec, rev 4 (D13): health / money / people; Carmen `elder` (es, Alert with countdown + DoseTracker + 3 BigButtons + 911), Ana `coordinator` (dashboard: LifeAreas, IncidentCard, VerificationPrompt, DoseTracker, PillOrganizer, CareRota, Timeline), Marco + Lucía `helper` ("Is it my turn?" + VerificationPrompt) | — | builder fallback, kit, release, gate |
| `fixtures/block_spec.json` | Second family: West 147th blackout block, rev 2 (coordinator / resident / volunteer; three phone-only members) | — | release (pre-generated village), kit, Control Room "same engine" beat |
| `fixtures/events_reyes_seed.json` | Ledger at the start of the Protect act (2026-10-16 ~14:00): lisinopril 5→10 (Oct 3), Oct 9 money_request + verification_pending + verification_timeout + incident, consents, Friday's shift, 08:11 morning dose, release r3 blocked / r4 released | — | core (`reset_demo`), memory, evals (Oct 9 seed session), kit |
| `fixtures/scam_call_tool_requests.json` | Exact voice tool exchanges for the headline flow: variants `denied`, `timeout`, `confirmed`, `unknown_claimed`, `duplicate_webhook`, each with the verification record afterwards | — | voice (mock core), core (handler tests), gate, evals |
| `fixtures/ws_sequence_scam.json` | WS frames each client (carmen / ana / marco / control) sees during the scam flow: `connect`, `start`, then one of `denied` / `timeout_tail` / `confirmed_tail` | — | kit (fake WS), core (hub tests), release (Anchor script) |
| `fixtures/lid_scan_sequence.json` | Lid sticker flow (policy T28): first scan, deduped prefetch, second scan → report + escalation, bad token; HTTP result + WS frames | — | core, kit, release, acceptance |
| `fixtures/messages_reyes_seed.json` | Village chat (D16) mirroring `design/Chat.dc.html`: nudge → Marco → Village "scam stopped" (refs the money row, Marco's answer, the incident) → Lucía → Village proposal (Approve · Not now) → Ana "@Village why…" → answer with rule + consent chips → release receipt | — | kit (`VillageChat` + chat frames), core (`reset_demo`, `post_message`), Control Room chat mirror |
| `validate.py` | The check above | orchestrator | everyone before merging |

## Conventions
- **Ids:** `v_*` village, `m_*`/`b_*` member, `ev_*` event, `ver_*` verification, `inc_*` incident (`inc_` + verification id for money incidents; upserted), `prop_*` proposal, `rel_*` release, `dc_*` decision, `st_*` slot token ref (never the token), `pr_*` printable. Core mints ids before calling the gate (`GateInput.alloc`), so `decide()` stays pure.
- **Times:** RFC 3339 with offset (`-04:00`), from the shared `Clock` (time-warp applies everywhere). Verification `deadline = created_at + 45 s`; `await_verification` holds ≤ 30 s (ElevenLabs tool timeout 35 s).
- **Spoken lines are gate-owned.** `Decision.say{es,en}` + `say_key` (templates in `data/datasets/policy_cases.md`). Voice responses carry the one string in the caller's `lang`; the agent speaks it verbatim. Kit shows gate text, never its own wording for outcomes.
- **Answers** to a verification are `yes | no | unsure` everywhere (prompt options, WS action, HTTP body, verification.answers).
- **Provenance:** every event has `source{kind: call|app|scan|url|system, ref, secs (required for call), url (required for url), quote?}`. Scans use `ref = token_ref`.
- **Roles (view keys):** Reyes = `elder`, `coordinator`, `helper` (D13 three apps; channels `app:<role>`). Block = `coordinator`, `resident`, `volunteer`. `snapshot.role = "control"` for the Control Room (gets the whole spec).
- **Family word** `[PALABRA]` lives only in `printables[fridge_card].family_word` (coordinator/control snapshots and the print pack); never in views, traces or the Mom line.

### Names that differ from older docs (contract name wins)
| Older doc says | Contract |
|---|---|
| `hold_and_escalate` (policy_cases P-DD-01), `block_double_dose` (SPEC F3) | `decision: report_already_logged` + `escalate{…}` + `say_key: dd_report` |
| `attempted_duplicate`, `dose_blocked` | event kind `dose_repeat_scan` (lid) / `dose_repeat` (call, app); Timeline accepts `dose_blocked` as an alias |
| `verification_requested` | `verification_pending` |
| `verification_unsure`, `verification_unreachable` | `verification_timeout` with `payload.reason: unsure | unreachable` (fine state kept in `state`) |
| `verification_answer_dup` | not an event: `answers[].outcome = dup` on the record |
| verification states `PENDING, DEFAULT_SPOKEN, …` | lowercase `state` (`pending, default_spoken, confirmed, late_confirmed, denied, late_denied, unsure, unreachable, timed_out`); coarse `status` = `pending | confirmed | denied | timeout` |
| `answered_via: app | call` (mom_line.md) | `app_prompt | outbound_call` |
| tool URLs `/voice/mom/<tool>`; response `{status, …, policy:{decision, rule, say}}` (mom_line.md) | `POST /tools/<tool>`; response `{decision, say, say_key, rule_id, lang, data}`. ElevenLabs assignments: `gate_decision←decision`, `say_text←say`, `verification_id←data.verification_id`, `verification_status←data.status` |
| `consent_calls` (SPEC) | `consent.ai_calls` (null = not asked = false) |
| builder role `family` | `coordinator` (Ana) + `helper` (Marco, Lucía); builder lane maps |
| builder `blueprint.profiles` (`memory: full|lapses|impaired`, `tech_comfort: none…high`) | `blueprint.people[].profile` (`memory: typical|mild_lapses|significant`, `tech_comfort: phone|app|both`); builder lane maps |
| SPEC `members[]` + D10 `blueprint.people[]` | one list: `blueprint.people[]` (role, view, profile, consent) |
| SSE `/control/stream` | WS `control{kind}` messages |

## Invariants (enforced by `validate.py` and core's pydantic model; JSON Schema can't say them)
1. `channels` keys == `blueprint.people[].id`; a person's `app:<role>` channel equals their `view`; every non-null `view` exists in `views`.
2. Each view: root `s` is a Screen; every child id exists; every element except `s` is referenced exactly once; no cycles.
3. Every non-layout element (not Screen/Stack/Header/Text) has `needs_served`; every cited need is in `blueprint.needs` or is `n_safety`.
4. Elder views: ≤ 3 BigButtons (ScamCheck doesn't count), a 911 ContactCard, `confirm` on danger buttons, no med names. ("Labels ≤ 3 words" stays a builder-prompt guideline, not a contract rule: the design copy "Ya me la tomé" is 4 words.)
5. `subject`, `member_id`, `choices_member_ids`, `subjects` props reference real members; `source_span` lies inside `blueprint.description.text`; every need is in some life area; life-area modules `<role>:<element>` exist.
6. Patches apply only when `patch.base_rev` == the client's rev; proposals apply in op order (builder patch rules).
7. A verification's `status` follows its `state` (`x-state-machine.status_of_state`); confirmed/denied states carry an applied answer.
8. `VillageChat` never appears in a `theme: elder` view and at most once per view (1.1.0). The chat fixture is ordered by `at`, `reply_to` points at an earlier row, and every `village` post carries `refs`.

## Binding values (`snapshot.data`, `event.data`)
Keys are the exact `bind` strings used in the role's view; shapes are enforced by `ws_messages.schema.json#/$defs/data` (`patternProperties`):

| Bind | Value |
|---|---|
| `alerts:active` | `[bv_alert]` (severity, title/body localized, optional `verification{id, deadline, status}` → countdown, optional `escalation{to, channel, status}` → "Village is calling you") |
| `verifications:pending?member=me` | `bv_pending_prompt` or null (VerificationPrompt) |
| `verifications:mine` | `bv_my_verification` or null (ScamCheck states) |
| `incidents:open`, `incidents:subject=<id>` | `[bv_incident]` (no account/card numbers ever) |
| `facts:dose_event?…valid_at=today|week` | `bv_dose_day` / `bv_dose_week` (`meds` only for views with `show_med_names`) |
| `rota:current?member=me` | `bv_rota_me` (`is_my_turn`, `answer` text) |
| `rota:week`, `rota:current` | `[bv_rota_day]` |
| `rota:current.on_duty|backup` | `bv_person` |
| `timeline:subject=<id>` | `[bv_timeline_item]` with `source` + `superseded` |
| `blueprint:life_areas` | `[bv_life_area]` with live chip `status` |
| `proposals:pending` | `[bv_proposal]` |
| `chat:village` | `[message]` (last 50, oldest first; never sent to elder views; appended to by WS `chat` frames) |
| `…?count` | number |

## How lanes mock each other (until the real thing merges)
- **core** (orchestrator): commits a stub `core/services.py` at 10:00 that returns fixture-shaped data: `decide()` returns the `decision` of the matching `gate.schema.json` example; tools answer from `scam_call_tool_requests.json`; `/ws` replays `ws_sequence_scam.json` filtered by `client`.
- **gate**: pure; needs no mocks. Test inputs = `gate.schema.json` examples, `policy_cases.md` T01–T51, and the `verification_after` records; transitions from `verification.schema.json#x-state-machine`. Return objects that validate as `$defs/decision`.
- **kit**: a fake WS server that sends `snapshot` (view from `reyes_spec.json` for the role, `data` from the fixtures) then replays `ws_sequence_scam.json` / `lid_scan_sequence.json` frames for that client. Scan page renders `lid_scan_sequence.json` `result.page`. Unknown types render nothing.
- **voice**: point agent tools at a mock server that matches `(tool, conversation_id, tool_call_id)` in `scam_call_tool_requests.json` and returns `response` (for `await_verification`, wait until `returned_at - at`). Validate every real request body against `$defs/req_<tool>` before shipping.
- **builder**: validate the merged output against `village_spec.schema.json` and run `validate.py` invariants; diff against `reyes_spec.json`. On failure, fall back to `reyes_spec.json` (or `block_spec.json`).
- **release**: build from `reyes_spec.json`; emit receipts that validate against `release.schema.json` (examples = the caught-and-fixed r3/r4 pair) as WS `control{kind: release}`. Anchor drives `/s/<token>` twice (expect `lid_scan_sequence.json` results) and the VerificationPrompt.
- **evals**: build the Oct 9 + Oct 16 sessions from `events_reyes_seed.json` + `scam_call_tool_requests.json`; emit a `proposal.schema.json` object (example = the ScamCheck proposal). Scam experiment inputs map to `req_report_money_request`.
- **memory**: consume ledger rows (`event.schema.json`); one fact per row with labels `src=<source.kind>:<source.ref>`, `secs=<source.secs>`, `village=…`, `agent=…`; supersession from `med_change`. Never on the safety path.

## CHANGELOG

### 1.3.4 (Oct 16, 14:08; orchestrator; additive patch)
- `message.schema.json`: ref kind `ask` with `member`, `label`, `answered`, `answered_at` (D39: Village's asks to members, resolved in place).

### 1.3.3 (Oct 16, 13:48; orchestrator; additive patch)
- `ws_messages`: actions `answer_ask`, `claim_plan_item`, `ask_proposal_other`; `prompt` frames may carry `kind: ask` with `ask{ask_id, question, options, deadline}` (D39). `proposal.detected_by` += `chat_request` (D36/D39).

### 1.3.2 (Oct 16, 13:40; orchestrator; additive patch)
- `voice_tools` `req_relay_message` (receptionist takes a message → family chat + screened-call log).

### 1.3.1 (Oct 16, 13:25; orchestrator; additive patch)
- `ws_messages` `bv_life_area.need_ids[]` so the kit derives a person's tabs from the life areas their cards serve (UX-UPGRADE).

### 1.3.0 (Oct 16, 13:15; orchestrator; additive, minor)
- Six catalog types (UX-UPGRADE): `RightNow`, `WhatVillageDid` (bind `rounds:latest`), `SinceYourTurn` (`events:since_last_turn?member=me`), `PlanBoard` (`plan:<id>`), `ScreenedCalls` (`calls:screened`), `FactCard` (`facts:history?subject=&key=`); bind grammar + `ws_messages` data shapes `bv_rounds`, `bv_since_turn`, `bv_plan`, `bv_screened_calls`, `bv_fact_history`.

### 1.2.2 (Oct 16, 13:00; orchestrator; additive)
- `ws_messages`: `control{kind: blueprint}.stage` += `questions` (gap list) and `will_build` (items `{person, display_name, component, reason}`: what each answer builds, D33).
- `voice_tools`: `req_submit_answer` (Setup agent intake answers), `req_screen_caller` (D19 receptionist), optional `lang` on every request.

### 1.2.1 (Oct 16, 11:58; orchestrator; additive)
- `decision.schema.json`: optional `mode: acted_alone | asked_human | refused` (D23 autonomy ledger; core previously carried it in `refs`).
- `ws_messages.schema.json`: `control.kind` += `caption` (`{es, en, speaker?, final?}`: live call turn for the projector, D18) and `ledger` (`{id, at, status: queued|running|done|retrying|fallback|refused, what, result?, role?, mode?, decision_id?, trace_id?, elapsed_ms?}`: agent work rows, D20/D23); `reasoning.payload.source` += `watcher | founder | verifier | explainer`; `reasoning.payload.mode` optional.

### 1.1.0 (Oct 16, applies RECONCILE.md "To apply" + the lane READMEs in specs/001, 002, 003, 005, 006; D16)
Minor bump: additive paths, kinds and fields; no existing field renamed. Every schema `x-contract-version`, `common#/$defs/contract_version`, every fixture and example `contract_version`, and `openapi.info.version` moved to `1.1.0` in one step (a `hello` with `1.0.0` now gets `error{contract_mismatch}`).
- **New schemas:** `message.schema.json` (D16 chat row), `decision.schema.json` (decision log row), `facts.schema.json` (fact / uncertainty views, every response with `degraded`).
- **common:** `invite_id`, `invite_token`, `message_id`, `uncertainty_id`, `village_status`, `message_kind`, `message_ref`; say key `money_core_down`.
- **event:** kinds `call_failed`, `village_activated`, `invite_redeemed` with typed payloads; `verification_pending.channels` may be `[]` (unreachable).
- **gate:** `Decision.escalate.related_event_id` optional (core fills it); optional `village_state.village_status`.
- **village_spec:** `village.status: draft | active` (absent = active), `village.activated_at`, top-level `invites[]` + `$defs/invite`; catalog type `VillageChat` (`props_VillageChat {bind: "chat:village", composer, title?, mention_label?, allow_approve?, limit?}`); bind grammar `chat:village`; invariant 8.
- **ws_messages:** server frame `chat{village, message}`; binding `chat:village → [message]` (`bv_message`); `control.kind` += `proposal{proposal}`, `blueprint{village, stage, items}`.
- **release:** `candidate_path` (`/v/{id}/r/{rev}/`), `evidence_base_url`, per-stage `evidence_urls[] {kind, url, label?, viewport?}`.
- **proposal:** approve allowed on `proposed` and `ready`; `rejected_by`, `rejected_at` (required when rejected), `message_id`.
- **voice_tools:** optional tool `answer_proposal` (`req_answer_proposal {proposal_id, answer: yes|no}`, `data_answer_proposal`).
- **openapi (18 → 33 paths):** `GET /voice/token`; `PATCH /villages/{id}/draft`; `POST /villages/{id}/activate` (409 while active; `/qr` answers 409 while draft); `POST /villages/{id}/answers`; `POST /villages/{id}/ask`; `GET /villages/{id}/decisions`; `GET|POST /villages/{id}/messages`; `POST /villages/{id}/proposals/{pid}/reject` (+ approve on `proposed`); `GET|POST /villages/{id}/releases`; `GET /villages/{id}/facts`, `GET /villages/{id}/facts/{entity}/{key}/history`, `GET /villages/{id}/uncertainties`, `POST /villages/{id}/uncertainties/{uid}/resolve`; `GET /v/{id}/r/{rev}/{path}`; `GET /releases/{rel}/qa/{file}`; `/tools/{name}` accepts `req_answer_proposal`.
- **fixtures:** `messages_reyes_seed.json` (8 rows mirroring `design/Chat.dc.html`); `validate.py` checks it, the VillageChat invariant, and counts fixtures dynamically.
- Not applied (not requested): `spec_patch_rejected` event kind (the `decision` row + `proposal.rejected_*` are the record); `reyes_spec.json` stays rev 4 without a `VillageChat` (add it via a proposal or a rev 5 fixture when the kit lands the component).

### 1.0.0
Initial contracts (schemas, fixtures, 18 paths).

## Decisions made in v1 that DECISIONS.md does not state
1. Demo dates: the scam flow is **Fri 2026-10-16 14:02** (from `reyes_family.json` call_3), when the rota has **Ana** on duty; the lid-scan fixture follows policy T28 on **Thu 2026-10-15** (Marco on duty, "Le avisamos a Marco"). Pin the demo clock to Thursday or accept "Le avisamos a Ana" on Friday.
2. Oct 9 is seeded as a Village-caught timeout (app prompt only), per the orchestrator brief; `reyes_family.json` tells it as discovered by Ana the next day.
3. `await_verification` with no answer returns at 30 s with `status: timeout` (state `default_spoken`); the row stays answerable until 45 s, then `timed_out`. A late answer updates the incident, not what Carmen heard.
4. Lid scan: `GET /s/{token}` records immediately; the same token within 10 s is deduped (`deduped: true`, no row) so link prefetch can't fake a second dose. Second scan → `report_already_logged` + escalate on-duty via `both` (call + banner).
5. Decision vocabulary adds `remind`, `verify_with_source`, `advise_talk_to_coordinator` to the 11 listed; confirmed money → `advise_talk_to_coordinator`.
6. Gate is pure: core pre-mints ids (`alloc`) and passes `now`; the gate returns `writes[]` (ledger drafts) instead of writing.
7. People are one list (`blueprint.people` with role/view/profile/consent); `consent.ai_calls` is nullable (Carmen's was never asked).
8. Proposal ops are a map `role → ops`; Evolve adds ScamCheck to `elder` and an IncidentCard to `helper` (Ana already has one); the fridge card change is a `spec_ops` op on `/printables/2/family_word_first`.
9. Added a `pattern` event (R-MONEY-PATTERN) and `verification_answer_conflict`; dropped a separate `scam_check` event (ScamCheck → action `start_verification` → `verification_pending{origin: start_verification}`).
10. Added `result`, `pong`, `error` server messages and `ping` client message to the WS protocol; `event` messages carry optional `data` (changed bindings) so clients never compute bindings themselves.
11. Typed `data` values for binds; `HelperAnswer`, `Proposal`, `PillOrganizer` props are defined here (not yet in the builder catalog); `Alert.show_countdown` added for Carmen's countdown.
12. Block-line tool request bodies are loosely typed in v1 (backup village only).
