# FS-3 contracts: what exists, what the builder consumes, what the orchestrator must add

All shapes below reference `contracts/` v1.0.0. The builder lane edits nothing in `contracts/`; the "Additions" section is a request to the orchestrator (bump to **1.1.0**, minor: new paths and enum values).

## Existing (consumed as-is)
### `POST /tools/create_village` (voice path; `X-Village-Secret`)
Body = `voice_tools.schema.json#/$defs/req_create_village`:
```json
{ "conversation_id": "conv_…", "caller_id": "+1555…", "call_secs": 71.2, "utterance": "…yes, that's right",
  "tool_call_id": "tc_…",
  "description": "Mom's seventy-eight and alone in Queens. She mixes up her pills, …",
  "members": [ { "name": "Carmen", "relationship": "mother", "role_hint": "care_recipient", "channel": "voice", "language": "es" },
               { "name": "Marco", "relationship": "brother", "role_hint": "caregiver", "channel": "app", "availability": "works nights" },
               { "name": "Ana", "relationship": "self", "role_hint": "coordinator", "channel": "app" } ],
  "needs": ["evening pills", "someone pretending to be Marco asked her for money", "whose turn it is"],
  "medications_mentioned": [], "language": "en" }
```
Response (≤2 s) = `voice_tools.schema.json#/$defs/response` with `data = data_create_village`:
```json
{ "decision": "allow", "say": "Building it now. You'll see the draft on your screen in a moment.", "rule_id": "R-NOOP", "lang": "en",
  "data": { "village_id": "v_reyes", "rev": 0, "plan": "Carmen, Ana, Marco → pills, money, turns" } }
```
Note: `prompts/setup_agent.md` still points the tool at `{{VILLAGE_API}}/villages`; the voice lane must point it at `{{system_env__core_host}}/tools/create_village` (contract name wins).

### `POST /villages` (text path; control token) → `202 {village_id, plan?, ws_url}`
Body `{description, members?, needs?, language?, mode: full|fast|fixture}`. The founding box sends `description` + `language` only.

### `GET /villages/{id}` → VillageSpec (ETag `W/"rev-<n>"`), `GET /villages/{id}/qr?kind=join&format=json` → `[{member_id, kind, url, svg}]`, `POST /auth/redeem` → member token + `consent_event` — unchanged; FS-3 defines their behaviour on drafts (409 below).

### WS `control{kind: reasoning}` (existing) — the blueprint stream
```json
{ "type": "control", "kind": "reasoning", "at": "2026-10-16T12:40:03-04:00",
  "payload": { "source": "builder", "kind": "note", "text": "Found Carmen, 78, mother. Spanish first. Uses a flip phone.", "village": "v_reyes", "trace_id": "…" } }
```
Frame order: `plan` ("Listening: 3 people, 3 problems") → one `note` per person, per need (with the quoted words), per life area, per rule → `decision` per channel/role/contact choice → `note` for questions, repairs, templates → `plan` per render → `note` "draft ready rev 1". Then a control `snapshot` with the full spec.

