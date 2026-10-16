# Implementation Plan: Memory & evolve (FS-6)

**Branch**: `006-memory-evolve` | **Date**: 2026-10-16 | **Spec**: `specs/006-memory-evolve/spec.md` | **Version**: V4

## Summary

Three modules: `core/memory/` (Agent Memory client + outbox + Fact view data), `evals/` (session eval `possible_fraud`, pattern detector, scam experiment, builder-prompt experiment) and the builder's `patch_app` path (`core/builder/patch.py`). They meet in `core/evolve.py` (core-owned orchestration): detector → proposal → notify → approve → patch_app → `release.run(trigger="proposal")` → live `patch` frames. Memory writes never block anything (outbox). Evals are in-process judges logged to Arize with local mirrors. The number comes from an Arize experiment over the 50-row scam set.

## Technical context

- **Language/stack**: Python 3.13, FastAPI, httpx (Agent Memory REST; the SDK lacks `observed_at` and resolve), pydantic v2; `arize` (`ArizeClient`: `datasets`, `experiments.run`, `spans.update_evaluations`, `spans.list`, `prompts.get`), `pandas`; `anthropic` via `core/llm.py`; SurrealDB Python SDK for `am_outbox`, `eval_record`, `proposal`, `decision` tables.
- **Storage**: SurrealDB Cloud (operational, LIVE), Agent Memory Context `village-demo` (facts), filesystem mirrors under `var/evals/`.
- **Testing**: pytest with `FakeAgentMemory` (httpx `MockTransport`), `FakeJudge`, `FakeArize`, `FakeRelease`; the detector and the outbox are tested model-off.
- **Constraints**: nothing on the safety path; approve→patch ≤ 60 s warm; Agent Memory has no push (Core is the only writer and fans out); Arize eval index lag (read the mirror first when racing).
- **Flags**: `VILLAGE_LAYERS` += `memory,evolve`.

## Constitution check

I ✅ (FR-001 import ban enforced by a test that greps `core/gate` and `core/voice/tools*` for `core.memory`/`evals` imports) · II ✅ (approve routes check the coordinator token; `approved_by` recorded) · III ✅ (labels + `observed_at` + supersession + uncertainty endpoints) · IV ✅ (only `release.run` publishes) · V ✅ (ops validated, template fallback) · VI ✅ (additions requested, not forked) · VII ✅ (flags; `acceptance/v4.sh`) · VIII ✅ (spans, mirrors, `measured.json`, decisions rows) · IX ✅ (outbox table, in-process judges, reuse FS-5).

## Project structure

```text
specs/006-memory-evolve/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
└── contracts/README.md

core/memory/                        # lane: memory
├── __init__.py                     # remember_event(), ingest_transcript(), facts_for(), fact_history(), uncertainties(), resolve_uncertainty()
├── client.py                       # AgentMemory(httpx): facts, facts_batch, entity, history, query, uncertainty, scopes; 2 s connect / 8 s read timeouts
├── conventions.py                  # entity/key/scope/label builders (data-model.md §3); event kind → triples mapping
├── outbox.py                       # am_outbox table, worker loop (2 s), backoff, idempotency on event_id, scope auto-register
├── factview.py                     # merge Agent Memory lookup + ledger mirror; as_of; degraded mode
└── tests/                          # conventions_test, outbox_test (503 → queued, safety path timing), factview_test, mapping_test

evals/                              # lane: evals
├── session_possible_fraud.py       # judge over a call session; log + mirror; job runner
├── detector.py                     # detect_patterns(village) -> list[Proposal]; evidence assembly; Arize read with mirror fallback
├── scam_experiment.py              # dataset upsert, task (extraction + gate), evaluators, measured.json
├── builder_prompt_experiment.py    # v1 vs v2 (optional)
├── arize_io.py                     # update_evaluations wrapper, spans.list wrapper (5 s), experiment helpers
├── mirror.py                       # var/evals/** + eval_record rows
└── tests/

core/builder/patch.py               # lane: builder — patch_app per role, validate, repair, template fallback
core/evolve.py                      # core (orchestrator) — proposal lifecycle, notify, approve, apply; routes in core/routes/evolve.py
core/routes/facts.py                # core — Fact view endpoints (thin, call core.memory)
agents/village-caller/procedures/proposal.yaml   # voice lane (optional) — reads the proposal, tool answer_proposal
acceptance/v4.sh
```

