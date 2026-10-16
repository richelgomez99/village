# Implementation Plan: FS-3 Founding & generation

**Spec:** `spec.md` · **Lane:** builder (owner), core (routes/services), kit (touchpoints only) · **Window:** 11:00–13:00 (V2), 13:00–13:40 block village (V3), patch_app ready for V4.

## Technical context
- Python 3.13, FastAPI, pydantic v2, `anthropic` SDK via `core.llm.llm()` (`AnthropicBedrockMantle` Sonnet 5.5 → Sonnet 5 → `Anthropic()`), no Converse, no structured outputs on Mantle (tools + validation instead).
- Tools: `extract_blueprint` (new, builder-owned), `render_app`, `patch_app` (verbatim from `prompts/builder_system.md`), `cite_answer` (ask). `tool_choice: auto` + "call X exactly once" instruction (forced tool choice 400s on 5.5; `strict` is an open item).
- Tracing: `arize-otel` register, `AnthropicInstrumentor`, OITracer decorators from `core/obs` (evals lane; mocked with a no-op tracer until merged).
- Prompt Hub: `ax.prompts.get(prompt="village-builder", label="production")`, 10 s TTL; local file fallback.
- Storage: through `core.services` only (SurrealDB `village`, `member`, `decision`, `spec_rev`, `invite`).

## Project structure
```
core/builder/
  __init__.py        found(), build_spec(), patch(), ask()  (public surface used by core routes)
  founding.py        FoundingSession state machine: listening → clarifying → drafting → draft → active
  blueprint.py       extract_blueprint call, streamed partial-JSON parser → control frames
  render.py          per-role render_app in parallel, merge, deadline guard
  patch.py           patch_app interface (FS-6 consumer); apply-to-copy + validate
  validate.py        pydantic VillageSpec/View (discriminated union on type), invariants 1–5, error formatter
  templates.py       fixture-based fallback per role/kind, name remap
  prompts.py         Prompt Hub fetch (TTL 10 s) + local fallback; returns {text, version_id, source}
  tools.py           JSON tool schemas (render_app/patch_app loaded from builder_system.md; extract_blueprint, cite_answer inline)
  mapping.py         builder↔contract role & profile mapping (family→coordinator/helper; memory/tech_comfort enums)
  decisions.py       decision-log entry builders (why this channel / role / contact / template)
  ask.py             Ask Village why: gather material → Claude → validate citations → redact (HTTP + chat entry points)
  chat_intent.py     V4: classify "@Village" text as why|change|other (Haiku, effort low) → ask() or patch()
  spans.py           thin wrappers over core.obs (AGENT/CHAIN/EVALUATOR + graph.node attrs), no-op fallback
  tests/             unit tests with a fake LLM (recorded tool outputs) and schema validation
core/routes/villages.py   (core lane) POST /villages, GET /villages/{id}, POST …/answers, …/draft, …/activate, …/ask, GET …/qr
core/chat.py              (core lane) messages store, Village posts from ledger events, WS `chat` fan-out, POST/GET …/messages
scripts/build_village.py  quickstart runner (description → blueprint + 3 specs → validate)
data/builder/             recorded blueprint streams + generated block village (lane-owned outputs)
```

