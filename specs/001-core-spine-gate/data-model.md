# Data model: FS-1 (SurrealDB ns `village`, db `main`)

## Record-id conventions
| Contract id | RecordID | Note |
|---|---|---|
| `v_reyes` | `village:reyes` | strip `v_` (verified gotcha) |
| `m_marco`, `b_tanya` | `member:m_marco` | full id as key |
| `ev_…`, `ver_…`, `dc_…`, `msg_…` | `event:ev_…`, `verification:ver_…`, `decision:dc_…`, `message:msg_…` | core mints before write |
| `st_reyes_morning` | `slot_token:st_reyes_morning` | token hash only, never the token |
| `(village, role)` / `(village, rev)` | `view:reyes_elder` / `spec_rev:reyes_4` | |
| `(subject, slot, date)` | `dose_window:m_carmen_morning_2026_10_15` | |
| idempotency key | `idem:⟨conv_demo_1016_scam:toolu_01⟩` | |
| `inc_…` | no table: `payload.incident_id` on `event` rows; latest row wins | |

`record<…>` fields are always `RecordID` (`core/ids.py`). Inline literals only. `core/db.py` applies every statement below as `DEFINE … IF NOT EXISTS` so boot is idempotent (prefix omitted here for brevity).

## DDL (`core/schema.surql`)
```surql
DEFINE TABLE village SCHEMAFULL;
DEFINE FIELD name ON village TYPE string;
DEFINE FIELD kind ON village TYPE string ASSERT $value IN ['care','block'];
DEFINE FIELD lang ON village TYPE string;
DEFINE FIELD timezone ON village TYPE string DEFAULT 'America/New_York';
DEFINE FIELD coordinator_id ON village TYPE record<member>;
DEFINE FIELD care_recipient_id ON village TYPE option<record<member>>;
DEFINE FIELD kill_switch ON village TYPE bool DEFAULT false;
DEFINE FIELD live_rev ON village TYPE int DEFAULT 0;

DEFINE TABLE member SCHEMAFULL;
DEFINE FIELD village ON member TYPE record<village>;
DEFINE FIELD name ON member TYPE string;
DEFINE FIELD short_name ON member TYPE option<string>;
DEFINE FIELD aliases ON member TYPE array<string> DEFAULT [];
DEFINE FIELD role ON member TYPE string ASSERT $value IN ['coordinator','care_recipient','caregiver','professional_caregiver','resident','volunteer','business','peer'];
DEFINE FIELD view ON member TYPE option<string>;
DEFINE FIELD pronoun ON member TYPE string ASSERT $value IN ['he','she','they'];
DEFINE FIELD lang ON member TYPE string;
DEFINE FIELD phone ON member TYPE option<string>;
DEFINE FIELD token_hash ON member TYPE option<string>;
DEFINE FIELD last_app_session_at ON member TYPE option<datetime>;   -- has_app_session = within 24 h
DEFINE FIELD consent ON member TYPE object FLEXIBLE DEFAULT {};      -- folded scopes; ai_calls NONE = not asked
DEFINE INDEX member_village ON member FIELDS village;
DEFINE INDEX member_token ON member FIELDS token_hash UNIQUE;

DEFINE TABLE consent SCHEMAFULL;                                     -- history; member.consent is the fold
DEFINE FIELD village ON consent TYPE record<village>;
DEFINE FIELD member ON consent TYPE record<member>;
DEFINE FIELD scopes ON consent TYPE object FLEXIBLE;
DEFINE FIELD text_version ON consent TYPE string;
DEFINE FIELD source ON consent TYPE object FLEXIBLE;
DEFINE FIELD event_id ON consent TYPE option<record<event>>;
DEFINE FIELD at ON consent TYPE datetime;
DEFINE INDEX consent_member_at ON consent FIELDS member, at;

DEFINE TABLE view SCHEMAFULL;
DEFINE FIELD village ON view TYPE record<village>;
DEFINE FIELD role ON view TYPE string;
DEFINE FIELD rev ON view TYPE int;
DEFINE FIELD spec ON view TYPE object FLEXIBLE;                      -- village_spec#/$defs/view
DEFINE INDEX view_village_role ON view FIELDS village, role UNIQUE;

DEFINE TABLE spec_rev SCHEMAFULL;
DEFINE FIELD village ON spec_rev TYPE record<village>;
DEFINE FIELD rev ON spec_rev TYPE int;
DEFINE FIELD spec ON spec_rev TYPE object FLEXIBLE;                  -- whole VillageSpec
DEFINE FIELD published ON spec_rev TYPE bool DEFAULT false;
DEFINE FIELD at ON spec_rev TYPE datetime DEFAULT time::now();
DEFINE INDEX spec_rev_unique ON spec_rev FIELDS village, rev UNIQUE;

DEFINE TABLE event SCHEMAFULL;                                       -- append-only ledger
DEFINE FIELD village ON event TYPE record<village>;
DEFINE FIELD kind ON event TYPE string ASSERT $value IN [
  'dose','dose_repeat_scan','dose_repeat','reminder','escalation','ack','symptom','help_request','shift','med_change','consent',
  'money_request','verification_pending','verification_confirmed','verification_denied','verification_timeout','verification_answer_conflict',
  'incident','pattern','spec_patch_proposed','spec_patch_applied','qa','release'];
DEFINE FIELD payload ON event TYPE object FLEXIBLE;
DEFINE FIELD actor ON event TYPE string;
DEFINE FIELD source ON event TYPE object FLEXIBLE;
DEFINE FIELD source.kind ON event TYPE string ASSERT $value IN ['call','app','scan','url','system'];
DEFINE FIELD source.ref ON event TYPE string;
DEFINE FIELD am ON event TYPE option<object> FLEXIBLE;
DEFINE FIELD decision_id ON event TYPE option<record<decision>>;
DEFINE FIELD at ON event TYPE datetime;
DEFINE INDEX event_village_at ON event FIELDS village, at;
DEFINE INDEX event_village_kind ON event FIELDS village, kind, at;

DEFINE TABLE dose_window SCHEMAFULL;
DEFINE FIELD village ON dose_window TYPE record<village>;
DEFINE FIELD subject ON dose_window TYPE record<member>;
DEFINE FIELD slot ON dose_window TYPE string;
DEFINE FIELD date ON dose_window TYPE string;                        -- YYYY-MM-DD village tz
DEFINE FIELD slot_time ON dose_window TYPE string;                   -- HH:MM
DEFINE FIELD due_at ON dose_window TYPE datetime;
DEFINE FIELD state ON dose_window TYPE string ASSERT $value IN ['scheduled','window_open','reminded','escalated_1','escalated_2','taken','skipped_ack','closed'];
DEFINE FIELD dose_event_id ON dose_window TYPE option<record<event>>;
DEFINE FIELD taken_at ON dose_window TYPE option<datetime>;
DEFINE FIELD confidence ON dose_window TYPE option<string>;
DEFINE FIELD reminder_placed_at ON dose_window TYPE option<datetime>;
DEFINE FIELD escalation_placed_at ON dose_window TYPE option<datetime>;
DEFINE FIELD escalated_to ON dose_window TYPE option<record<member>>;
DEFINE FIELD next_check_at ON dose_window TYPE option<datetime>;
DEFINE FIELD version ON dose_window TYPE int DEFAULT 0;
DEFINE INDEX dw_key ON dose_window FIELDS subject, slot, date UNIQUE;
DEFINE INDEX dw_due ON dose_window FIELDS next_check_at;

DEFINE TABLE verification SCHEMAFULL;                                -- verification.schema.json
DEFINE FIELD village ON verification TYPE record<village>;
DEFINE FIELD subject ON verification TYPE record<member>;
DEFINE FIELD claimed_member_id ON verification TYPE record<member>;
DEFINE FIELD claimed_identity ON verification TYPE string;
DEFINE FIELD origin ON verification TYPE string ASSERT $value IN ['report_money_request','start_verification'];
DEFINE FIELD conversation_id ON verification TYPE option<string>;
DEFINE FIELD money_request_event_id ON verification TYPE option<record<event>>;
DEFINE FIELD request ON verification TYPE object FLEXIBLE;           -- {amount, currency, method, urgency, red_flags}
DEFINE FIELD state ON verification TYPE string ASSERT $value IN ['pending','default_spoken','confirmed','late_confirmed','denied','late_denied','unsure','unreachable','timed_out'];
DEFINE FIELD status ON verification TYPE string ASSERT $value IN ['pending','confirmed','denied','timeout'];
DEFINE FIELD channels ON verification TYPE array<object> FLEXIBLE DEFAULT [];
DEFINE FIELD answers ON verification TYPE array<object> FLEXIBLE DEFAULT [];
DEFINE FIELD created_at ON verification TYPE datetime;
DEFINE FIELD deadline ON verification TYPE datetime;                 -- created_at + 45 s
DEFINE FIELD call_placed_at ON verification TYPE option<datetime>;
DEFINE FIELD await_returned_at ON verification TYPE option<datetime>;
DEFINE FIELD resolved_at ON verification TYPE option<datetime>;
DEFINE FIELD spoken_say_key ON verification TYPE option<string>;
DEFINE FIELD incident_id ON verification TYPE option<string>;
DEFINE FIELD pattern_flag ON verification TYPE option<string>;
DEFINE FIELD version ON verification TYPE int DEFAULT 0;
DEFINE FIELD transitions ON verification TYPE array<object> FLEXIBLE DEFAULT [];
DEFINE INDEX ver_open ON verification FIELDS village, state, deadline;
DEFINE INDEX ver_conv ON verification FIELDS conversation_id, claimed_member_id;

DEFINE TABLE decision SCHEMAFULL;                                    -- user-readable decisions log
DEFINE FIELD village ON decision TYPE record<village>;
DEFINE FIELD input_kind ON decision TYPE string;
DEFINE FIELD input ON decision TYPE object FLEXIBLE;                 -- candidate + alloc
DEFINE FIELD decision ON decision TYPE object FLEXIBLE;              -- gate#/$defs/decision
DEFINE FIELD rule_id ON decision TYPE string;
DEFINE FIELD idempotency_key ON decision TYPE option<string>;
DEFINE FIELD event_ids ON decision TYPE array<record<event>> DEFAULT [];
DEFINE FIELD trace_id ON decision TYPE option<string>;
DEFINE FIELD at ON decision TYPE datetime;
DEFINE INDEX decision_village_at ON decision FIELDS village, at;

DEFINE TABLE idem SCHEMAFULL;                                        -- id = ⟨key⟩
DEFINE FIELD village ON idem TYPE record<village>;
DEFINE FIELD decision_id ON idem TYPE record<decision>;
DEFINE FIELD response ON idem TYPE object FLEXIBLE;                  -- exact first body
DEFINE FIELD at ON idem TYPE datetime DEFAULT time::now();

DEFINE TABLE slot_token SCHEMAFULL;                                  -- id = token_ref
DEFINE FIELD village ON slot_token TYPE record<village>;
DEFINE FIELD subject ON slot_token TYPE record<member>;
DEFINE FIELD slot ON slot_token TYPE string;
DEFINE FIELD token_hash ON slot_token TYPE string;
DEFINE FIELD revoked ON slot_token TYPE bool DEFAULT false;
DEFINE FIELD last_scan_at ON slot_token TYPE option<datetime>;      -- 10 s dedup
DEFINE FIELD last_decision_id ON slot_token TYPE option<record<decision>>;
DEFINE INDEX slot_token_hash ON slot_token FIELDS token_hash UNIQUE;

DEFINE TABLE message SCHEMAFULL;                                     -- D16 village chat
DEFINE FIELD village ON message TYPE record<village>;
DEFINE FIELD author ON message TYPE string;                          -- member id | 'village' | 'system'
DEFINE FIELD kind ON message TYPE string ASSERT $value IN ['chat','incident','proposal','receipt','nudge','answer'];
DEFINE FIELD text ON message TYPE string ASSERT string::len($value) <= 2000;
DEFINE FIELD refs ON message TYPE array<string> DEFAULT [];          -- event / fact / trace / proposal ids
DEFINE FIELD source ON message TYPE object FLEXIBLE;                 -- common.source (app | system)
DEFINE FIELD at ON message TYPE datetime;
DEFINE INDEX message_village_at ON message FIELDS village, at;
```
Rota = latest `shift` event per date; meds and dose slots live in `spec_rev.spec`; no extra tables for V0–V2.

