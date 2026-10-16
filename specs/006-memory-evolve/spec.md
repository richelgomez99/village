# Feature Specification: Memory & evolve (FS-6)

**Feature Branch**: `006-memory-evolve` · **Created**: 2026-10-16 · **Status**: Draft · **Version**: V4 (cutoff 14:15) · **Lanes**: memory, evals, builder (core and release are consumed)

**Input**: PRODUCT.md FS-6 row; US-13, US-14, US-15, US-16; LAYERS.md V4 row and the Rebuild climax (1:25–2:25); DECISIONS.md D5 (Agent Memory holds facts with provenance), D13 Evolve (detect → investigate → fix → verify → human approves; measured number; receipts), D15 + addendum (rebuild trigger is conversational + self-detected); ARCHITECTURE-VALIDATION.md edge 14 (Agent Memory via outbox, never on the safety path) and edge 15 (rebuild chain budget 30–55 s); FLEET.md memory + evals + builder lanes; `data/datasets/policy_cases.md` R-MONEY-PATTERN (T46/T47); `data/datasets/scam_eval_set.jsonl`; `prompts/builder_system.md` (patch_app, v1/v2 delta); `contracts/schemas/{proposal,event,village_spec}.schema.json`; `research/surrealdb.md`, `research/arize-bedrock.md`, `research/innovation-scout.md` (#1 Gauntlet, #5 memory-driven evolution).

**Plain words for the stage**: "it remembers where every fact came from, notices a pattern, asks Ana, and rebuilds itself — tested — on every phone."

## Why this exists

FS-5 proves a version can be released safely. FS-6 is why a new version exists at all: Village keeps a memory of every fact with its source, notices (from its own evals and its memory) that Carmen has had two money-request calls, raises it with Ana, and, once she says yes, writes the change, runs it through the release gate, and patches every phone live. The scam eval set gives the one measured number in the pitch. Nothing here touches the deterministic safety path: Agent Memory is written through an outbox and read only by the Fact view, the detector and Ask-Village-why.

## User Scenarios & Testing

### User Story 1 — Village raises a pattern and Ana approves a rebuild (US-14, US-15, US-16; Priority P1)

After today's scam call, Village says to Ana (card on her app and the Control Room; optionally by voice): "Mom's had two of these calls. Want me to change her app?" The card shows the evidence (Oct 9 call at 0:21, today's call at 0:09, the Arize `possible_fraud` eval on both sessions, the memory fact with its source). Ana taps "Sí, hazlo" (or says it). Village writes the change (`ScamCheck` "¿Es de verdad?" for Carmen, "Scam alerts" `IncidentCard` for Marco/Lucía, family word first on the fridge card), runs it through FS-5, and when it passes every phone grows the new card.

**Why P1**: this is the V4 acceptance and the climax of the pitch (D15).

**Independent test**: with the seeded Oct 9 ledger + today's `money_request` event present, `evals.detect_patterns("v_reyes")` returns one proposal with ≥ 3 evidence items; `POST /villages/v_reyes/proposals/{pid}/approve` leads to `status=applied`, `published_rev=5`, and a `patch{role: elder, highlight: ["scam"]}` frame on Carmen's socket.

**Acceptance scenarios**

1. **Given** the ledger has `money_request` events on 2026-10-09 and 2026-10-16 for `m_carmen` (gate flag `possible_fraud_pattern` per R-MONEY-PATTERN, `pattern` event emitted) and the session eval `possible_fraud` is logged for both sessions, **When** the detector runs, **Then** exactly one proposal `prop_reyes_scamcheck` with `detected_by=arize_eval` (or `memory_pattern` when only the ledger rule fired), `status=proposed`, `base_rev=published_rev`, evidence of kinds `call_moment` ×2, `trace` ×1, `fact` ×1 is created; the coordinator's socket receives `event{kind: spec_patch_proposed, data: {"proposals:pending": [...]}}` and the Control Room receives `control{kind: proposal}`; a decisions-log row explains why.
2. **Given** a `proposed` proposal, **When** Ana approves (WS `action{name: approve_proposal}`, `POST …/approve`, or the voice tool `answer_proposal{answer: yes}`), **Then** `approved_by/approved_at` are set, status → `verifying`, builder `patch_app` runs once per affected role, the ops validate (pydantic + invariants 2–6), a new spec rev `target_rev=base_rev+1` is stored, and `release.run(village, target_rev, trigger="proposal", proposal_id, publish=True)` starts; the Control Room strip narrates it.
3. **Given** the release passes, **When** the `live` stage runs, **Then** core applies the proposal: `published_rev=target_rev`, a `patch{rev, base_rev, role, ops, proposal_id, highlight}` frame per affected role goes to every connected socket of that role, `spec_ops` on printables are applied, `event{kind: spec_patch_applied}` is written, status → `applied`; Carmen's phone shows "¿Es de verdad?" without reload.
4. **Given** the same pattern again (a third call), **When** the detector runs, **Then** no duplicate proposal is created while one is `proposed|verifying|ready` or was `applied` for the same `(village, subject, pattern)`.
5. **Given** a `proposed` proposal, **When** Ana rejects it (`action{name: reject_proposal}`), **Then** status → `rejected`, a decisions-log row records it, the Control Room gets `control{kind: proposal}` with the new status, nothing is built, and the detector does not re-raise it for 24 h.
6. **Given** the release is blocked (tests, Anchor, evals), **When** the pipeline ends, **Then** status → `failed` with `release_id`, Ana's card says "I couldn't make the change safely; nothing changed", `published_rev` is unchanged, and the receipt shows the failed stage.
7. **Given** the rebuild has run for 60 s, **When** the Control Room is on the Rebuild beat, **Then** it shows the afternoon's recorded `rel_reyes_r5` receipt and the pre-verified proposal state; when the live run finishes its result replaces the fallback and the patch still lands; if the live run is blocked, Ana can approve the pre-verified `ready` proposal from the 13:50 run (same ops, same rev 5) and the patch lands from that receipt.

### User Story 2 — Every fact keeps its source and history (US-13; Priority P1)

Any member taps a fact (a dose, the lisinopril change, a money request) and sees where it came from (call + second with a quote, app tap, scan, URL) and what it replaced. Leaders see open uncertainties and can resolve them.

**Independent test**: after seeding, `GET /villages/v_reyes/facts?subject=m_carmen` lists the `lisinopril_dose` chain 5 mg (closed 2026-10-03) → 10 mg with `src=call:conv_setup_0003`, `secs=88`; `GET …/facts/person/m_carmen/lisinopril_dose/history` has two entries, the first `superseded_by` the second.

**Acceptance scenarios**

1. **Given** a ledger event is written by core (after the gate), **When** the outbox worker runs, **Then** an Agent Memory triple (`infer: "triples"`) is written with `scopes=[["village/<id>"]]`, `observed_at=event.at`, labels `src=<source.kind>:<source.ref>`, `secs=<source.secs>` (calls), `agent=<actor>`, `village=<id>`, `event=<event.id>`, and the event row gets `am{turn_id|fact_ref, entity, key}`.
2. **Given** a `med_change` 5→10 mg, **When** both triples are written on the same entity+key through the same path, **Then** history shows the 5 mg value closed and `supersedes` set on the 10 mg value (never overwritten).
3. **Given** a post-call webhook with the transcript, **When** ingestion runs, **Then** `/facts/batch` is called with `session_id=conversation_id`, `extract: whole_conversation`, scopes `[["village/<id>","agent/momline"]]`, and the resulting facts carry `source.span` (quote positions) that the Fact view can show.
4. **Given** Agent Memory answers 503 (or times out), **When** core writes a ledger event or Carmen's call is in progress, **Then** the gate decision, the ledger write and the spoken line are unaffected; the outbox entry stays `queued` with exponential backoff (1 s … 10 min) and `attempts` incremented; the Fact view answers from the ledger-derived mirror with `degraded: true`; no 5xx reaches a phone or ElevenLabs.
5. **Given** two sources disagree on the same key with different provenance kinds (a document vs a call), **When** the Fact view loads, **Then** an uncertainty appears with both values and their sources, and `POST …/uncertainty/{uid}/resolve` (coordinator only) writes the accepted value and supersedes the others.
6. **Given** `?as_of=2026-10-02T00:00:00-04:00`, **When** facts are requested, **Then** `lisinopril_dose` shows 5 mg (what Village believed then).

### User Story 3 — Session evals flag possible fraud and the agent reads its own evals (Priority P2)

Each Mom-line call session gets an in-process judge label `possible_fraud` (or `benign`) with a score and explanation, logged to Arize on the session's root span and mirrored locally. The detector can read the labels from Arize or the mirror.

**Acceptance scenarios**

1. **Given** the Oct 9 seeded session (built from `events_reyes_seed.json` + `scam_call_tool_requests.json` and traced at `reset_demo`), **When** the session eval runs, **Then** `eval.possible_fraud.label=possible_fraud`, `score ≥ 0.8`, explanation cites the gift-card request; the record is in `var/evals/sessions/conv_seed_1009.json` and the `eval_record` table.
2. **Given** today's call ends (post-call webhook), **When** the eval job runs (≤ 20 s after), **Then** the label is logged and the detector is triggered; the eval never runs on the call's tool path.
3. **Given** `ax.spans.list(filter="eval.possible_fraud.label = 'possible_fraud'")` fails or exceeds 5 s, **When** the detector investigates, **Then** it reads the local mirror and the proposal's trace evidence still carries the trace ids (from the mirror), labelled "(mirror)" in the decisions log.
4. **Given** the judge times out twice (20 s + 10 s Haiku), **When** the eval job ends, **Then** the record is `label=judge_timeout`, nothing is logged to Arize for that session, the job is retried once after 60 s, and the ledger `pattern` event alone is still sufficient for the detector (`detected_by=memory_pattern`).

### User Story 4 — The measured number (D13; Priority P2)

The 50-row scam eval set runs as an Arize experiment against the money extraction + gate: for each row the extraction prompt turns the utterance into a `report_money_request` request (or none), the pure gate decides, and code evaluators compare with `expected_decision`. The pitch says "N/30 caught, M/20 false alarms" only from the experiment output.

**Acceptance scenarios**

1. **Given** the dataset `scam-eval-set` (50 rows from `scam_eval_set.jsonl`) exists in Arize, **When** `evals.scam_experiment.run()` runs, **Then** an experiment `scam-gate-<ts>` with evaluators `decision_match`, `caught` (scam rows), `false_alarm` (benign rows) completes, and `var/evals/measured.json` holds `{scams, caught, benign, false_alarms, experiment_url, run_at}`.
2. **Given** `measured.json` exists, **When** the pitch lane builds Devpost/README, **Then** it reads the numbers from the file; any text still containing `[MEASURE:` fails `acceptance/v4.sh`.
3. **Given** Bedrock 429s during the run (concurrency 4), **When** rows fail, **Then** they are retried twice and any still-failing row is reported as `error` (counted as not caught / not a false alarm, and listed), never silently dropped.

### User Story 5 — Builder prompt v1 → v2 experiment (optional Q&A material; Priority P3)

`POST /improve {mode: builder_prompt}` runs the builder on `data/datasets/group_descriptions.jsonl` with Prompt Hub labels v1 and v2, evaluators `spec_valid` + `spec_coverage` (money-area villages must have an `IncidentCard` bound to `incidents:*`), and promotes v2 to `production` only if it wins with `spec_valid=100%`.

**Acceptance scenario**: both experiments exist in Arize; the Reyes village stays on the v1-built spec (the Evolve patch is what adds the scam card on stage).

### User Story 6 — Ask-Village-why can cite memory and evals (US-18 data; Priority P3)

FS-3's `/villages/{id}/ask` is given data sources from this feature: `memory.facts_for`, `memory.fact_history`, `evals.session_labels`, `evals.latest_measured`, plus the decisions log. Answers cite `fact:`, `trace:`, `dc_` ids.

### Edge cases

- Builder `patch_app` output invalid after one repair (unknown type, bad path, missing `needs_served`): use the reviewed template ops for the pattern (`contracts/schemas/proposal.schema.json` example) and log a decision "builder patch invalid; reviewed template used" (Constitution V: catalog-only; CLAUDE.md rule 3).
- Patch base mismatch (`base_rev != published_rev` at approve time because a release happened in between): rebase by re-running `patch_app` against the current view; if ops are identical proceed, else proposal → `failed` with reason `stale_base`.
- Scopes not registered in Agent Memory (`unknown scope node`): the outbox registers `village/<id>` and `agent/<name>` once (cached) and retries.
- Agent Memory key limits (Sandbox plan): one data-plane key with `agent=` labels; per-agent keys only if available (R-03 in `research.md`).
- Transcript ingestion returns facts on a key the triples path also uses (cross-kind uncertainty by design): triples use operational keys (`lisinopril_dose`, `last_money_request`), turns get their own LLM-chosen keys; conflicts are shown as uncertainty, never auto-resolved.
- Shadow villages (`*_qa`) and `v_smoke_*` never reach the outbox or the detector.
- Proposal for the block village: the detector is village-agnostic (it reads `pattern` events); only the ops template is pattern-specific.

## Requirements

### Functional requirements

- **FR-001** `core/memory/` MUST provide an Agent Memory client over raw httpx (`/facts` with `infer: triples|full`, `observed_at`, `labels`, `scopes`; `/facts/batch`; `/entities/{type}/{name}[/history[/{key}]]` with `asOf`; `/query` with `lens`/`asOf`; `/uncertainty` list + `/resolve`; `/scopes`) and MUST only be called from the outbox worker, the Fact view endpoints, Ask-Village-why and the detector — never from `core/gate/`, the voice tool handlers' response path, or the WS action path (Constitution I, III).
- **FR-002** Every Agent Memory write MUST carry labels `src=<kind>:<ref>`, `secs=<n>` (when `source.kind=call`), `agent=<actor>`, `village=<id>`, `event=<event_id>` and the correct `observed_at` (event time, not write time); writes go through the `am_outbox` table with at-least-once delivery, idempotent on `event_id` (Constitution III).
- **FR-003** Entity/key conventions in `data-model.md` §3 MUST be used so that the same fact always lands on the same entity+key (deterministic supersession chains).
- **FR-004** Post-call transcripts MUST be ingested with `infer: full` via `/facts/batch` (`session_id=conversation_id`) under scopes `[["village/<id>","agent/<agent>"]]` so facts carry `source.span`; this is queued, never awaited by the webhook.
- **FR-005** Fact view endpoints: `GET /villages/{id}/facts?subject=&as_of=` (merged Agent Memory `/lookup` + ledger events with `source`), `GET /villages/{id}/facts/{entity}/{key}/history`, `GET /villages/{id}/facts/uncertainty`, `POST /villages/{id}/facts/uncertainty/{uid}/resolve` (coordinator token); on Agent Memory failure they MUST answer from the ledger mirror with `degraded: true` within 2 s.
- **FR-006** `evals/session_possible_fraud.py` MUST judge each completed call session in-process (Claude, 20 s budget, Haiku retry) over the tool-call spans + transcript, log `eval.possible_fraud.{label,score,explanation}` on the session root span with `update_evaluations`, and mirror to `var/evals/sessions/<conversation_id>.json` + `eval_record`. It runs from a post-call job, never on the tool path.
- **FR-007** `evals.detect_patterns(village) -> list[Proposal]` MUST fire when (a) the ledger has ≥ `MONEY_PATTERN_MIN=2` `money_request` events for a subject within `MONEY_PATTERN_WINDOW_D=30` days (the gate's `pattern` event; R-MONEY-PATTERN) or (b) ≥ 2 sessions in 30 days carry `possible_fraud`; evidence MUST include `call_moment` items (from event `source{ref, secs, quote}`), `trace` items (Arize or mirror) and `fact` items (Agent Memory refs); one open proposal per `(village, subject, pattern)`.
- **FR-008** Raising a proposal MUST notify the coordinator's app (`event{kind: spec_patch_proposed, data["proposals:pending"]}`), the Control Room (`control{kind: proposal}`), and optionally voice (ElevenLabs village-caller procedure reading the proposal title; tool `answer_proposal`), and MUST write a decisions-log row with the evidence labels (Constitution VIII).
- **FR-009** Approval MUST be by the coordinator only (R-SPEC; Constitution II): `POST /villages/{id}/proposals/{pid}/approve` or WS `approve_proposal` or voice `answer_proposal{yes}`; approval on a `proposed` proposal starts verification and auto-applies on `ready` (consent already recorded); approval on `ready` applies at once; any other status → 409.
- **FR-010** The change MUST be produced by builder `patch_app` (one call per affected role, Prompt Hub `village-builder` label `production`, `using_prompt_template` on the span), validated (pydantic + contract invariants), one repair, then the reviewed template ops; ops are limited to `add/remove/replace` under `/elements` (≤ 12 per role) and `spec_ops` to `/printables/*` (Constitution V).
- **FR-011** Verification MUST be FS-5's `release.run(..., trigger="proposal")`; the live patch MUST be sent as `patch` frames per role with `proposal_id` and `highlight`, and `spec_patch_applied` MUST be written; `published_rev` moves only through the release.
- **FR-012** The scam eval set experiment MUST run as an Arize experiment over the 50 rows with the extraction prompt + pure gate as the task and code evaluators; `var/evals/measured.json` is the only source of the numbers in README/Devpost/pitch (Constitution VIII).
- **FR-013** Every step MUST be a span: `evolve.detect` AGENT with `evals.read` TOOL + `memory.read` TOOL children, `builder.patch_app` LLM/AGENT, `proposal.approve` CHAIN, and the FS-5 release trace linked by `proposal.trace_id`/`release_id`; `session.id=village-<id>`, `user.id=m_ana` on approval.
- **FR-014** Feature flags: `VILLAGE_LAYERS` includes `memory` (outbox + Fact view) and `evolve` (session eval, detector, proposals); V3 must keep working with `evolve` off (Constitution VII).

### Key entities

- **Fact** (Agent Memory attribute/relation/action with provenance labels; mirrored view in the Fact endpoint).
- **OutboxEntry** (`am_outbox`): queued Agent Memory write with retries.
- **EvalRecord** (shared with FS-5): session eval, experiment row summary.
- **Proposal** (`proposal.schema.json`): evidence + ops + status flow.
- **Measured** (`var/evals/measured.json`): the number.
- **Decision row** (`decision` table, FS-1): the user-readable reasoning log entry per detector/approval/rejection.

## Constitution check

| Principle | How this spec serves it |
|---|---|
| I | FR-001: no Agent Memory, no judge, no Arize read on the safety path; the pattern rule stays in the pure gate (`pattern` event), the detector only consumes it. |
| II | FR-009: only the coordinator approves; a `proposed` proposal never builds before a yes; the block village needs its own coordinator. |
| **III** | FR-002/003/004: provenance labels, `observed_at`, supersession chains, uncertainty surfaced not auto-resolved, `as_of` reads; Fact view shows source and what it replaced. |
| **IV** | FR-011: the change ships only through FS-5; a blocked release leaves `published_rev` untouched; the fallback approves a pre-verified proposal, never an unverified one. |
| V | FR-010: catalog-only ops, reviewed template fallback, safety wording untouched by patches. |
| VI | Consumes `proposal`, `event`, `village_spec`, `ws_messages`; additions listed in `contracts/README.md` for the orchestrator. |
| VII | FR-014 flags; `acceptance/v4.sh`. |
| **VIII** | FR-006/012/013: evals logged and mirrored, measured number from a file, every step a span, decisions log rows for raise/approve/reject/fallback. |
| IX | In-process judges, outbox table instead of a queue service, one WebSocket, reuse of FS-5 instead of a second pipeline. |

## Success criteria

- **SC-001** `acceptance/v4.sh` passes: from the seeded state, detector → proposal → approve → release → `applied`; Carmen's socket receives a `patch` with `highlight: ["scam"]`; `published_rev=5`; the Fact view returns the dose chain with sources; `measured.json` exists and no `[MEASURE:` remains in `docs/DEVPOST.md`.
- **SC-002** Approve → patch on phones in `[MEASURE: s]` with the warm pool (target ≤ 55 s; budget 60 s with the receipts fallback).
- **SC-003** 100% of ledger events written after 11:00 have a matching outbox entry; ≥ 95% delivered within 10 s when Agent Memory is up; 0 gate decisions delayed by memory.
- **SC-004** The scam experiment reports `caught/30` and `false_alarms/20` from a completed Arize run (link in `measured.json`).
- **SC-005** Oct 9 and Oct 16 sessions both show `possible_fraud` in Arize and in the mirror.

## Assumptions

- FS-1 writes the `pattern` event per R-MONEY-PATTERN (gate lane, T46/T47) and a `decision` table exists for the decisions log.
- FS-2's post-call webhook delivers the transcript and `conversation_id`; FS-3's Ask-Village-why endpoint accepts injected data sources.
- FS-4 ships `Proposal` (approve/reject), `ScamCheck`, `IncidentCard` and the Fact view screen (`design/Fact.dc.html`).
- FS-5 is green (V3) before any proposal is verified live.
- Agent Memory Context `village-demo` exists with `village/*` and `agent/*` scopes registrable by the key in `.env`.
