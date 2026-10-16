# Research: FS-1 Core spine & safety gate

## Decisions already made
| Decision | Pointer |
|---|---|
| WebSockets only (SSE buffers through tunnels); one socket per client; snapshot on reconnect | DECISIONS D4; `research/public-url.md` |
| SurrealDB Cloud is the operational store; Core subscribes with LIVE SELECT; phones never touch the DB | D5; `research/surrealdb.md` §6 |
| Local fallback `surreal start memory` (ws); embedded `mem://` has no LIVE | `research/surrealdb.md` §6, §8 |
| `record<…>` needs `RecordID`; `DEFINE` can't take `$params`; `event.kind` ASSERT == contract kinds | ARCHITECTURE-VALIDATION §2 edge 2, §4.3 |
| CAS `UPDATE … WHERE version = $v` returns `[]` when stale (inner list) | D5 |
| Deadline rows + 5 s tick loop in Core; catch up on boot; no APScheduler | `research/real-world-architecture.md` §1 |
| `Clock.now() = real + offset`; warp runs a tick; FakeClock, model off | same §1 |
| Gate pure; core pre-mints `alloc` and passes `now`; gate returns `writes[]` | `contracts/README.md` decision 6; `gate.schema.json` |
| Verification 45 s deadline / 30 s await / `default_spoken` answerable; late answers update the incident only | `policy_cases.md` SM; README decision 3; `verification.schema.json#x-state-machine` |
| Lid scan: token is identity, 10 s dedup, second scan = report + escalate on-duty `both` | D3, D13; README decision 4; `lid_scan_sequence.json` |
| Idempotency `(conversation_id, tool_call_id)`, fallback `(conversation_id, tool, call_secs)`; actions `(member, req_id)` | CLAUDE.md rule 6; `voice_tools.schema.json#common_fields` |
| In-app prompt primary, outbound call secondary | ARCHITECTURE-VALIDATION §4.2 |
| Village chat with Village as participant; `message` rows; `chat` frames; elder's chat is the phone line | D16 |

## Open questions and the resolving test
| # | Question | Resolves when | Script |
|---|---|---|---|
| Q1 | Cloud LIVE latency under 4 live queries + 30 sockets | p50 < 300 ms, 10/10 notifications | `uv run smoke/06b_surreal_live.py --n 20`, then `acceptance/v0.sh` on Cloud |
| Q2 | Cloud signin shape; `DEFINE … IF NOT EXISTS` accepted on Cloud 3.x | `apply_schema()` twice, no error | `uv run python -m core.db --apply` (T004) |
| Q3 | surrealdb 3.0b `subscribe_live` yields `{action, result}` or the record only | a test row reaches a WS client | `smoke/10_spine_local.py`; `acceptance/v0.sh` step 3 |
| Q4 | LIVE on `verification` UPDATE carries the full record (prompt close) | `state` present in the notification | `acceptance/v1.sh` step 2 |
| Q5 | Rota 2026-10-16: `reyes_family.json` + seed `shift` say Marco/Ana; `policy_cases` T10, gate T29 example and README decision 1 say Ana/Lucía | orchestrator aligns; FS-1 reads the `shift` row | `test_policy_cases.py::T10` fails until aligned |
| Q6 | `escalation.related_event_id` in the lid fixture names the sibling row id the gate can't know (`alloc` has no event ids) | core fills it after minting; gate omits it | scan route test vs `lid_scan_sequence.json` step 3 |
| Q7 | `unreachable` verification vs `verification_pending.channels minItems 1` | gate writes `verification_timeout{unreachable}` + `incident`, no `verification_pending`; voice `status: unverifiable` | `test_policy_cases.py::T45` |
| Q8 | `R-WINDOW/R-CONSENT/R-MISSED/R-DOSE-ADVICE/R-911/R-AUTONOMY/R-SPEC/R-KILL/R-NOOP` exist in `common.rule_id` but `policy_cases.md` defines only `P-*` | mapping in spec FR-009; P-ids listed after the R-id in `rules_fired` | `test_policy_cases.py` |
| Q9 | `policy_cases.md` money header says 2026-10-15 / `c_1015a`; fixtures say 2026-10-16 / `conv_demo_1016_scam` | tests use fixture values | `test_policy_cases.py` |
| Q10 | `ws_sequence_scam.json` Marco snapshot has `is_my_turn: true, on_duty: m_marco` but `answer: "No. Ana is on tonight."` | `bindings.rota_me()` derives `answer` from `is_my_turn`; fixture text not asserted | `test_bindings.py` |
| Q11 | Re-fire `remind` after a backwards warp? | no (`reminder_placed_at` guard, T07) | `test_sm_dose_window.py` |
| Q12 | D16 `chat` frame, `message` schema and `POST /villages/{id}/messages` are absent from contracts 1.0.0 | orchestrator bumps to 1.1.0; until then Core uses the local model in `contracts/README.md` | `test_messages.py` validates against the local model |

## Names that differ (contract wins)
`hold_and_escalate → report_already_logged + escalate`; `verification_requested → verification_pending`; `verification_unsure|unreachable → verification_timeout{reason}`; `verification_answer_dup → answers[].outcome = dup`; research dose states `OPEN/REMINDING/ESCALATING/ACKED/UNRESOLVED/CLOSED_MISSED → window_open/reminded/escalated_1/escalated_2/skipped_ack/closed`; `POST /admin/clock{advance_min} → POST /clock/warp{minutes}`.
