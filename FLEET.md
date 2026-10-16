# FLEET.md: running Village as a parallel subagent fleet (Oct 16)

The main session is the **orchestrator**: it owns `core/app.py`, merges, contracts and tags. Every other lane is a subagent in its **own git worktree + branch** (`lane/<name>`), owning only its folders, building against `contracts/` and `contracts/fixtures/`, and mocking anything that isn't ready yet. Nothing merges unless the acceptance check for the current version passes (`acceptance/`).

## Lanes and ownership
| Lane | Owns | Consumes | Produces |
|---|---|---|---|
| **core** (orchestrator) | `core/app.py`, `core/settings.py`, `core/ws_hub.py`, `core/live.py` (SurrealDB LIVE → hub), `core/routes/*`, `core/proxy.py`, `core/auth.py` | all contracts | the running API (`contracts/openapi.yaml`) |
| **gate** | `core/gate/` (rules, dose window SM, verification SM, clock) + `core/gate/tests/` | gate/verification/event schemas, `data/datasets/policy_cases.md` | `decide(state, event) -> Decision`, `step_verification(...)`, `step_dose_window(...)` (pure) |
| **kit** | `kit/` (renderer, catalog incl. ScamCheck/VerificationPrompt/IncidentCard/LifeAreas, WS client, themes, scan/join/prompt pages, Control Room `/control`) | village_spec, ws_messages, release, proposal schemas + fixtures; `design/*.dc.html` | built static app; Control Room |
| **voice** | `agents/` (ElevenLabs CLI configs, procedures), `core/voice/` (tool handlers calling `core.services`), outbound calls | voice_tools schema, `prompts/mom_line.md`, `prompts/escalation_call.md` | working phone line + outbound verification call |
| **builder** | `core/builder/`, `prompts/builder_system.md` usage, Prompt Hub fetch | village_spec schema, fixtures | `build_spec(description) -> VillageSpec` (streams blueprint events) |
| **release** | `core/release/` (daytona_svc, anchor_svc, receipts), `sandbox/` (village bundle template + floor tests) | release schema, kit build | receipts; Anchor QA runs; second family pre-generated |
| **evals** | `core/obs/` (tracing helpers, span decorators), `evals/` (scam eval experiment, release evals, session eval, evolve detector) | event + voice + release schemas, `data/datasets/scam_eval_set.jsonl` | Arize project wiring, the measured number, `detect_patterns(village) -> Proposal evidence` |
| **memory** | `core/memory/` (Agent Memory client: facts with provenance labels, history, uncertainty, asOf), Fact view endpoint | event schema | `remember_fact`, `fact_history`, `facts_for(village)` |
| **pitch** | `docs/` (DEVPOST.md per version, README.md, slides outline, video script) | LAYERS version map, measured numbers only | submission text always current |

`core/services.py` (owned by core) is the single seam other lanes call: `services.record_event`, `services.decide`, `services.start_verification`, `services.answer_verification`, `services.broadcast`. At 10:00 core commits a **stub** version of it that returns fixture-shaped data, so every lane can start immediately.

## Schedule: which lanes run when
| Window | Target | core | gate | kit | voice | builder | release | evals | memory | pitch |
|---|---|---|---|---|---|---|---|---|---|---|
| 10:00–11:00 | **V0** | app, WS hub, LIVE, scan route, stub services | **rules + both SMs + tests** | renderer, 3 views from fixture, scan page, WS client | agent configs, mock tool server vs contracts | — | Daytona snapshot/template build | tracing helpers; scam eval harness vs gate | — | README skeleton, DEVPOST V0 |
| 11:00–12:15 | **V1** | wire voice→services→gate; verification answer route; incident | integrate SMs; idempotency | VerificationPrompt, IncidentCard, countdown, Join/consent | **real number, tools, procedures, outbound call** | blueprint offline vs fixtures | bundle build + floor tests in sandbox; Anchor QA script vs local | spans on the voice path; **run scam experiment v0** | facts writer (calls, money requests) | DEVPOST V1 |
| 12:15–13:00 | **V2** | QR/join/auth; builder→broadcast; `POST /villages/{id}/ask` ("Ask Village why": Claude over the decisions log + memory sources, read-only, cites sources) | — (bugfix) | Control Room blueprint + three apps | harden, Spanish ASR checks | **integrate: sentence → spec** | proxy `/v/{id}`; receipts | builder spans; release evals draft | history + uncertainty | DEVPOST V2 |
| 13:00–13:40 | **V3** | receipts → control stream | — | receipts strip | — | pre-generate block village | **receipts end-to-end, caught+fixed build, Anchor live view** | release evals live | Fact view data | **draft video at V3** |
| 13:40–14:15 | **V4** | proposals: create/approve → patch | — | ScamCheck live patch, Fact view | — | patch_app for proposal | rebuild through gate | **session eval + detector; final number** | provenance links | DEVPOST V4 |
| 14:15–15:10 | Freeze | reset_demo.sh, run storyboard ×2 | | | | | | | | video, page, submit |

