# Data model: Memory & evolve (FS-6)

Contract types: `proposal.schema.json`, `event.schema.json` (`pattern`, `spec_patch_proposed`, `spec_patch_applied`, `money_request`, `med_change`…), `ws_messages.schema.json` (`patch`, `bv_proposal`, `control`). Everything else below is internal.

## 1. Agent Memory conventions (`core/memory/conventions.py`)

**Context**: `SURREAL_MEMORY_CONTEXT` (one per deployment, e.g. `village-demo`; use a fresh one for the demo so Workbench turns don't pollute it).

**Scopes** (DNF wire format: `[["a","b"]]` = a AND b):

| Scope | Who writes | Who reads |
|---|---|---|
| `village/<village_id>` (e.g. `village/v_reyes`, `village/v_w147`) | outbox (all event-derived triples) | Fact view, detector, Ask-why, builder |
| `[["village/<id>","agent/momline"]]` | transcript ingestion from the Mom line | Fact view (spans), Ask-why |
| `[["village/<id>","agent/evolve"]]` | detector notes (`infer: none` memory chunks: "raised proposal X because …") | Ask-why |
| `[["village/<id>","agent/builder"]]` | builder reasoning notes (optional) | Ask-why |
| `[["village/<id>","agent/release"]]` | release summaries (optional) | Ask-why |

Keys: one data-plane key per agent when the plan allows (`SURREAL_MEMORY_API_KEY_<AGENT>`), else one key; attribution always also in labels.

**Entities** (closed type list; our own semantics in names/keys):

| Village thing | Entity | Name convention |
|---|---|---|
| member | `person` | display name from the spec + ` (<member_id>)`, e.g. `Carmen Reyes (m_carmen)`; the id suffix makes lookups deterministic and still reads well in Studio |
| medication | `product` | generic name, e.g. `Lisinopril` |
| village | `organisation` | `Village <village_id>` |
| scam attempt | `event` | `Money request <event_id>` |
| rota shift | `event` | `Shift <date> <slot>` |
| printable/fridge card | `concept` | `Fridge card <village_id>` |

**Keys / relations / actions per event kind** (`triples_for(event)`):

| Event kind | Triples |
|---|---|
| `med_change` | attribute `person.<med>_dose = "<to.dose>"` (key `lisinopril_dose`), with `observed_at=effective`; relation `person takes product` with `valid_from` |
| `dose` | action `person took_dose "<med list> <slot> <time>"`; attribute `last_dose_<slot> = <time>` |
| `dose_repeat_scan`/`dose_repeat` | action `person attempted_repeat_dose "<slot> <time>"` |
| `money_request` | action `person received_money_request "<amount> claimed <claimed_identity> <at>"`; attribute `last_money_request = "<event_id>"`; relation `event(Money request) claims_member person(<claimed>)` |
| `verification_*` | attribute on the Money request event entity: `verification_outcome = confirmed|denied|timeout` |
| `incident` | action `person had_incident "<type> <incident_id>"` |
| `consent` | attribute `person.consent_ai_calls = true|false`, `observed_at=event.at` |
| `shift` | relation `person covers event(Shift …)` with `valid_from/valid_until` |
| `symptom` | action `person reported_symptom "<text>"` |
| `pattern` | attribute `person.pattern_<pattern> = "<count>/<window_days>d"` |
| `spec_patch_applied`, `release` | attribute `organisation.published_rev = <rev>` |
| `qa`, `reminder`, `escalation`, `ack`, `help_request` | none (operational only) |

**Labels on every write**: `src=<source.kind>:<source.ref>` · `secs=<source.secs>` (calls) · `url=<source.url>` (urls) · `agent=<actor.id or 'core'>` · `village=<village_id>` · `event=<event_id>` · `rule=<decision.rule_id>` when a gate decision caused the event. Free text quotes go in the action `object` or a `quote=` label truncated to 120 chars.

**Fact ref format** (used in `proposal.evidence[kind=fact].ref` and the Fact view): `fact:<key>:<member_id>:<YYYY-MM-DD>` (e.g. `fact:money_request:m_carmen:2026-10-16`) resolving to entity + key + observed date; the Fact view resolves it through `/lookup`.

## 2. `am_outbox` (SurrealDB table)

| Field | Type | Notes |
|---|---|---|
| `id` | `am_outbox:<event_id or batch:<conversation_id>>` | idempotency key |
| `village` | `record<village>` | |
| `kind` | `facts` \| `batch` \| `note` | |
| `path` | string | `/facts`, `/facts/batch` |
| `body` | object FLEXIBLE | the request |
| `status` | `queued` \| `sent` \| `dead` | |
| `attempts` | int | |
| `next_at` | datetime | backoff target |
| `last_error` | string ≤ 500 | |
| `am_ref` | object | `{turn_id?, fact_ids?, corrections?}` from the response |
| `created_at`, `sent_at` | datetime | |

Indexes: `(status, next_at)`. Retention: `sent` rows kept for the day (click-through from events).

## 3. `event.am` (existing nullable field on ledger rows)
`{"ref": "<turn_id|fact_id>", "entity": "person/Carmen Reyes (m_carmen)", "key": "last_money_request", "sent_at": …}` set by the outbox on success.

## 4. FactCard (Fact view response, internal)

```json
{"entity":"person/Carmen Reyes (m_carmen)","key":"lisinopril_dose","value":"10 mg","valid_from":"2026-10-03T00:00:00-04:00","valid_until":null,
 "supersedes":{"value":"5 mg","valid_from":"2026-09-01…","valid_until":"2026-10-03…","source":{…}},
 "source":{"kind":"call","ref":"conv_setup_0003","secs":88,"quote":"The doctor changed her lisinopril from five to ten on October third.","event_id":"ev_1003_1740_med_change","span":[412,468]},
 "fact_ref":"fact:lisinopril_dose:m_carmen:2026-10-03","am":{"turn_id":"…","trace_id":"…"},"degraded":false}
```
`FactsResponse = {village, subject, as_of, facts: FactCard[], uncertainties: Uncertainty[], degraded}`; `Uncertainty = {id, entity, key, candidates: [{value, source, kind}], created_at}`.

## 5. EvalRecord (shared with FS-5) — session and experiment variants

| Field | Session eval | Experiment |
|---|---|---|
| `name` | `possible_fraud` | `decision_match` / `caught` / `false_alarm` |
| `conversation_id` | set | — |
| `span_id` | call root span | experiment run span |
| `label` | `possible_fraud` \| `benign` \| `judge_timeout` | `match` / `miss` |
| `score` | 0..1 | 0/1 |
| `explanation` | judge text | expected vs actual |
| `mirror path` | `var/evals/sessions/<conv>.json` | `var/evals/experiments/<name>.json` |

`eval_record` table: `{id: evr_<scope>_<name>, village, kind: release|session|experiment, ref, name, label, score, threshold?, passed?, explanation, span_id, trace_id, model, duration_ms, at}`.

## 6. Measured (`var/evals/measured.json`)
```json
{"dataset":"scam-eval-set","experiment":"scam-gate-20261016T1350","experiment_url":"https://app.arize.com/…",
 "scams":30,"caught":0,"benign":20,"false_alarms":0,"errors":[],"run_at":"2026-10-16T13:52:10-04:00","gate_version":"<git sha>","extraction_model":"anthropic.claude-haiku-5-5"}
```
(`caught`/`false_alarms` filled only by the run; the file does not exist before.)

## 7. Proposal (= `proposal.schema.json`, persisted in table `proposal`)
Status flow and who moves it:

| From → to | Actor | Side effects |
|---|---|---|
| — → `proposed` | detector | `decision` row; `spec_patch_proposed` event (+ `data["proposals:pending"]`); `control{proposal}`; optional voice |
| `proposed` → `verifying` | coordinator approve | `approved_by/at`; builder ops; `target_rev`; `release_id`; `release.run(publish=False)` |
| `verifying` → `ready` | release passed (not pre-approved) | `control{proposal}` |
| `verifying` → `applied` | release passed (pre-approved) | `publish`; `patch` frames; `spec_patch_applied` |
| `ready` → `applied` | coordinator approve | same as above, < 1 s |
| `verifying` → `failed` | release blocked | notify coordinator; `published_rev` unchanged |
| `proposed|ready` → `rejected` | coordinator reject | `decision` row; snooze 24 h |
| any → `failed` | builder invalid twice **and** template unavailable, or stale base | `decision` row |

Uniqueness: one proposal per `(village, subject, pattern)` not in `{rejected, failed}` older than 24 h.

## 8. Decision rows this feature writes (`decision` table, FS-1)
`source=evolve`, kinds: `pattern_detected`, `proposal_raised`, `proposal_approved`, `proposal_applied`, `proposal_rejected`, `proposal_failed`, `builder_fallback_template`, `evals_read_mirror`, `memory_degraded`. Each carries `evidence_labels[]`, `trace_id`, `proposal_id?`, `text` (user-readable, ≤ 400 chars; also streamed as `control{kind: reasoning, source: evolve, kind: decision}`).

## 9. `call_session` (FS-2 table, one field added by request)
`root_span_id` (16 hex) + `trace_id` so the session eval can attach to the call's root span after a restart.
