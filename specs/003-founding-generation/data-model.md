# Data model: FS-3 Founding & generation

Contract-owned shapes are referenced, not restated. Core-side records are stored through `core.services` (SurrealDB; record ids mapped from contract ids on every write).

## VillageSpec (contract `village_spec.schema.json`, produced here)
| Part | Produced by | Notes |
|---|---|---|
| `village{id, name, kind, lang, timezone, coordinator_id, care_recipient_id?, theme}` | blueprint step (+ `theme.relationship_words` from follow-ups) | `status` is **not** in the contract; see additions |
| `blueprint.description{text, speaker, lang}` | verbatim founding text; follow-up answers appended as new paragraphs so `source_span` stays valid | |
| `blueprint.people[]` (id, name, short_name, relation, role, view, phone?, notes, life_areas, `profile` capability_profile, `consent`) | blueprint step; `consent.ai_calls = null` unless the input states it; `recorded_by = "founder, setup call"` | profile `evidence[]` = `{field, source{kind: call|app, ref, secs|quote}}` |
| `blueprint.edges[]` | blueprint step (cares_for, on_duty, backup, trusted_contact, helps, neighbor, coordinates) | rota edges use `Clock.today()` |
| `blueprint.needs[]` (`source_span` or `origin: follow_up|data`) | blueprint step; merged with render `needs` by id | ≤8 |
| `blueprint.rules[]` (human chips) | blueprint step | mapped to policy ids by the primary render |
| `blueprint.life_areas[]` | primary render (`modules`, `rules`, `trusted_contacts`) merged over the blueprint step's ids/labels | |
| `channels{member → [...]}` | derived: `app:<view>`, `phone_line` (tech_comfort phone or `uses: phone|both`), `lid_qr` + `fridge_card` (care recipient with dose slots), `outbound_calls` (consent.ai_calls true), `verification:app_prompt|call` (trusted contacts) | invariant 1 |
| `views{role → view}` | one `render_app` per role (or template) | `needs_served` kept per view |
| `policies[]`, `voice_lines[]`, `official_sources[]`, `refusals[]`, `needs_clarification[]`, `custom_components[]` | primary render; `custom_components[].status = planned` (FS-5 builds) | |
| `printables[]` | derived for `lid_qr` members: one `lid_sticker` per dose slot (color/label from input or defaults), one `fridge_card` (`[NÚMERO]`, `[PALABRA]`) | `token_ref` minted at activation |

## FoundingSession (core, `founding_session`)
`{id: fs_*, village_id, channel: voice|text, conversation_id?, founder_member_id, lang, state: listening|clarifying|drafting|draft|active|failed, description_turns[{text, at, origin: description|follow_up}], questions_asked[≤2], options{mode: full|fast|fixture}, created_at, updated_at}`

Lifecycle: `listening → (blueprint) → clarifying?* → drafting → draft → (activate) → active`. `failed` only when even the template path fails (should never happen; alert in the Control Room).

## BuilderRun (core, `builder_run`; one per found/patch)
`{id: br_*, village_id, mode: render|patch, prompt{source: hub|local, version_id}, model, blueprint{ms, frames, questions}, roles{<role>: {status: validated|repaired|template|skipped, attempts, errors[], ms, ttft_ms, cache_read_tokens}}, total_ms, trace_id, at}`

## Invite (core, `invite`; minted at activation)
`{id: inv_*, village_id, member_id, role (view key), token_hash, kind: join, url, status: issued|redeemed|revoked, issued_at, expires_at (+24 h wall), redeemed_at?, redeemed_by{first_name, phone?}}`
Rules: one active invite per member; token appears only in the URL/QR (`/join?i=<token>`), never in specs, logs or traces (`slot_token` convention); `POST /auth/redeem` consumes it and returns a member token.

## DecisionLogEntry (core `decision`; FS-1 owns the table, builder emits rows)
`{id: dc_*, village_id, at, actor: builder|gate|evolve|voice:setup|release, kind: plan|decision|note, text (≤400, plain words), rule_id?, refs[{kind: need|member|event|fact|policy, id}], source{kind: system, ref: "builder"}, trace_id}`

Rows the builder writes during founding:
- `plan`: the `plan` string of each render (verbatim, ≤280).
- `decision`: channel choice per member ("Carmen: phone line + lid stickers. She uses a flip phone and mixes up her pills" refs m_carmen, n_evening_pills), role/view per member, trusted contacts ("Marco checks money asks in his name: Ana said 'pretending to be Marco'" refs n_scam_calls), consent state ("Lucía: no AI calls, she said app only"), rules switched on, refusals.
- `note`: follow-up asked/answered, `repaired <role>: <errors>`, `template <role>: <reason>`, `prompt v<version> from hub|local`, `village_activated: N invites`.
These rows are the material of `/ask` and of the Control Room DecisionsLog (FS-4).

## AskAnswer (not stored; returned + traced)
`{answer, lang, citations[{id, kind: decision|fact|event, label, at, source}], dropped_citations: n, trace_id}`

## Message (core `message`; D16 village chat)
`{id: msg_*, village_id, author: <member_id> | village | system, kind: chat|incident|proposal|receipt|nudge|answer, text (≤1000; localized for village/system posts), mention: village|null, reply_to?: msg_*, refs[{kind: event|decision|fact|proposal|release|member, id, label?}], source{kind: app|system, ref}, at}`
Rules: members write only `kind: chat`; `village` posts are created by Core from ledger events or by `builder.ask()`/`builder.patch()` and always carry ≥1 ref; `system` posts are lifecycle lines ("Ana invited everyone", "Marco joined"). Append-only (a correction is a new message, never an edit). Not visible to elder views; never on the safety path; binding `chat:village` = last 50.

## Village lifecycle (core `village` row, alongside the spec)
`{id, status: draft|active, founder_id, draft_rev, published_rev, created_at, activated_at?}` → `draft` (edits allowed, no invites/calls/prompts) → `active` (invites minted; edits only via proposals, FS-6).

## State transitions guarded by code
| Transition | Guard |
|---|---|
| draft → active | caller is founder/leader (member token) or control token; status is draft; spec validates |
| invite issued | village active; member has a non-null view |
| invite redeemed | status issued, not expired; consent body valid → `consent` event + profile update |
| outbound call / prompt to a member | village active AND consent (FS-1 gate R-CONSENT / R-VERIFY-CONSENT) |
