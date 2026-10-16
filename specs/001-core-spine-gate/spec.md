# Feature Specification: FS-1 Core spine & safety gate

**Lanes:** core, gate · **Versions:** V0 (11:00), V1 gate/spine parts (12:15), V2 chat (13:00) · **Contract:** 1.0.0 · **Status:** Draft

## Overview
One FastAPI process (`core/`) loads a VillageSpec fixture, applies the SurrealDB schema, subscribes with LIVE SELECT and fans changes out over one WebSocket per client. Every consequential input (lid scan, app action, voice tool, scheduler tick) becomes a `GateInput`, passes the pure gate `decide(state, event) -> Decision`, and only then reaches the ledger. Two pure state machines (dose window, money verification) run on a shared `Clock` with time-warp; updates are compare-and-set on `version`; webhooks are idempotent on `(conversation_id, tool_call_id)`. `core/services.py` is the seam other lanes call. Per D16, Core also keeps the village chat (`message` table, `chat` frames) and posts system messages for incidents, proposals, receipts and rota nudges. Voice (FS-2), builder (FS-3), kit (FS-4), release (FS-5), memory (FS-6) are mocked.

## User scenarios & testing

**US-05 Live state on every phone (V0)**
- Given elder, coordinator and helper clients hello'd at rev 4, When a ledger row is created, Then each receives `event{event, data}` within 1 s, `data` holding only the bindings its view uses.
- Given a client reconnects with `last_rev: 2` at server rev 4, Then it gets a fresh `snapshot`.
- Given `hello.contract_version != 1.0.0`, Then `error{contract_mismatch}` and close.

**US-06 Lid scan logs; second scan reports only (V0)**
- Given `st_reyes_morning` with no dose today, When `GET /s/<token>` at 08:02:10, Then `record` (`R-WINDOW`, `dose_recorded`), one `dose` row `{via: lid_qr}`, `source{scan, st_reyes_morning}`, page `tone ok`; every phone turns green.
- Given the same token within 10 s, Then `deduped: true`, same decision id, no row, no frames.
- Given the same token at 08:40 (inside 6 h), Then `report_already_logged` (`R-DOUBLE`, `dd_report`: "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco."), writes `dose_repeat_scan` + `escalation{to: on_duty, channel: both}`, page `tone report`, no advice wording.
- Given an unknown or revoked token, Then 404 error page, no row.

**US-08 "Is it my turn?" (V0)** Given Marco's view binds `rota:current?member=me`, Then `bv_rota_me` is derived server-side from the latest `shift` row for today.

**US-13 Every fact shows its source (V0 static)** Every `event` carries `source` and `decision_id`; `GET /villages/{id}/decisions` returns the Decision with `rules_fired`, `say_key`, `say_vars`, `writes`.

**US-09/10/11 gate parts (V1)**
- Given T29 state, When `money_request` claims `m_marco`, Then `verify_with_member`, `verification{deadline: now+45 s, channels: [app_prompt, outbound_call], state: pending}`, writes `money_request`, `verification_pending`, `pattern`; `notify m_ana`; `rules_fired = [R-MONEY-VERIFY, R-VERIFY-CONSENT, R-MONEY-PATTERN]`.
- Given pending, When Marco sends `action answer_verification{no}` at t=12, Then CAS → `denied`, `result{decision: advise_do_not_send, say_key: money_denied}`, `prompt{closed: true}`, events `verification_denied` + `incident{inc_ver_…, high}`.
- Given no answer, When `await_verification` returns at t=30, Then `default_spoken`, `money_timeout`, incident upserted; When the tick reaches t=45, Then `timed_out`, `verification_timeout{deadline}`, prompt closed.
- Given the claimed member has `ai_calls=false` and no app session, Then created `unreachable`, `money_timeout` at once (T45). Given `claimed_member_id = null`, Then `advise_do_not_send` (`R-MONEY-UNKNOWN`), no verification, incident now (T36).

**US-17b Village chat (V2, D16)**
- Given Ana posts `POST /villages/v_reyes/messages {text}`, Then a `message{kind: chat, author: m_ana}` row is created and every member client except the elder receives `chat{message}` within 1 s.
- Given Core records an `incident` (or proposal, receipt, rota nudge), Then it also writes `message{author: village, kind: incident, refs: [event_id]}` and fans it out.
- Given a message starting with `@Village`, Then Core routes it to the ask endpoint (FS-3) and posts the answer as `message{author: village, kind: answer, refs: [decision/fact ids]}`; change requests route to proposals in V4.

**Model-off gate tests (V0)** `VILLAGE_LLM=off`, network disabled: `uv run pytest core/gate -q` passes T01–T51 and both SM tables.