## Founding flow
1. **Entry.** Voice: `POST /tools/create_village` body = `req_create_village` (conversation_id, caller_id, call_secs, utterance, description, members[], needs[], medications_mentioned, language). Text: `POST /villages` (description, members?, needs?, language, mode). Both normalise to `FoundingInput` and call `builder.found(input, village_id)`. The voice route returns within 2 s (`decision: allow`, `say` = fixed "building" line, `data.village_id`) and continues in a background task; the text route returns `202`.
2. **Blueprint (≤8 s target).** One streamed call, Sonnet 5.5 `output_config.effort: low` (Haiku 5.5 if Sonnet TTFT > 3 s in `smoke/01_llm.py`), tool `extract_blueprint`. Core reads `input_json_delta` events, keeps a buffer, parses with `pydantic_core.from_json(buf, allow_partial=True)`, and each time a new complete item appears in `people`, `needs`, `life_areas`, `rules`, `kind`, `questions` it emits one `control{kind: reasoning}` frame (`kind: note` for findings, `decision` for choices such as "Carmen → phone_line + lid_qr: tech_comfort phone"). Also a `control{kind: counter}` `people_found`. The frame texts are plain words (LAYERS "on stage, plain words"). Profiles are typed per contract (`capability_profile`), with `evidence[]` pointing at `source{kind: call|app, ref, secs|quote}`.
3. **Clarify.** If `questions` non-empty and the channel is text, the session pauses in `clarifying` (`control` note with the question); `POST /villages/{id}/answers` appends the answer, re-runs the blueprint with `prior_blueprint` so ids stay stable (`needs[].origin = follow_up`). Voice never reaches this state (the agent asks before the webhook). A 30 s wait with no answer proceeds anyway.
4. **Render (parallel).** `asyncio.gather` of one `render_app` call per role in `views_for(kind)`: care → `elder` (members with `view: elder`), `coordinator` (primary), `helper`; block → `coordinator` (primary), `resident`, `volunteer`. Each call's user message is the prompt's INPUT JSON (role, primary, members_in_role, village = normalised input + blueprint). Each call is its own task with `asyncio.wait_for(…, 45 s)`; the whole render has a 60 s deadline. Missing/failed roles get the template.
5. **Validate → repair → template.** `validate.py` builds the merged spec and runs the pydantic model + invariants 1–5 from `contracts/README.md`. Errors are formatted as a short numbered list (≤12 lines) and sent back as `tool_result{is_error: true}` once. The second failure (or any exception) selects `templates.view(kind, role)`: the fixture view with member ids/names remapped where the input matches (`m_carmen` ↔ care recipient, etc.). Every outcome writes a decision row (`validated`, `repaired`, `template`).
6. **Draft.** `services.store_spec(village_id, spec, status="draft")` → `rev 1`; `services.broadcast_control(snapshot)` to the control socket. Member sockets get nothing until activation.
7. **Edit.** `POST /villages/{id}/draft {ops}`: RFC 6902 over the whole spec, allowed paths `/village/name|theme/*`, `/blueprint/people/<i>/short_name|role|life_areas`, `/channels/<id>`, `/blueprint/life_areas/<i>/trusted_contacts`, `/blueprint/rules`, `/views/<role>/elements/<id>/props/<prop>` (labels/titles only). Re-validate; floor invariants reject edits that break them; `rev++`.
8. **Activate.** `POST /villages/{id}/activate`: `status: active`, `published_rev = rev`, `services.mint_invites()` (one `inv_*` per member with a non-null view; hashed token at rest), printables get `token_ref`s, decision row `village_activated`, response = join list. Then FS-4 phones can connect; FS-5 may build.

## Latency budget (targets; all `[MEASURE]` via `smoke/01_llm.py` and `scripts/build_village.py --time`)
| Step | Target | Guard |
|---|---|---|
| Webhook ack | ≤2 s | fixed `say`, background task |
| First reasoning frame | ≤3 s | stream, effort low |
| Blueprint complete | ≤8 s | 12 s wait_for → proceed with partial blueprint + question |
| 3 renders in parallel | ≤30 s (Sonnet 5.5, ~2–4k tokens each) | 45 s per role, 60 s total |
| Repair round | +15 s | once per role |
| Template fallback | ≤1 s | always available |
| Ask Village why | ≤8 s | Sonnet 5.5 effort low; material capped at 60 rows |

Prompt caching: `cache_control: ephemeral` on the system block (≈12k tokens of prompt + examples) so the three parallel renders share one cache write; check `usage.cache_read_input_tokens` in the quickstart output.

## Prompt Hub + fallback
`prompts.get_builder_prompt()` → `{text, version_id, source: hub|local}`; TTL 10 s on monotonic time (not the demo Clock). Hub failure (network, BETA warning, non-string content) → local file, logged once per minute. The system block = SYSTEM PROMPT + EXAMPLES verbatim; tools = JSON blocks parsed from the same file by a tiny fence parser with a unit test that pins their names. `using_prompt_template(template=text, variables={role, village_id}, version=version_id or "local")` wraps each `messages.create`.

## LLM factory usage
`client, model = core.llm.llm(tier="sonnet"|"haiku")`; on `403/ExpiredToken` the factory rebuilds the client and falls back (core-owned). The builder passes `max_tokens=8000` (render), `3000` (blueprint), `1500` (ask), `output_config={"effort": "low"}` for blueprint/ask and the default for render. `VILLAGE_LLM=off` makes `llm()` raise `LLMUnavailable`, which the builder maps straight to the template path.

## Streaming of blueprint events
WS contract today allows only `control{kind: reasoning, payload{source, kind, text, trace_id, village}}` and `counter`. V2 ships with text frames (one per finding) plus a full control `snapshot` when the draft exists, which lets the Control Room draw the blueprint from `spec.blueprint`. A structured `control{kind: blueprint}` frame is proposed in `contracts/README.md`; if the orchestrator adds it, `blueprint.py` emits both.

## Ask Village why
Material: `services.decisions_for(village, limit=60)` (newest first), `services.facts_for(village)` (memory lane; until merged, derived from `contracts/fixtures/events_reyes_seed.json`), `services.events_for(village, kinds=[consent, verification_*, escalation, incident, pattern])`. Each row is rendered as `[id] at · actor · text · source`. System prompt: answer only from the material, cite ids in `citations[]`, say "no record" otherwise, never output the family word, phone numbers or account details (regex redaction on output as a second line of defence). Tool `cite_answer{answer, citations[{id, kind}]}`; citations whose id is not in the material are dropped and counted in the span (`dropped_citations`). Read-only: no ledger write; one AGENT span `ask_village_why` with the question as input.