## State machine tables

**Verification** (`verification.schema.json#x-state-machine`, `step_verification`)
| From | On | To | say_key | Emits |
|---|---|---|---|---|
| (create) | report, ≥1 channel | pending | money_hold | verification_pending (+ money_request, pattern?) |
| (create) | no reachable channel | unreachable | money_timeout | verification_timeout{unreachable}, incident |
| pending | answer yes / no / unsure | confirmed / denied / unsure | money_confirmed / money_denied / money_timeout | verification_confirmed · verification_denied + incident · verification_timeout{unsure} + incident |
| pending | await_returned (t ≥ 30) | default_spoken | money_timeout | incident |
| pending | tick (t ≥ 45) | timed_out | money_timeout | verification_timeout{deadline}, incident |
| default_spoken | answer no / yes (t < 45) | late_denied / late_confirmed | – | verification_denied + incident · verification_confirmed |
| default_spoken | answer unsure | unsure | – | verification_timeout{unsure}, incident |
| default_spoken | tick (t ≥ 45) | timed_out | – | verification_timeout{deadline} |
| terminal | answer | same | – | answers[] `ignored` |

Timers: `deadline = created_at + 45 s` (tick loop); await long-poll ≤ 30 s. Invariants: `status = status_of_state[state]`; first applied answer wins (CAS); same value later → `dup`, different → `conflict` + `verification_answer_conflict`, a `yes` winner reports `money_timeout`; `call_placed_at` set at most once; `resolved_at` iff terminal; `incident_id = "inc_" + id`; `transitions[]` appended each change.