## Functional requirements
- **FR-001** `uv run uvicorn core.app:app --port 8787`; pydantic-settings from `.env`; `GET /health` → `{ok, contract_version, now, clock_offset_minutes, layers, deps}`.
- **FR-002** DDL (data-model.md) applied idempotently on boot, inline literals, Cloud or local `surreal start memory`.
- **FR-003** Contract ids ↔ `RecordID` via `core/ids.py` on every write/read; no strings in `record<…>` fields.
- **FR-004** One LIVE SELECT per table (`event`, `view`, `verification`, `message`) on a dedicated connection; reconnect with backoff; `resync` forces snapshots.
- **FR-005** Hub implements `ws_messages.schema.json` plus the D16 `chat` frame: C→S `hello, ack, action, ping`; S→C `snapshot, patch, event, control, prompt, result, pong, error, chat`; `prompt` only to the claimed member; `control` only to role control; `chat` never to elder views.
- **FR-006** `GET /s/{slot_token}`: signature check, 10 s dedup, `GateInput`, `services.decide`, writes, HTML or `lid_scan.schema.json` JSON.
- **FR-007** `POST /v/{id}/actions/{name}` and WS `action` share one gated handler; idempotent on `(member_id, req_id)`.
- **FR-008** `decide()` is pure (no I/O, clock or randomness); ids from `alloc`; output validates against `gate.schema.json#/$defs/decision`; `rules_fired[0] == rule_id`.
- **FR-009** All rules with contract ids: `R-WINDOW`, `R-DOUBLE` (P-DD-01), `R-DOSE-ADVICE` (P-MA-*, P-DD-02), `R-MISSED` (P-ME-*), `R-911` (P-911-*), `R-CONSENT` (P-CO-*, P-PR-*), `R-AUTONOMY`/`R-SPEC` (model_output, spec_patch), `R-KILL`, `R-NOOP`, `R-MONEY-NEVER/VERIFY/DEFAULT/UNKNOWN/PATTERN`, `R-VERIFY-CONSENT`. Say lines only from `policy_cases.md` templates.
- **FR-010** `step_verification(v, event, now) -> (v', emits[])` implements `verification.schema.json#x-state-machine` incl. first-answer-wins, `dup/conflict/ignored`, conflict downgrade, `status_of_state`.
- **FR-011** `step_dose_window(w, event, now) -> (w', actions[])` over `scheduled → window_open → reminded → escalated_1 → escalated_2 → closed | taken | skipped_ack`, constants 45/90/15 min, quiet hours `22:30-07:00`.
- **FR-012** `Clock.now() = real + offset`; `POST /clock/warp{minutes|to|reset}` runs a tick and broadcasts `control{clock}`; tests use `FakeClock`.
- **FR-013** Every `dose_window`/`verification` update is `WHERE id = $id AND version = $v`, `version += 1`; empty result = re-read and re-step.
- **FR-014** `idem` row per `<conversation_id>:<tool_call_id>` (fallback `<conversation_id>:<tool>:<call_secs>`) or `<member_id>:<req_id>`; repeats return the cached body without `decide()`.
- **FR-015** Every Decision persisted to `decision` and broadcast as `control{gate}` before its writes fan out.
- **FR-016** 5 s tick loop over due `dose_window`/`verification` rows; runs on boot and after warp.
- **FR-017** `services.py` exposes `now, decide, record_event, start_verification, answer_verification, await_verification, broadcast, control, post_message`; a stub lands at 10:00.
- **FR-018 (D16)** `message` rows are written by members (`POST /villages/{id}/messages`) or by Core (`author: village|system`) on incident, proposal, receipt and rota nudge; fan-out as `chat`; `@Village` prefix routes to ask (V2) / proposals (V4).

## Key entities
`village`, `member` (+ `consent` history), `view`, `spec_rev`, `event` (append-only), `dose_window`, `verification`, `decision`, `idem`, `slot_token`, `message`.

## Edge cases
| Case | Expected |
|---|---|
| Duplicate webhook (T49) | same `idem` key → identical body; no second verification, prompt or call |
| App and call answers in the same second (T50) | first CAS wins; loser `conflict` + `verification_answer_conflict`; a `yes` winner downgraded to `money_timeout` |
| Late answer after `default_spoken` (T32) | `late_denied/late_confirmed`; incident updated; Carmen's line unchanged |
| Answer after `timed_out` | `outcome: ignored`, no state change |
| Restart mid-verification | rows rebuilt from DB; `call_placed_at` set → no redial; first tick closes rows past deadline |
| Unknown slot token | 404, no row, no frames |
| Warp across a window boundary | tick runs inside warp; one state step per tick, never two calls |
| Warp backwards | `reminder_placed_at`/`escalation_placed_at` guards prevent repeats |
| LIVE reconnect | backoff 0.5→8 s; `resync`; hello with `last_rev` gets a snapshot |
| Scan outside the slot window | `record` with `flags: [off_schedule]`, never blocked |
| Kill switch | `R-KILL`: log only, `flags: [kill_switch]` |
| `@Village` message while ask endpoint is down | message stored; Core posts `kind: answer` "No pude responder ahora" (pre-written), no retry storm |

## Out of scope
ElevenLabs (FS-2), builder and ask endpoint itself (FS-3), kit rendering and Control Room page (FS-4), Daytona/Anchor/Arize (FS-5), Agent Memory (FS-6), QR/join beyond a static token map, SMS, `@Village` change requests (V4).

## Constitution check
**I** pure gate, model-off tests, never-rules as `R-MONEY-NEVER`/`R-DOSE-ADVICE`/`R-CONSENT`; silence = `money_timeout`. **II** verification with the named member; consent checked at dial time. **III** every row and message carries `source`/`refs`; incidents upsert with history. **VI** built on contracts 1.0.0; `services.py` is the seam; the D16 `chat` frame and messages endpoint are flagged for an orchestrator contract bump, not added locally. **VII** `VILLAGE_LAYERS` flags; `acceptance/v0.sh`, `v1.sh` gate the tags. **VIII** every Decision logged and broadcast; `trace_id` slot reserved. **IX** one process, one WebSocket, in-process tick.
