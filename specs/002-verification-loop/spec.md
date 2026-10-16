# Feature Specification: FS-2 Verification loop (voice)

**Branch:** `lane/voice` (+ `core/voice/`, `core/services.py` seam) · **Version:** V1 (cutoff 12:15) · **Stories:** US-07, 09, 10, 11, 12 · **Status:** Draft, contract 1.0.0

## Problem
Carmen (78, phone-only) gets a call from "Marco" asking for $2,000. She calls the Mom line. Village must (a) take the report, (b) check with the real Marco through a second channel, (c) tell Carmen the outcome word for word, (d) default to "don't send" if nobody answers, and (e) show Ana an incident card with the source moment. The gate rules exist (FS-1); this spec wires the voice channel, the verification record, the in-app prompt and the outbound call around them.

## Scope
In: ElevenLabs agents as code (`agents/`: `mom-line` es/en, `village-caller`, `setup`), eight tools pointing at `https://{{system_env__core_host}}/tools/…`, structured procedures for verbatim `say`, init + post-call webhooks, `core/voice/` handlers over `core/services.py`, `POST /calls/outbound` with consent check, WS `prompt` delivery, `POST /verifications/{id}/answer`, incident event, Twilio import, web-call fallback.
Out: gate rules (FS-1), UI components (FS-4), Agent Memory internals (FS-6), founding conversation content (FS-3; only the `setup` agent shell and `create_village` tool are here).

## User scenarios (Given / When / Then)
Shared state: Reyes village, Fri 2026-10-16 14:02, Carmen on the Mom line from the demo phone (`DEMO_CARMEN_CALLER_ID` → `m_carmen`), judge joined as Marco (`consent.ai_calls=true`, live app session), Ana on the coordinator app. `t` = seconds since the verification was created.

1. **Denied (headline).** Given Carmen says "Me llamó Marco llorando… dos mil dólares"; When the agent calls `report_money_request{claimed_member: marco, amount: 2000, urgency: now}`; Then Core returns `verify_with_member` + `money_hold` within 2 s, the agent says the hold line verbatim, Marco's phone shows the `prompt` ("¿Acaba de llamar a Mamá pidiendo $2,000?") and rings (T3), and when Marco taps "That wasn't me" at t=12 the in-flight `await_verification` returns `denied` with `say: "Ese no era Marco. No mande dinero. Ana ya lo sabe."`, the agent speaks it unchanged, the call to Marco is cancelled, Ana's app gets an `incident` (`suspected_scam`, high) with `source{call, conv_demo_1016_scam, secs: 9}`.
2. **Confirmed.** Given the same; When Marco says "yes" on the outbound call at t=21 and the village-caller posts `verification_answer: yes`; Then `await_verification` returns `confirmed`, Carmen hears `money_confirmed` ("…Village nunca envía dinero; hable con Ana…"), no incident, FYI event to Ana, the app prompt closes (`prompt{closed:true}`).
3. **Timeout, safe default.** Given nobody answers; When t reaches 30; Then `await_verification` returns `timeout` (state `default_spoken`) with `money_timeout`, Carmen hears "No pude confirmar con Marco. No mande dinero. Le aviso a Ana.", an incident (`unverified_money_request`) opens for Ana now; at t=45 the row becomes `timed_out`, the prompt closes, the call is cancelled, no second call is ever placed.
4. **App answer before call answer.** Given both channels open; When the app tap lands first; Then it is `applied`, the outbound call is cancelled (best effort) and if the call still connects the village-caller's later `submit_verification_answer` is stored with `outcome: dup` or `conflict` and never changes what Carmen heard.
5. **Call answer after timeout.** Given scenario 3 at t=38; When Marco says "no" on the call; Then the row goes `default_spoken → late_denied`, event `verification_denied{late: true}`, Ana's incident updates to "Marco says it wasn't him"; Carmen hears nothing new (P2 callback is out of scope).
6. **Caller not in village.** Given an unknown `caller_id`; When the init webhook runs; Then Core still returns all seven dynamic variables with `member_id: m_unknown`, a guest first message, and any money tool from that call resolves to R-MONEY-NEVER (`deny`, `money_never`, T42) with an incident to Ana; no verification is opened.
7. **Marco without consent → app prompt only.** Given `m_marco.consent.ai_calls=false` (before Join) or claimed member `m_lucia`; When `report_money_request` runs; Then `channels=[app_prompt]`, `POST /calls/outbound` returns `placed: false` with decision R-VERIFY-CONSENT, and the rest behaves as scenarios 1–3 (T44, T38).
8. **Duplicate tool call.** Given ElevenLabs retries `report_money_request` with the same `(conversation_id, tool_call_id)`; Then Core returns the byte-identical cached response, the same `verification_id`, no second prompt, no second call (T49). Same for `await_verification` on a terminal row (cached `say`).
9. **Core down mid-call, fixed script.** Given Core returns 503 or the tool times out; When the procedure's `on_failure` fires; Then the agent speaks a pre-written line and never improvises: for care tools "No pude anotarlo. Le aviso a su familia."; for either money tool the safe default "No pude confirmar con su familia. No mande dinero. Le aviso a Ana." (`money_core_down`, see research R7).