## Village chat (D16): component, composer, message handling
- **Component (kit, FS-4):** `VillageChat` props `{bind: "chat:village", title?, show_composer (bool), mention_label ("@Village"), allow_approve (bool; leader only)}`. Renders `[message]` newest at the bottom; `kind` picks the row style: `chat` (member bubble), `incident` (source chip from `refs[event]`), `proposal` (inline Approve / Not now → existing `approve_proposal` / `reject_proposal` actions), `receipt` (release strip line), `nudge` ("Marco, you're on tonight"), `answer` (Village reply with citation chips). Unknown `kind` renders as plain text.
- **Builder insertion (`render.py` → `mapping.ensure_chat(view, role)`):** after merge, for every view whose theme is `family` or `dashboard`, insert element `chat: {type: VillageChat, props: {bind: "chat:village", show_composer: true, allow_approve: role == "coordinator"}}` at the end of `s.children` if no `VillageChat` exists; `needs_served.chat = [n_safety]` plus the money/people need ids present. Validation: forbidden in `elder` views; at most one per view. The template views get the same insertion so fixtures stay untouched.
- **Composer:** text + "@Village" affordance (prefixes the text and sets `mention: village`). Sends `POST /villages/{id}/messages` (member token). Never offers attachments, money or phone fields.
- **Message handling (core `core/chat.py`, FS-3 core part):** `post_message(village, author, text, mention)` → store (`msg_*`, `source{kind: app, ref: member}`) → `services.broadcast_chat()` to sockets whose role view is non-elder. Village posts come from one subscriber on the ledger: `incident` → `kind: incident` (text = gate `say`/incident summary in the viewer's lang), `spec_patch_proposed` → `proposal`, `release` → `receipt`, `reminder|escalation` on the rota → `nudge`. If `mention == village`: V2 → `builder.ask(question=text, channel="chat")` → `kind: answer`, `reply_to`; V4 → `classify(text)` (Haiku, effort low; labels `why|change|other`) → `change` → `builder.patch()` per affected role → Proposal row → `kind: proposal` message. Every Village post has `refs[]`; a post with no refs is a bug (assert in tests).
- **Binding:** `chat:village` resolves to the last 50 messages in `snapshot.data`; later messages arrive only as WS `chat` frames (not `patch`), so the view spec never changes when people talk.

## Demo clock considerations
`Clock.now()` stamps `consent.recorded_on`, decision rows, `founding_session.created_at` and the rota-derived `on_duty`/`backup` edges (Thursday → Marco, Friday → Ana). Invite expiry and the Prompt Hub TTL use wall time. The quickstart prints both clocks so a warped Thursday demo produces "on duty: Marco" edges consistently with FS-1's gate.

## Live vs pre-generated per version
| Version | Live on stage | Pre-generated / replayed |
|---|---|---|
| V2 | Reyes founding by voice (text as fallback), blueprint stream, 3 renders, draft, activate, join, `/ask` | `mode: fixture` replays `reyes_spec.json` + a recorded reasoning stream (`data/builder/reyes_reasoning.jsonl`) if the LLM is off |
| V3 | the 15 s reveal: `GET /villages/v_w147` + its build time and trace id | block village generated from `block_blackout.json` during 13:00–13:40 and stored (`data/builder/block_spec.generated.json`), validated against the schema and diffed against `block_spec.json` |
| V4 | nothing new from FS-3; FS-6 calls `builder.patch()` | — |

## Anyone fast path (optional; cut by D13)
`mode: fast`: skip follow-ups, `custom_component` forbidden, render roles in parallel with Haiku 5.5, no FS-5 build (catalog-only views render in the already-built kit), activation auto-mints invites. Target ≤40 s to a phone. The code path is the same `found()` with `FoundingOptions(fast=True)`; no task is scheduled for it.

## Validation pipeline (what `validate.py` checks)
1. JSON Schema shape (pydantic model mirrors `village_spec.schema.json`; `contracts/validate.py` is the oracle in tests).
2. Invariants: channels ⇔ people; `app:<role>` = view; every child exists, referenced once, acyclic; non-layout elements have `needs_served` ⊆ needs ∪ {n_safety}; elder ≤3 BigButtons + 911 card + confirm on danger + no med names; member refs real; `source_span` inside the text; life-area modules exist.
3. Safety text scan: no dose numbers/advice words in labels, no family word, no phone numbers except input/911/988/Poison Control.
4. Output: `ValidationReport{ok, errors[], warnings[]}`; errors become the repair message.

## Risks & mitigations
Sonnet 5.5 gated (403) → Sonnet 5 fallback in `llm()`; render > 45 s → template + decision row; Prompt Hub BETA breaks → local prompt; `ax` SDK import cost → lazy import in `prompts.py`; three parallel calls hit Bedrock TPM → sequential fallback flag `BUILDER_PARALLEL=0`.
