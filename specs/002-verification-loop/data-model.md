# Data model: FS-2 Verification loop

All shapes are owned by `contracts/schemas/*`; this file says which fields FS-2 reads/writes and when. Ids are contract ids (`v_reyes`, `m_marco`); Core maps them to `RecordID` on every SurrealDB write.

## verification (`verification.schema.json`, table `verification`, CAS on `version`)
| Field | Written by | When |
|---|---|---|
| `id` (`ver_*`), `village`, `subject`, `claimed_member_id`, `claimed_identity`, `origin: report_money_request`, `conversation_id`, `money_request_event_id`, `request{amount,currency,method,urgency,red_flags}` | `services.start_verification` | creation (gate `alloc` pre-mints id) |
| `state` / `status` | gate `step_verification` via `services.answer_verification`, `await_verification`, `tick_verifications` | `pending → confirmed|denied|unsure` (answer), `→ default_spoken` (await at 30 s), `→ late_*` (answer after default), `→ timed_out` (tick ≥ 45 s), `unreachable` (no channel) |
| `channels[] {via, member_id, status, ref, at}` | voice (`outbound.py`, WS hub) | `app_prompt`: `sent → delivered → answered|cancelled`; `outbound_call`: `ringing → in_progress → answered|no_answer|voicemail|failed|cancelled|skipped_no_consent`; `ref` = WS prompt id / ElevenLabs `conversation_id` |
| `answers[] {answer, via, member_id, at, secs_since_created, outcome, quote}` | `services.answer_verification` | every answer; `outcome ∈ applied|dup|conflict|ignored` |
| `created_at`, `deadline = created_at + 45 s` | creation | shared `Clock` |
| `call_placed_at` | `outbound.py` by CAS (`WHERE call_placed_at = NONE AND version = $v`) | once, never redialed |
| `await_returned_at`, `spoken_say_key` | `services.await_verification` | what Carmen heard (`money_confirmed|money_denied|money_timeout`) |
| `resolved_at`, `incident_id (inc_<id>)`, `pattern_flag` | gate actions | terminal state / R-MONEY-PATTERN |
| `transitions[] {from, to, at, cause}` | every step | audit |

Invariants: `status = status_of_state[state]`; confirmed/denied carry an `applied` answer; `default_spoken|late_*` require `await_returned_at` and `spoken_say_key = money_timeout`.

## consent (ledger `consent` event + member row)
`member.consent.ai_calls: bool|null` (null = never asked = false), `app_prompts`, `money_safety_sharing`; written by `POST /auth/redeem` (Join) as event `consent{member_id, scopes, text_version}`. Read at **dial time** by `POST /calls/outbound` (R-VERIFY-CONSENT); a revoke between creation and dial → channel `skipped_no_consent`. Carmen's `money_safety_share_with` governs the incident notice (never suppressed by "don't tell Ana").

## call records (new, Core-local; not a contract table)
`voice_call {conversation_id (pk), village, member_id, agent: mom-line|village-caller|setup, direction: inbound|outbound|web, caller_id, call_sid, started_at, ended_at, verification_id?, init_vars (the seven returned), post_call: {received_at, signature_ok, termination_reason, duration_secs, data_collection{verification_answer?}}, transcript_ref}`. Created by the init webhook (inbound), by `outbound.py` (outbound), or by the first tool call (web); completed by the post-call webhook. `call_initiation_failure` sets `ended_at` + `post_call.termination_reason` and the verification channel `failed`.

## idempotency (Core-local)
`tool_cache {key: (conversation_id, tool_call_id) | (conversation_id, tool, call_secs), response_json, at}`; TTL = call lifetime + 10 min. `answer_cache` keyed `(verification_id, call_sid)` for post-call `data_collection` backups. One open verification per `(conversation_id, claimed_member)`.

## transcript provenance (events + post-call reconcile)
Every event FS-2 writes carries `source{kind: call, ref: <conversation_id>, secs: <call_secs>, quote: <utterance>}`; app answers carry `source{kind: app, ref: <member_token_id>}`. At post-call, for each transcript turn with `tool_calls`, Core matches by `conversation_id` + nearest `time_in_call_secs`, and if `|secs − time_in_call_secs| > 2` writes a superseding note (`am.key = provenance_reconciled`, old value kept in history); `quote` is corrected to the transcript text when the ASR final differs. Nothing is overwritten (Constitution III). Agent Memory hand-off: `memory_outbox/<conversation_id>.json {village, member_id, transcript[], events[], labels: src=call:<id>, secs=, agent=<agent>, village=<id>}` consumed by FS-6.

## events written by FS-2 (`event.schema.json`)
`money_request`, `verification_pending`, `verification_confirmed|denied {late, state, answered_via}`, `verification_timeout {reason, state}`, `verification_answer_conflict`, `incident` (upsert `inc_<verification_id>`, `type ∈ suspected_scam|unverified_money_request|money_request_confirmed|call_failed`), `pattern`, `escalation {reason: money_request, channel: outbound_call, status, call_id}` for the dial, `consent` (via Join). Bindings changed: `alerts:active`, `verifications:pending?member=me`, `incidents:open`, `blueprint:life_areas`, `scams_stopped` counter (control).

## chat message (D16, V2; not in contract 1.0.0)
`message{village, author: village, text, kind: incident, refs: [inc_<verification_id>, money_request event id], at}` posted by Core when the incident opens or updates; WS type `chat`. FS-2 only emits the event; the chat post is a core/kit concern once the orchestrator adds `message` + `chat` to the contract.

## WS messages used
S→C `prompt {verification_id, question, detail, options[{id: yes|no|unsure, label}], deadline, closed?}` only to the claimed member's sockets; C→S `action {name: answer_verification, payload{verification_id, answer}}` → S→C `result {req_id, ok, decision}`; `event{…, data}` fan-out per role; `control{kind: gate|reasoning|counter}` to the Control Room.