## Functional requirements
- **FR-001** Three agents exist as code in `agents/` and push with `elevenlabs agents push`; the repo is the source of truth (no dashboard-only edits).
- **FR-002** Every server tool POSTs JSON that validates against `voice_tools.schema.json#/$defs/req_<tool>` to `https://{{system_env__core_host}}/tools/<tool>` with header `X-Village-Secret` from the `core_secret` workspace env var; every tool body carries `conversation_id`, `caller_id`, `call_secs`, `utterance`, `village_id`.
- **FR-003** Every tool response is `{decision, say, say_key?, rule_id, lang, decision_id?, data?}`; the agent speaks `say` verbatim via a structured procedure (fallback: prompt rule + Arize eval).
- **FR-004** `report_money_request` → `services.start_verification` → gate (R-MONEY-*) → persists a `verification` row, writes `money_request` + `verification_pending` (+ `pattern`) events, sends WS `prompt` to the claimed member's sockets, and places at most one outbound call if R-VERIFY-CONSENT allows. Response ≤ 2 s.
- **FR-005** `await_verification` long-polls in Core ≤ 30 s and returns the gate `say` for the terminal state or the safe default at 30 s (`default_spoken`); ElevenLabs `response_timeout_secs = 35`.
- **FR-006** Deadline 45 s from creation, enforced by the 5 s tick on the shared `Clock` (time-warp applies).
- **FR-007** Answers arrive via WS action `answer_verification` (preferred), `POST /verifications/{id}/answer` (member token) or the village-caller tool `submit_verification_answer` (`X-Village-Secret`). First answer wins by CAS on `version`; later answers are stored as `dup | conflict | ignored`; a conflict emits `verification_answer_conflict` and never upgrades to "send".
- **FR-008** `POST /calls/outbound` re-reads `consent.ai_calls` at dial time, sets `call_placed_at` by CAS (never redials), calls ElevenLabs `POST /v1/convai/twilio/outbound-call` with the T3 dynamic variables and `ringing_timeout_secs: 30`, and stores `conversation_id`/`callSid` on the `outbound_call` channel.
- **FR-009** Init webhook maps `caller_id` → village + member and returns `conversation_initiation_client_data` with all seven declared dynamic variables; unknown callers get the guest set, never a non-2xx.
- **FR-010** Post-call webhook verifies `ElevenLabs-Signature` (HMAC, timestamp window) before parsing, always returns 200 afterwards, reconciles `source.secs`/`quote` on events keyed by `conversation_id` + `time_in_call_secs`, stores `data_collection_results.verification_answer` as a backup answer keyed `(verification_id, call_sid)`, and hands the transcript to the Agent Memory outbox (stub).
- **FR-011** Idempotency key `(conversation_id, tool_call_id)`, falling back to `(conversation_id, tool, call_secs)`; plus one open verification per `(conversation_id, claimed_member)`.
- **FR-012** Incident rows are upserts with id `inc_<verification_id>`, carry `related_event_ids`, `verification_id`, and `provenance[]` in the `bv_incident` binding; no account/card digits ever (redacted at ingest, `#`). V1 delivers the incident as the `incident` event + IncidentCard binding; from V2 (D16) Core additionally posts it to the village chat as `message{author: village, kind: incident, refs: [inc_<id>, ev_…]}` over WS `chat`. The `prompt` to the claimed member is unchanged by D16 (it is not a chat message).
- **FR-013** Every handler, gate call, WS send, outbound placement and webhook is a span (`session.id = village-<id>`, `user.id` = member; GUARDRAIL kind for gate, TOOL for tools).
- **FR-014** The family word is spoken only by the village-caller on outbound calls, never on the Mom line, never on voicemail, and is redacted as `[PALABRA]` in traces and transcripts.
- **FR-015** A web-call fallback (browser WebRTC to `mom-line`) exercises the same tools; on web calls `caller_id` is empty and Core resolves the subject from `village_id` → care recipient.
- **FR-016** Twilio number imported into ElevenLabs via `POST /v1/convai/phone-numbers`, assigned inbound to `mom-line`, reused for outbound by `village-caller`.

## Edge cases
- `report_money_request` with `claimed_member` that resolves to a member but no app session and no consent → row created `unreachable`, first `await` returns at once with `money_timeout` (T45).
- Two reports in one call for the same member → the existing row is returned.
- `call_initiation_failure` webhook → channel `outbound_call.status = failed`, prompt stays open, no retry to another sibling for verification (T3 is one person only).
- Restart mid-pending → row with `call_placed_at` set is never redialed; past-deadline rows closed by the first tick.
- Consent revoked between creation and dial → no call, channel `skipped_no_consent`.
- ElevenLabs times out `await` at 35 s anyway → procedure `on_failure` speaks the same safe default; Core's 30 s CAS still runs.
- Time-warp during a pending verification → deadline compares against the warped clock (test with FakeClock).
- Post-call webhook arriving before the tool-time rows exist (never expected; log and skip).
- Digits in `utterance` matching account/card patterns are replaced with `#` before storage, traces and Memory.

## Constitution check
- I: every consequential action goes through `services.decide`/`start_verification` (pure gate, model off); silence is safe (FR-005/006). ✔
- II: verification with the named member through a second channel; calls only after recorded consent (FR-008). ✔
- III: `source{kind: call, ref, secs, quote}` on every event; post-call reconcile supersedes, never overwrites (FR-010). ✔
- V: every spoken safety line is gate-owned or pre-written in the agent config; nothing generated at runtime (FR-003, scenario 9). ✔
- VI: builds only against `contracts/`; the one gap (`money_core_down` say key, `GET /voice/token`) is reported to the orchestrator, not forked. ✔
- VIII: FR-013 spans; no invented metrics. ✔
- IX: one WebSocket, in-process long-poll, config over code (agents as JSON). ✔