**Dose window** (contract enum, `step_dose_window`)
| From | On | To | Actions |
|---|---|---|---|
| scheduled | tick, now ≥ due − 30 m | window_open | – |
| window_open | tick, now ≥ due + 45 m, not quiet hours, no reminder yet | reminded | CALL(subject), EMIT reminder |
| window_open / reminded | tick, now ≥ due + 90 m | escalated_1 | CALL(on_duty), EMIT escalation{level 1} |
| escalated_1 | tick, ≥ 15 m after placement, no answer | escalated_2 | CALL(backup), EMIT escalation{level 2} |
| any open | dose(event) | taken | flag `off_schedule` outside −30 m…+4 h |
| any open | skip_ack | skipped_ack | NOTIFY(on_duty) |
| any open | tick, now ≥ min(due + 4 h, next_due − 2 h) | closed | EMIT escalation{missed_dose} if never escalated |

Gate overlay (in `decide`, not the SM): a `dose` candidate with a dose in the slot within 6 h (confirmed or uncertain) → `R-DOUBLE report_already_logged`; `dose_question{take_another}` same; `{double_already_taken}` → `R-DOSE-ADVICE escalate_family` + `possible_double_dose`. Timers: `next_check_at` = next boundary; one step per tick. Invariants: one window per `(subject, slot, date)`; `taken` requires `dose_event_id`; reminder/escalation placed at most once (timestamps guard warps); quiet hours suppress CALL(subject) only.

## Indexes
`member(village)`, `member(token_hash) U`, `view(village, role) U`, `spec_rev(village, rev) U`, `event(village, at)`, `event(village, kind, at)`, `dose_window(subject, slot, date) U`, `dose_window(next_check_at)`, `verification(village, state, deadline)`, `verification(conversation_id, claimed_member_id)`, `decision(village, at)`, `slot_token(token_hash) U`, `message(village, at)`.
