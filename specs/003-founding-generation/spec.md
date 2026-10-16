# Feature Specification: FS-3 Founding & generation

**Branch:** `lane/builder` (+ `core` routes, kit touchpoints) · **Version:** V2 (second village: V3; chat change requests: V4) · **Status:** draft · **Sources:** PRODUCT.md (FS-3, US-01..04, US-17b, US-18, US-19), EXPERIENCE.md (founding as a conversation, roles, phase-1 governance), DECISIONS.md (D8, D9, D10, D13–D15 + addendum, D16 village chat), LAYERS.md (V2, "Ask Village why"), FLEET.md (builder lane), `prompts/builder_system.md`, `prompts/setup_agent.md`, `contracts/`.

## Summary
A founder (Ana) talks to Village, by voice (ElevenLabs setup agent) or by typing in a text box. Village asks at most 1–2 follow-ups, extracts a **blueprint** (people, capability profiles, life areas, needs, rules, group type) and streams it to the Control Room as it is found, then builds one app per role from the fixed catalog (elder / coordinator / helper, in parallel). The result is a **draft village** the founder reviews and edits. Nothing leaves the building until she taps **Invite everyone** (`activate`), which mints a join invite + QR per member; members join with consent and land in their own app. A leader or a judge can ask **"Why did you…?"** and get an answer that cites the decisions log and memory facts. The same engine, fed the blackout-block description, produces a different village (V3 reveal). Kit rendering (FS-4), the release pipeline (FS-5) and memory writes (FS-6) are out of scope; `patch_app` is built here as an interface for FS-6.

## User scenarios & testing

### S1 Founding by voice (US-01)
Ana calls the Setup agent. She tells the story in her own words; the agent asks "Anyone else who helps?" and "What does she like to be called?", summarises in one sentence, and on "yes" calls the `create_village` webhook (`POST /tools/create_village`, `X-Village-Secret`). Core answers within 2 s with `{decision: allow, say: "Building it now…", data: {village_id, plan}}`; the Control Room starts showing the blueprint assembling.
*Test:* replay the recorded webhook body from `contracts/fixtures` → 200 within 2 s; `control{kind: reasoning}` frames arrive on the control socket within 8 s; `GET /villages/{id}` returns a spec with `status: draft`.

### S2 Founding by text (fallback, ARCHITECTURE-VALIDATION §4.6)
Ana types the same story into the founding box on the Control Room / founder page and presses Build. `POST /villages {description, language}` → same builder path, same frames, same draft.
*Test:* `POST /villages` with Ana's sentence (D13) → `202 {village_id, ws_url}`; draft ready (3 views) within 45 s or the template fallback is in place within 60 s.

### S3 A follow-up question is asked (D15 addendum)
The description is thin (`gd_20`): the blueprint step returns `needs_clarification` (≤2 questions). By voice the agent asks them before the webhook. By text, Core stores the partial blueprint, sends `control{kind: reasoning, kind: note, text: "Q: Who is in the group?"}`, and the box shows the question; the answer goes to `POST /villages/{id}/answers` and the build resumes with the answer appended (`needs[].origin = follow_up`).
*Test:* `gd_20` → no invented people (`blueprint.people` ⊆ named/role-labelled only), ≤2 questions, no views rendered until answered or skipped.

### S4 Draft edit (US-02)
The draft shows people (name, relation, role, channels), life areas, rules and the three views. Ana renames "Carmen" → short name "Mamá", turns Lucía's `outbound_calls` channel off and sets Marco as a money trusted contact. Each edit is a bounded RFC 6902 op on the draft (`POST /villages/{id}/draft`), re-validated; the spec `rev` increments; the control snapshot refreshes.
*Test:* ops on allowed paths pass; an op that removes the 911 card or adds a 4th elder BigButton is rejected `422` with the invariant name; no event, invite or call is produced while `status: draft`.