Max ~6 agents at once. Lanes marked "—" are paused or folded into another lane.

## Merge protocol
1. Each lane works in its own worktree: `git worktree add ../village-<lane> -b lane/<lane>`.
2. To merge, a lane reports: its diff summary, which acceptance checks it ran, and what it mocked.
3. The orchestrator merges in the order core → gate → kit → voice → builder → release → evals → memory, runs `acceptance/run.sh V<n>`, and tags when green.
4. **Contract changes:** only the orchestrator edits `contracts/`, bumps `contract_version`, and broadcasts it to all lanes.
5. **After 15:00,** no agent touches the demo path.

## Paste-ready lane prompt (template)
```
You are the <LANE> lane of the Village build (hackathon, today). Read CLAUDE.md, LAYERS.md, FLEET.md (your lane row), DECISIONS.md (D13 at the end), contracts/README.md and the schemas you consume.
Work ONLY in your worktree ../village-<lane> on branch lane/<lane>, and ONLY in the folders your lane owns. Build against contracts/ and contracts/fixtures/; mock anything not yet merged (never edit another lane's folder or contracts/; if a contract seems wrong, stop and tell the orchestrator).
Current target: <VERSION> (see the LAYERS.md version map). Deliver: <the lane's cell for this window from the schedule table>.
Definition of done: `acceptance/run.sh <VERSION> --lane <lane>` passes locally, plus your own unit tests. Then report: what's done, what's mocked, the exact commands you ran, open risks. Keep commits small; no secrets in code.
```

## Per-lane specifics to add to the template
- **gate:** pure functions only: no network, no LLM, no Agent Memory. Every rule in policy_cases.md becomes a test, plus the verification SM (pending → confirmed / denied / timeout) and the dose-window SM with FakeClock. CAS on `version`; idempotency on `(conversation_id, tool_call_id)`.
- **kit:** visual tokens and screens from `design/*.dc.html` (Fraunces / Atkinson Hyperlegible, sage #2F6B57, floor colors locked). The elder view follows the floor rules in DECISIONS D8. One WebSocket client; apply RFC 6902 patches; unknown component types render nothing.
- **voice:** ElevenLabs agents as code (`elevenlabs agents init/push`); tool URLs use `{{system_env__core_host}}`; verbatim `say` via a structured procedure (fallback: a prompt rule); `await_verification` is blocking with a 35 s timeout; outbound call only to members with consent; AI disclosure + family word first.
- **builder:** output only via the `render_app` / `patch_app` tool schemas; validate with pydantic; one repair, then fall back to `contracts/fixtures/reyes_spec.json`; stream blueprint events as they're found.
- **release:** Daytona snapshot `village-kit`; never call Core from the sandbox; Anchor Playwright at 390×844 drives the scan page (twice) and the VerificationPrompt; save the live view URL + recording; a deliberately broken bundle must be caught, then fixed.
- **evals:** compute evals in-process (Claude) and log them with `update_evaluations`; the scam experiment over `scam_eval_set.jsonl` produces "N/30 caught, M/20 false alarms". Report only measured numbers.
- **memory:** structured writes use `infer:"triples"`; provenance goes in labels (`src=call:<id>`, `secs=`, `agent=`, `village=`); full transcripts at post-call; never on the safety path.
- **pitch:** never invent numbers; write placeholders as `[MEASURE: …]` until evals reports them.
