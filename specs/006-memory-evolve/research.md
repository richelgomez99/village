# Research: Memory & evolve (FS-6)

Sources read: `research/surrealdb.md` (Agent Memory write paths, supersession, history, asOf, uncertainty, scopes, no push), `research/arize-bedrock.md` (update_evaluations, datasets/experiments, Prompt Hub, improve loop, index lag), `research/innovation-scout.md` (#1 Gauntlet, #3 "what did Mom know when", #5 memory-driven evolution), ARCHITECTURE-VALIDATION.md edges 13–15, `prompts/builder_system.md`, smoke 06/07. Marks: ✅ verified · 🟡 docs/SDK · 🔴 untested.

## Decisions already made (do not reopen)
| Decision | Source | Consequence |
|---|---|---|
| Agent Memory via outbox; never on the safety path; Core is the only writer | D5, ARCH-VAL edge 14, FLEET memory lane | `am_outbox` table + worker; gate/voice never import `core.memory` |
| Provenance in labels (`src=`, `secs=`, `agent=`, `village=`) because triples can't carry `source.ref/span` | `research/surrealdb.md` §1, CLAUDE.md rule 5 | `conventions.labels_for(event)` |
| Dose changes written as triples on the same key → clean supersession; transcripts via `infer: full` for spans | `research/surrealdb.md` §2–3 | two keys families: operational keys vs LLM-extracted keys |
| Evals in-process, logged with `update_evaluations`, mirror first | ARCH-VAL §4.4 | detector reads mirror, links Arize |
| Rebuild trigger conversational + self-detected; Village raises it, Ana says yes | D15 addendum | approve on `proposed` starts verification |
| Scam eval set as an Arize experiment → "N/30, M/20" | D13 | `measured.json` is the single source |
| Builder v1 deliberately weak; the Evolve patch adds the scam card on stage | D9, `builder_system.md` header | v2 promotion only after the Reyes build |
| No Agent Memory push → Core fans out | `research/surrealdb.md` §5 | Fact view polls/reads on demand; WS carries ledger-derived changes |

## Open items

| # | Question | Status | Resolved by | Fallback if bad |
|---|---|---|---|---|
| R-01 | Exact request shapes: triple entry `{"entity":{type,name},"key","value"}`, `/facts/batch` `messages[]` fields (`role`, `content`, timestamps?), `GET /uncertainty` list field name, `/lookup` subject format | 🟡 (marked VERIFY in smoke 06) | `uv run smoke/06_memory.py --keep` tonight; T002 pins shapes in `client.py` with recorded fixtures | Keep raw dicts configurable in `conventions.py`; tests use recorded responses |
| R-02 | Triples write latency p50/p95 on the Sandbox plan; `full` extraction latency for a 2-minute transcript; token cost of triples | 🟡 | smoke 06 latency table (T003 records `[MEASURE]`) | Outbox absorbs it; ingestion can be deferred to idle time |
| R-03 | Per-agent keys/principals on the Sandbox plan (how many keys; can the data-plane key create scopes?) | 🔴 | smoke 06 §1 (`scopes.register` 403?) + Studio check | One key, `agent=` labels for attribution; register scopes in Studio once |
| R-04 | Do a turn-derived fact and an upsert on the **same** key create a cross-kind uncertainty (we rely on it for the Fact view uncertainty card)? Does `resolve` supersede both? | 🟡 | smoke 06 §7–8 | Seed the uncertainty from a document upload (pharmacy label) as the smoke does |
| R-05 | `asOf` semantics on attributes written with backdated `observed_at` (known time vs valid time) — does `asOf=2026-10-02` return 5 mg? | 🟡 | smoke 06 §6 | Fact view computes `as_of` from the ledger mirror (`valid_from/until` from `med_change`) |
| R-06 | `update_evaluations` → visibility delay and `spans.list(filter="eval.possible_fraud.label = 'possible_fraud'")` grammar | 🟡 | FS-5 T014 (smoke 07 extension) | Mirror-first detector (already the design) |
| R-07 | `experiments.run` with a task that calls Bedrock at concurrency 4: 429 rate, total time for 50 rows; does the experiment project show per-row traces? | 🔴 | T012 v0 run at ~11:30 (gate only) then T013 full run | Concurrency 2; the numbers still come from the run |
| R-08 | Root span id of a call session available to the eval job (FS-2 must expose it; survives restart?) | 🔴 | T006 with FS-2's tracing helper; `call_session.root_span_id` | Log the eval on a fresh EVALUATOR span with `session.id` and `metadata.conversation_id`; evidence `trace` ref = that trace |
| R-09 | Prompt Hub BETA SDK end to end (`prompts.get(label=)`, `create_version`, `set_labels`) and that `messages[].content` is a plain string | 🟡 | T016 (optional) | `prompts/builder_system.md` from disk; v2 experiment skipped (Q&A only) |
| R-10 | `patch_app` on Mantle with `tool_choice: {"type":"tool"}` — research says forced tool choice 400s on 5.5 models | 🟡 | builder lane's first `render_app` run (FS-3) | `tool_choice: auto` + instruction "call patch_app"; validate; template fallback |
| R-11 | Voice path for the proposal (village-caller procedure + `answer_proposal` tool) — time to add safely | 🔴 | voice lane after V2; `EVOLVE_VOICE=0` default | Tap approval only; the line is spoken from the Control Room narration |
| R-12 | Phones applying a `patch` frame with `highlight` (kit `fast-json-patch` path) when the client rev equals `base_rev`; snapshot fallback on mismatch | 🟡 (spine test ✅ for events) | smoke 10 `10_spine_local.py` + kit fake WS with the proposal example | `snapshot_all` after publish (always sent anyway) |

## Items explicitly out of scope
- Agent Memory `/reflect`-driven proposals (innovation #5 "reflect"): the detector is rule + eval based today; reflect is a roadmap line.
- Daytona fork for "try the variant": FS-5 builds a rev; no fork.
- Arize Signal as the detector: cadence 3 h; enable in the background only.
- `/forget` (right to be forgotten): P3 (US-28).