### S5 Activate (US-03; principle II)
Ana taps **Invite everyone**. `POST /villages/{id}/activate` (leader's member token or control token) flips `status: active`, writes a `village_activated` decision-log row, mints one invite per member with a non-null view (and a lid/fridge print pack for `lid_qr` members), and returns `[{member_id, kind: join, url, svg}]`. Only after this may invites, outbound calls or verification prompts exist.
*Test:* `GET /villages/{id}/qr?kind=join` before activation → `409 conflict`; after → one join URL per app member; `activate` twice → `409`.

### S6 Join with consent (US-04, D11)
A judge scans Marco's join QR → `/join?i=<invite>` → first name, mobile, AI-call consent checkbox → `POST /auth/redeem` → `{member_token, app_url, ws_url, consent_event}`; the consent ledger row (`kind: consent`) carries `text_version`; `blueprint.people[m_marco].consent.ai_calls` becomes true; the phone opens the helper view. A second redeem of the same invite → `409`.
*Test:* redeem → consent event validates; `R-VERIFY-CONSENT` params now include `m_marco`; the control counter `phones_connected` increments on the WS hello.

### S7 Invalid spec repaired (principle V)
The elder render returns 4 BigButtons and a `needs_served` id not in needs. Core's pydantic validation fails; the errors go back as a `tool_result{is_error: true}`; the model's second `render_app` passes. A `control{reasoning, decision}` line says "elder view repaired: 4 BigButtons → 3; n_turnss unknown".
*Test:* fault-injected mock LLM (first answer invalid) → final spec valid; `builder_run.roles.elder.status = repaired`; exactly 2 LLM calls for that role.

### S8 LLM down → template fallback (principle VII)
Bedrock 403 and the Anthropic key missing, or the repair also fails, or the 60 s deadline passes. Core assembles the village from `contracts/fixtures/reyes_spec.json` (care) or `block_spec.json` (block), remapping names from the input where they match, marks `builder_run.roles.*.status = template`, logs a decision "used template: <reason>", and still produces a draft. The demo never shows a blank screen.
*Test:* `VILLAGE_LLM=off` → draft within 3 s, spec validates, reasoning panel shows "template".

### S9 Ask Village why with citations (US-18)
A judge types "Why did you call Marco and not Lucía?" in the Control Room box. `POST /villages/{id}/ask {question}` → Claude reads the village's decisions log + memory facts + ledger rows (read-only) → `{answer, citations: [{kind: decision|fact|event, id, label, at, source}]}`. Every citation id exists in the material supplied; the answer never contains the family word, phone numbers or account details; unanswerable → "I don't have a record of that" with no citation.
*Test:* seeded Reyes log → answer cites `R-VERIFY-CONSENT` decision + Lucía's `consent.ai_calls=false` fact; hallucinated ids are stripped and counted; a question about the family word returns a refusal line.

### S10 Village chat: Village posts an incident (D16, US-17b)
After activation the coordinator and helper views contain a `VillageChat` feed (never the elder view; Carmen's chat is the phone line). When the gate opens an incident (`event.kind: incident`), Core posts a `message{author: village, kind: incident, text, refs: [{kind: event, id}]}` and fans it out as WS `chat`; the feed shows the source chip (call + second) on tap.
*Test:* seed `events_reyes_seed.json` incident → Ana's and Marco's sockets receive one `chat` frame with `kind: incident` and a `refs[0].kind == "event"`; Carmen's socket receives nothing.

### S11 Village chat: a member posts
Marco types "I'll take Thursday" → `POST /villages/{id}/messages {text}` (member token) → stored with `source{kind: app, ref: m_marco}` → WS `chat` to every member socket of that village except elder views. No gate decision is involved (plain chat is not consequential); the composer never sends money/account details anywhere.
*Test:* message appears on Ana's socket ≤1 s `[MEASURE]`; `GET /villages/{id}/messages?after=` returns it with its author and `at`.

### S12 Village chat: "@Village why…" → answer with sources (US-18 in chat)
Ana writes "@Village why did you call Marco and not Lucía?". The composer's "@Village" affordance marks the message `mention: village`; Core stores the member's message, routes the text to the same `builder.ask()` as S9, and posts `message{author: village, kind: answer, text, refs: citations}` as a reply (`reply_to` = Ana's message id). Citations render as source chips.
*Test:* reply arrives with ≥1 ref of kind `decision|fact|event`; the answer text passed the redaction scan; one AGENT span `ask_village_why` with `metadata.channel = chat`.

### S13 Village chat: proposal approved inline (V4 touchpoint)
Village posts `kind: proposal` with `refs: [{kind: proposal, id}]`; the feed renders Approve / Not now for the leader only. Approve → the existing `approve_proposal` WS action → FS-6 pipeline; the message updates to "approved by Ana" when `spec_patch_applied` lands. "@Village, Marco switched to days" (V4) is a change request: Core routes it to `builder.patch()` → Proposal → the same inline card.
*Test (V4):* leader approves inline → `/villages/{id}/proposals/{pid}/approve` called once; non-leaders see no buttons.

### Edge cases
- Description names nobody (`gd_20`): minimal draft + questions, never invented members.
- Covert tracking / dose calculation (`gd_18`, `gd_19`): `refusals[]` with `P-CO-02` / `P-MA-01`; build the consent-based alternative only.
- Two parallel role calls disagree on needs: merge by id, primary call wins text/priority; non-primary extra needs are kept only if cited by that view.
- Builder emits a type outside the catalog (`MapPin`): pydantic rejects → repair → template. Unknown types never reach a phone.
- Prompt Hub unreachable or returns a non-string message: use `prompts/builder_system.md`, record `prompt_source: local`.
- Founder re-describes after activation: out of scope (P2 US-23); return `409` with "village is active; changes go through proposals".
- Spanish description: blueprint `description.lang = es`; views still use each person's `profile.lang`.
- Demo clock warped to Thursday: rota-derived `on_duty` edges and `consent.recorded_on` use the shared `Clock`, not wall time.
- Member with `tech_comfort: phone` and `view: null` (Mrs. Alvarez): channels `phone_line` only; no invite minted; counted in printables only if the village has lid stickers.

## Requirements
- **FR-001** Village accepts a founding description by voice (setup agent → `POST /tools/create_village`) and by text (`POST /villages`); both call the same `builder.found()` and produce the same artifacts.
- **FR-002** The blueprint step extracts `people` (id, name, relation, role, view, profile, consent=null unless stated), `edges`, `needs` (with `source_span` into the verbatim text or `origin: follow_up`), `rules`, `life_areas`, and `village.kind` (care | block). It never invents names, phone numbers or diagnoses.
- **FR-003** Blueprint findings stream to the Control Room as `control{kind: reasoning}` frames (`source: builder`, `kind: plan|decision|note`, text ≤400) in the order found; first frame ≤3 s after the request, blueprint complete ≤8 s (D9) `[MEASURE]`.
- **FR-004** At most two follow-up questions per founding; by voice they are asked by the agent, by text they are shown and answered via `POST /villages/{id}/answers`. Unanswered questions do not block a draft (the builder proceeds with what it has and lists them in `needs_clarification`).
- **FR-005** Views are rendered with one `render_app` call per role, in parallel; exactly one call is `primary`; Core merges into one VillageSpec (`views[role]`, needs by id, village-level fields from the primary).
- **FR-006** Every render output is validated by Core's pydantic model (per-type props, graph acyclic and reachable from `s`, `needs_served` refs, elder limits, member refs, catalog-only types). On failure: one repair round with `tool_result{is_error}`; then the template view for that role from the fixtures.
- **FR-007** A draft village has `status: draft`; no invite, outbound call, verification prompt or printable token exists for a draft. `activate` requires the founder/leader and is idempotent (second call `409`).
- **FR-008** `activate` mints one invite per member with a non-null view (`kind: join`), returns URL + SVG per member, and writes a `village_activated` decisions-log row. Invites are single-use, bound to one member, and expire after 24 h (wall clock).
- **FR-009** Join (`POST /auth/redeem`) records consent with provenance (`source{kind: app, ref: invite id}`), updates `blueprint.people[].consent`, and the gate's `R-VERIFY-CONSENT` params reflect it on the next decision.
- **FR-010** The builder system prompt is fetched from Arize Prompt Hub (`village-builder`, label `production`) with a 10 s TTL and falls back to `prompts/builder_system.md`; every builder LLM span carries `using_prompt_template(version=…)` and `prompt_source`.
- **FR-011** `patch_app` is callable as `builder.patch(village, role, instruction, current_view) -> PatchResult{ops, needs_added, reason, plan}` with the same validate/repair pipeline, applied to a copy and never broadcast by the builder (FS-6 does).
- **FR-012** `POST /villages/{id}/ask` answers in the asker's language from the decisions log, memory facts and ledger rows of that village only, cites by id, writes nothing except a trace, strips citations whose ids were not supplied, and never reveals the family word, phone numbers or account details.
- **FR-013** Every founding writes decisions-log rows explaining channel, role, trusted-contact and consent choices, plus repair/template events, each with `source{kind: system, ref: builder}` and the Arize `trace_id`.
- **FR-014** The block village is generated by the same pipeline from `data/villages/block_blackout.json`'s spoken description (V3, pre-generated), stored with its build time and trace id, and differs from Reyes in `kind`, roles, modules and rules.
- **FR-015** Builder spans: AGENT `builder.found` (graph.node.id `builder`, parent `core`), CHAIN `builder.blueprint`, LLM spans per role (auto-instrumented), EVALUATOR `builder.validate`, AGENT `ask_village_why`; all under `session.id = village-<id>`, `user.id = <founder>`.
- **FR-016** Hard latency guard: a render that has not finished by 60 s `[MEASURE]` is cancelled and replaced by the template for the missing roles; the draft is always produced.
- **FR-018** Every non-elder role view of an active village contains exactly one `VillageChat` element (`bind: chat:village`); the builder inserts it deterministically after rendering if the model did not (config, not prompt), and validation rejects it in elder views. D16: the chat replaces IncidentCard/Proposal/DecisionsLog cards in member apps; those stay for the Control Room.
- **FR-019** Chat messages are stored with provenance (`author`, `source`, `refs[]`), fanned out as WS `chat` to member sockets of non-elder views only, and never pass through the LLM unless they carry `mention: village`. Village-authored messages come only from Core events (incident, proposal, receipt, nudge) or from `builder.ask()` (`answer`); their text for incidents/receipts is the gate/release text, never generated.
- **FR-020** "@Village" messages route to `builder.ask()` (read-only, cited) in V2; in V4 a message classified as a change request routes to `builder.patch()` and produces a Proposal, never a direct change. Classification errs toward "answer": when unsure, Village answers and offers "Want me to propose a change?".
- **FR-017 (optional, cut)** Fast path `mode: fast` (D9 Anyone): catalog-only, no custom component, no follow-ups; target ≤40 s to a usable app. Documented, not scheduled.

## Key entities
VillageSpec (contract), FoundingSession, BuilderRun, Invite, DecisionLogEntry, AskAnswer, Message (chat) — see `data-model.md`.

## Constitution check
- **I** The builder decides what to build; it never writes ledger rows directly, never calls anyone; invites/calls are gated on `status: active` (FR-007) by code in `core/gate` (R-CONSENT), not by the prompt.
- **II** Nothing consequential without the right person: the founder activates (S5), each member consents at join (S6), Carmen's `ai_calls` stays `null` until asked (P2). Draft edits are the leader's. ✅
- **III** Needs keep `source_span`; profiles keep `evidence[]`; consent rows carry `recorded_by`; decision rows carry `trace_id`; `ask` cites ids only. ✅
- **IV** Nothing generated reaches a phone untested: FS-3 outputs only validated catalog specs; the build pack is FS-5's. ✅
- **V** Catalog-only, pydantic on the server (FR-006), unknown types rejected before the kit sees them; elder floor invariants are enforced in validation and cannot be edited away in S4; safety lines are never generated (the builder only picks `say_key`-driven components). ✅
- **VI** No lane edits `contracts/`; the additions this feature needs are listed in `contracts/README.md` for the orchestrator. Builder code calls `core.services` only. ✅
- **VII** Template fallback and the 60 s guard mean V2 is always pitchable; `mode: fixture` replays the Reyes spec if the model is off. ✅
- **VIII** Every step is a span; decisions are user-readable in the log and through `/ask`; latency numbers are `[MEASURE]` until the smoke scripts run. ✅
- **IX** Config over codegen (catalog views), in-process validation, one WebSocket, no new transport; `/ask` is one endpoint over data Core already holds. ✅