## Module designs with exact call sequences

### A. Agent Memory client and outbox (`core/memory/`)

Scopes (registered once per process, cached; `POST /scopes {"path": …}`, 409 = exists): `village`, `village/<id>`, `agent`, `agent/momline`, `agent/builder`, `agent/evolve`, `agent/release`.

Write path (called by `services.record_event` **after** the ledger commit; returns immediately):
```python
async def remember_event(event: Event) -> None:          # core.memory
    if event.village.endswith("_qa") or event.kind in NO_MEMORY_KINDS: return
    triples = conventions.triples_for(event)            # [] for kinds with no memory meaning (qa, release, reminder)
    if not triples: return
    await outbox.enqueue(kind="facts", village=event.village, event_id=event.id, body={
        "infer": "triples", "scopes": [["village/" + event.village]],
        "observed_at": event.at_utc, "labels": conventions.labels_for(event), "triples": triples})
```
Worker (`outbox.run()` started at app boot when `memory` is enabled):
```python
while True:
    rows = SELECT * FROM am_outbox WHERE status='queued' AND next_at <= time::now() ORDER BY next_at LIMIT 10
    for row in rows:
        try:
            resp = await client.post(row.path, json=row.body)          # POST /api/v1/{ctx}/facts  |  /facts/batch
            await mark_sent(row, resp)                                  # status=sent, am_ref=resp.turn_id/fact ids; UPDATE event SET am = {...}
        except (httpx.HTTPStatusError 5xx/429, httpx.TimeoutException, ConnectError) as e:
            await backoff(row, e)                                       # attempts+1, next_at = now + min(2**attempts, 600) s, last_error
        except httpx.HTTPStatusError 4xx (422 ambiguous triple, 400 unknown scope):
            if "unknown scope" in text: await register_scopes(row); await backoff(row, e, fast=True)
            else: await mark_dead(row, e)                               # status=dead; decisions-log note; never retried automatically
    await asyncio.sleep(2)
```
Transcript ingestion (from FS-2's post-call handler): `ingest_transcript(conversation_id, village, agent, turns)` → outbox `kind="batch"`, `path="/facts/batch"`, body `{"session_id": conversation_id, "extract": "whole_conversation", "scopes": [["village/<id>","agent/<agent>"]], "labels": ["src=call:<id>","agent=<agent>","village=<id>"], "messages": [{"role": "user"|"assistant", "content": text, "at": ts}, …]}` (field names per `research/surrealdb.md` §1; R-01 verifies the exact `messages[]` shape with smoke 06).

Reads (Fact view, detector, Ask-why) use `lens=[["village/<id>"]]`, optional `asOf`, and never run on the WS action or tool path.

### B. Fact view data (`core/memory/factview.py`, routes in `core/routes/facts.py`)
```python
async def facts_for(village, subject=None, as_of=None) -> FactsResponse:
    ledger = await services.events_for(village, subject, until=as_of)       # always available
    try:
        am = await client.lookup(subject_entity, lens=[["village/"+village]], as_of=as_of)   # POST /lookup, 2 s
        unc = await client.uncertainties(entity=subject_entity, resolved=False)
        return merge(ledger, am, unc, degraded=False)
    except MemoryUnavailable:
        return merge(ledger, None, [], degraded=True)
```
Merge rule: one `FactCard` per (entity, key); value chain from Agent Memory history when present, else from ledger kinds (`med_change`, `dose`, `money_request`, `shift`, `consent`); every card carries `source{kind, ref, secs, quote, url}` from labels (`src=`, `secs=`) or the ledger event, `superseded_by`, `valid_from/until`, and `fact_ref` (for proposal evidence). `history()` = `GET /entities/person/<name>/history/<key>`; `resolve()` = `POST /uncertainty/{id}/resolve {"acceptedValue", "note": "<member> via app <ts>"}` (coordinator only; writes a `decision` row).

### C. Session eval `possible_fraud` (`evals/session_possible_fraud.py`)
Trigger: FS-2's post-call handler enqueues `evals.jobs.session_eval(conversation_id, village)`; `reset_demo` enqueues it for `conv_seed_1009` after replaying the seeded session through the traced tool handlers (so a real trace id exists).
```python
@tracer.evaluator(name="session_possible_fraud")
async def judge_session(conv_id, village) -> EvalRecord:
    ctx = await build_session_context(conv_id)        # tool requests/responses from the ledger + transcript (post-call) + gate decisions
    verdict = await judge.run(PROMPT_POSSIBLE_FRAUD, ctx, budget_s=20, retry_model=HAIKU)   # {"label": possible_fraud|benign, "score": 0..1, "explanation"}
    rec = EvalRecord(name="possible_fraud", conversation_id=conv_id, span_id=root_span_id(conv_id), **verdict)
    mirror.write_session(rec); await arize_io.update_evaluations([rec])   # 5 s; failure logged
    await detector.trigger(village, reason=f"eval:{conv_id}")
    return rec
```
Root span lookup: `session_root_span_id(conv_id)` from the tracing helper's in-memory map (filled when FS-2 opens the CHAIN span for the call), persisted in the `call_session` row so it survives restarts. Judge timeout twice → `label=judge_timeout`, no Arize write, one retry at +60 s.

### D. Detector and proposal lifecycle (`evals/detector.py`, `core/evolve.py`)
```python
async def detect_patterns(village) -> list[Proposal]:
    subjects = await ledger.subjects_with(kind="pattern", since_days=30)         # the gate's R-MONEY-PATTERN emission
    flagged = await evals_read.sessions_with_label(village, "possible_fraud", since_days=30)   # Arize spans.list (5 s) → mirror fallback
    for subject in subjects | subjects_of(flagged):
        if await proposals.open_for(village, subject, "possible_fraud_pattern"): continue
        evidence = [call_moment(ev) for ev in money_requests(subject)] + [trace(s) for s in flagged] + [fact(ref) for ref in memory.fact_refs(subject, key="last_money_request")]
        detected_by = "arize_eval" if flagged else "memory_pattern"
        yield Proposal(id=f"prop_{village_short}_scamcheck", detected_by=detected_by, title=…, rationale=…, changes=…, evidence=evidence, ops={}, status="proposed", base_rev=published_rev, created_at=now)
```
`core/evolve.py`:
1. `raise_proposal(p)`: persist (`proposal` table), `decision` row ("Two money requests in 7 days for m_carmen; evidence: …"), `hub.event(coordinator, spec_patch_proposed, data={"proposals:pending": [bv_proposal(p)]})`, `hub.control("proposal", {proposal: p})`, optional `voice.call_coordinator(procedure="proposal", vars={title, rationale, proposal_id})`.
2. `approve(village, pid, member)`: 403 unless coordinator; `proposed` → set `approved_by/at`, status `verifying`, then `asyncio.create_task(verify_and_apply(p))`; `ready` → `apply(p)`; else 409.
3. `verify_and_apply(p)`: `ops = await builder.patch_for_proposal(p)` (section E) → new spec rev `target_rev` stored (`spec_rev` table; `published_rev` untouched) → `p.target_rev, p.release_id` → `receipt = await release.run(village, target_rev, trigger="proposal", proposal_id=pid, publish=False)` → if `receipt.result == "blocked"`: status `failed`, notify Ana, stop; else status `ready` (if not pre-approved) or `apply(p)`.
4. `apply(p)`: `await release.publish(p.release_id)` (FS-5 live stage: `published_rev=target_rev`, snapshot_all) **then** for each role in `p.ops`: `hub.patch(role, {rev: target_rev, base_rev: p.base_rev, role, ops, proposal_id, highlight: added_ids})` (clients with a different rev get a snapshot instead, per contract invariant 6); apply `spec_ops` to printables; `event spec_patch_applied`; status `applied`; `hub.control("proposal", …)`; decisions row.
5. `reject(village, pid, member)`: status `rejected`, decisions row, control frame, `detector.snooze(village, subject, pattern, hours=24)`.

### E. Builder patch (`core/builder/patch.py`, builder lane)
```python
async def patch_for_proposal(p: Proposal) -> dict[role, ops]:
    prompt = prompt_hub.get("village-builder", label="production")             # 10 s TTL cache; fallback prompts/builder_system.md
    for role in affected_roles(p):                                            # elder + helper for possible_fraud_pattern
        view = spec.views[role]
        with using_prompt_template(template=prompt.text, variables={...}, version=prompt.version_id):
            msg = llm().messages.create(model=SONNET, system=prompt.text, tools=[PATCH_APP_TOOL], tool_choice={"type":"tool","name":"patch_app"},
                                        messages=[{"role":"user","content": json.dumps({"mode":"patch","role":role,"current_view":view,"instruction":instruction_for(p, role)})}])
        ops = extract_tool_input(msg)["ops"]
        try: validate_patched(view, ops)                                       # fast-json-patch semantics in Python, pydantic view model, invariants 2–6
        except ValidationError as e:
            msg = repair_once(msg, e)                                          # tool_result is_error → second call
            ops = …; validate_patched(...)                                     # raises again → fallback
    return ops_by_role
# fallback: TEMPLATE_OPS["possible_fraud_pattern"] = proposal.schema.json example ops (+ spec_ops); decisions row "builder patch invalid; reviewed template used"
```
`instruction_for` embeds the evidence labels and the needed need id (`n_scam_calls`), and asks for ScamCheck on elder / IncidentCard on helper (the v1 prompt's Examples 5–6).

### F. Scam experiment (`evals/scam_experiment.py`)
```python
ax = ArizeClient()
rows = load_jsonl("data/datasets/scam_eval_set.jsonl")          # 50; is_scam True=30 / False=20
ds = ax.datasets.create_or_get(name="scam-eval-set", space=SPACE, examples=rows)
def task(dataset_row):                                           # traced CHAIN "scam_task"
    req = extraction.to_money_request(dataset_row["utterance"], lang, village_state)   # Claude Haiku → report_money_request args or {"kind":"none"}
    state = fixture_state(prior_money_request_days=7)
    dec = gate.decide(state, event_from(req), alloc=…)           # pure
    return json.dumps({"decision": dec.decision, "rule_id": dec.rule_id, "claimed_member_id": req.get("claimed_member_id")})
def decision_match(output, dataset_row): return EvaluationResult(score=float(json.loads(output)["decision"] == dataset_row["expected_decision"]), label=...)
def caught(output, dataset_row):       # scam rows only; benign rows → score None (skipped)
    return EvaluationResult(score=float(decision in {"verify_with_member","advise_do_not_send","deny"}))
def false_alarm(output, dataset_row):  # benign rows only
    return EvaluationResult(score=float(decision != "record"))
exp, df = ax.experiments.run(name=f"scam-gate-{ts}", dataset="scam-eval-set", space=SPACE, task=task, evaluators=[decision_match, caught, false_alarm], concurrency=4, timeout=300)
measured = {"scams": 30, "caught": int(df.caught.sum()), "benign": 20, "false_alarms": int(df.false_alarm.sum()), "errors": [...], "experiment_url": link, "run_at": ts}
write("var/evals/measured.json", measured); mirror.write_experiment(df)
```
Run v0 at ~11:30 against the gate alone (expected rows only); final at ~13:50 with extraction. Retries: 2 on 429; failing rows listed in `errors`.

### G. Builder prompt v1 → v2 (optional, `evals/builder_prompt_experiment.py`)
Dataset `village-descriptions` from `data/datasets/group_descriptions.jsonl`; task = `build_spec_only(description, prompt_label)`; evaluators `spec_valid` (jsonschema) + `spec_coverage` (money area → family view has an `IncidentCard` bound to `incidents:*`); run `builder-v1`, `builder-v2`; promote with `prompts.set_labels(v2, ["production"])` only if v2 wins and `spec_valid=100%`, **after** the Reyes village was built with v1 (so the Evolve patch is still what adds the card on stage). `POST /improve {mode: builder_prompt}` is the trigger.

### H. Ask-Village-why data sources
`core/services.ask_sources(village)` returns `{decisions: [...], facts: memory.facts_for(...), fact_history: memory.fact_history, session_labels: evals.session_labels(village), measured: evals.latest_measured(), receipts: release.get_receipts(village)}`; FS-3's prompt cites ids.

## Timing budget for the Rebuild beat (approve → patch on phones)

| Step | Budget | Note |
|---|---|---|
| approve route → status `verifying` | 0.3 s | |
| `patch_app` ×2 roles in parallel (Sonnet) | 5–10 s | adds already-cataloged components; validate 0.1 s |
| store rev 5 | 0.3 s | |
| FS-5 pipeline (warm) | ≈ 35–49 s | see FS-5 plan |
| `publish` + `patch` frames | 0.5 s | phones apply RFC 6902 locally |
| **Total** | **≈ 41–60 s** (`[MEASURE]`) | over 60 s → Control Room shows the 13:50 recorded `rel_reyes_r5` receipt; patch lands when the real run ends |

**Pre-verified fallback (13:50)**: run the full detector → approve path once on the demo village with `publish=False`, leaving `prop_reyes_scamcheck` at `ready` with `rel_reyes_r5` `in_progress` (first five stages passed). `reset_demo.sh` keeps that proposal and receipt. On stage, if the live rebuild is blocked or over budget, Ana's approve on the `ready` proposal applies in < 1 s from the pre-verified receipt. Both paths are honest: the receipt shown is real and timestamped.

## Live vs recorded
Live: detection (after today's call), Ana's yes, `patch_app`, the pipeline, phones changing. Recorded/pre-run: Oct 9 session eval, the experiment and `measured.json`, the 13:50 pre-verified proposal + receipt, the optional v1/v2 experiment.

## Environment variables
```
SURREAL_MEMORY_URL SURREAL_MEMORY_CONTEXT SURREAL_MEMORY_API_KEY   # + optional SURREAL_MEMORY_API_KEY_<AGENT>
MEMORY_OUTBOX_INTERVAL_S=2  MEMORY_HTTP_TIMEOUT_S=8  MEMORY_SCOPE_PREFIX=village
ARIZE_SPACE_ID ARIZE_API_KEY ARIZE_PROJECT_NAME=village  ARIZE_READ_TIMEOUT_S=5
EVALS_DIR=var/evals  EVALS_JUDGE_TIMEOUT_S=20  BEDROCK_SONNET_MODEL BEDROCK_HAIKU_MODEL ANTHROPIC_API_KEY
MONEY_PATTERN_MIN=2  MONEY_PATTERN_WINDOW_D=30  (read by the gate; the detector reads the same settings)
EVOLVE_VOICE=0            # 1 = call Ana with the proposal (village-caller)
PROMPT_HUB_PROMPT=village-builder  PROMPT_HUB_LABEL=production  PROMPT_HUB_TTL_S=10
VILLAGE_LAYERS=…,memory,evolve
```

## Risks and mitigations
- Agent Memory latency/outage → outbox; Fact view degraded mode; never on the safety path.
- Arize eval index lag → mirror is the primary read for the detector; Arize is the dashboard and the evidence link.
- Builder patch invalid → reviewed template ops; still goes through the gate.
- Rebuild over budget / blocked → pre-verified `ready` proposal from 13:50; receipts fallback on the strip.
- Judge rate limits during the experiment → concurrency 4, retries, errors listed.