## Additions the orchestrator must add (contracts 1.1.0)
1. **`village.status`** in `village_spec.schema.json#/$defs/village`: `{"enum": ["draft", "active"], "default": "active"}` (fixtures stay valid via the default; `validate.py` example unchanged). Without it, Core must keep status outside the spec and `GET /villages/{id}` cannot show it.
2. **`POST /villages/{id}/activate`** (memberToken of the leader | controlToken) → `200 { "status": "active", "rev": 1, "invites": [ { "member_id": "m_marco", "kind": "join", "url": "https://<host>/join?i=…", "svg": "<svg…>" } ], "printables": [ { "id": "pr_lid_evening", "token_ref": "st_…", "url": "https://<host>/s/…" } ] }`; `409 conflict` if already active; `422` if the draft fails validation.
3. **`POST /villages/{id}/ask`** (controlToken | leader memberToken) body `{ "question": "Why did you call Marco and not Lucía?", "lang": "en" }` → `200 { "answer": "…", "lang": "en", "citations": [ { "id": "dc_1016_1240_consent", "kind": "decision", "label": "Lucía: no AI calls (she chose app only)", "at": "…", "source": { "kind": "system", "ref": "builder" } } ], "trace_id": "…" }`. Read-only. `kind ∈ decision | fact | event`.
4. **`POST /villages/{id}/answers`** (controlToken) body `{ "answers": [ { "question": "Anyone else who helps?", "text": "My sister Lucía, by phone, she does refills" } ] }` → `202 {village_id, state}`. Text-path follow-ups only.
5. **`POST /villages/{id}/draft`** (leader | control) body `{ "ops": [RFC 6902 add|remove|replace on the allowed paths in plan.md §7] }` → `200 {rev}`; `409` if active; `422` with the invariant name on a floor violation.
6. **`decision.schema.json`** (new, FS-1 co-owned): the DecisionLogEntry shape in `data-model.md`, plus `common.schema.json#/$defs/actor` already has `builder`. `GET /villages/{id}/decisions?limit=` for the Control Room (FS-4) and `/ask`.
7. **Event kinds**: add `village_activated` (payload `{rev, invites: n}`) and `invite_redeemed` (payload `{member_id, invite_id}`) to `event.schema.json#/$defs/kind` (or fold the second into `consent.payload`). The SurrealDB `event.kind` ASSERT list must match.
8. **`common.schema.json#/$defs/invite_id`** `^inv_[A-Za-z0-9_]{2,64}$` and `invite_token` (same rules as `slot_token`: secret, never in specs/traces).
9. **Optional:** `control{kind: blueprint}` payload `{ "stage": "people|needs|life_areas|rules|kind|questions|done", "items": [ … contract-shaped objects … ] }` so the Control Room draws chips without parsing text. V2 works without it.
10. **Village chat (D16).**
    - `village_spec.schema.json`: add `VillageChat` to `catalog_type` + `props_VillageChat {bind: const "chat:village", title?, show_composer (bool), mention_label (≤20), allow_approve (bool)}`; add `chat:village` to the `bind` pattern; invariant: never in `theme: elder` views, ≤1 per view.
    - `ws_messages.schema.json`: new server message **`chat`** `{ "type": "chat", "village": "v_reyes", "message": { "id": "msg_…", "author": "village", "kind": "incident", "text": "Someone called Mamá as Marco asking for $2,000. Marco said it wasn't him.", "refs": [ { "kind": "event", "id": "ev_1016_1402_inc" } ], "reply_to": null, "at": "2026-10-16T14:02:40-04:00" } }`; `$defs/bv_message` for the `chat:village` binding (`[bv_message]`, last 50). Sent only to sockets whose view is not `elder`.
    - `openapi.yaml`: **`POST /villages/{id}/messages`** (memberToken) body `{ "text": "…", "mention": "village" | null, "reply_to"?: "msg_…", "client_ts"? }` → `201 { "message": {…}, "routed": "none" | "ask" | "change_request" }`; **`GET /villages/{id}/messages?after=<msg_id>&limit=50`** → `[message]`. Elder members get `403`.
    - `common.schema.json`: `message_id` `^msg_[A-Za-z0-9_]{2,64}$`; `message_kind` enum `chat|incident|proposal|receipt|nudge|answer`; `message_ref` `{kind: event|decision|fact|proposal|release|member, id, label?}`.
    - No new event kind: chat rows live in `message`, not the ledger; Village posts reference ledger rows by id.
11. **`/villages/{id}/qr` on a draft** → document `409 conflict` ("village is draft"), and `/villages/{id}` `404` vs `403` for non-leader members.

## Behaviour notes for other lanes
- **kit (FS-4):** `VillageChat` component (feed by `kind`, composer with "@Village", inline Approve/Not now via the existing `approve_proposal`/`reject_proposal` actions, source chips from `refs[]`), applies WS `chat` frames to the `chat:village` binding; the founding box posts to `/villages` and `/villages/{id}/answers`; the Control Room draws from reasoning frames + the control snapshot; the draft review page uses `GET /villages/{id}` + `POST …/draft`; "Invite everyone" calls `/activate` and renders the returned `svg`s; the Ask box calls `/ask` and renders `citations[]` as tappable source chips.
- **voice (FS-2):** the setup agent's tool URL and the fixed `say` line; follow-ups are asked by the agent before the webhook.
- **gate (FS-1):** R-CONSENT/R-VERIFY-CONSENT must also deny when `village.status != active` (new param `village_status` in `GateInput.village_state`, or Core refuses before the gate).
- **memory (FS-6):** `services.facts_for(village)` returns `[{id, text, labels{src, secs, village, agent}, at, superseded}]` for `/ask`; until merged, the builder derives facts from `events_reyes_seed.json`.
