# Data Model: FS-4 Kit

The kit stores no durable data. Its model is (a) what arrives over the WebSocket, (b) the in-memory session, (c) the mapping from spec elements to React props, and (d) the theme tokens derived from the spec.

## 1. Session state (`useLive`)

```ts
type SocketState = "idle"|"connecting"|"hello_sent"|"live"|"resync"|"reconnecting"|"closed";
interface LiveState {
  socket: SocketState; attempt: number; closedReason?: "bad_token"|"contract_mismatch"|"manual";
  village: string; role: string | "control"; member_id: string | null;
  rev: number;                         // snapshot.rev, advanced by patch.rev
  view: View | null;                   // member clients: views[role]; control: whole VillageSpec
  data: Record<string, unknown>;       // snapshot.data merged with event.data; null deletes
  now: string; drift: number;          // server clock + ms drift
  prompt: PromptFrame | null;          // current verification overlay
  highlight: Set<string>;              // element ids flashed NEW (cleared after 2 s)
  pending: Map<string, PendingAction>; // req_id → promise handles
  unknownTypes: string[];              // for data-test="unknown-types"
}
```

Invariants: `view` is always zod-valid or null; `rev` only moves forward; `data` keys are exact bind strings from the view (keys not referenced by the view are kept but unused).

## 2. Message types (from `ws_messages.schema.json`) and what the kit does

| Direction | Type | Fields the kit uses | Handling |
|---|---|---|---|
| C→S | `hello` | contract_version, village, member_token, last_rev?, client | first frame; `client` = `kit` (member), `control`, `scan_page`, `test` |
| C→S | `action` | req_id, name, arg?, element_id, payload?, client_ts | from BigButton, ScamCheck, VerificationPrompt, IncidentCard, Proposal, DoseTracker(log), CareRota(swap), SymptomLog, CheckIn, NeedBoard, ResourceBoard, VerifiedInfoFeed |
| C→S | `ack` | event_id, status, req_id? | Alert "I've got it" / IncidentCard ack (`got_it`), escalation banner (`accepted`/`declined`) |
| C→S | `ping` | ts | every 15 s |
| S→C | `snapshot` | rev, role, member_id, spec, data, now | replace all; set `<html lang dir>`; theme attributes |
| S→C | `patch` | rev, base_rev, role, ops[], highlight[], proposal_id? | gated apply; highlight |
| S→C | `event` | event{id, kind, at, source…}, data? | merge data; for Control Room also feed the gate/timeline panes |
| S→C | `prompt` | verification_id, question, detail, options[], deadline, closed? | overlay |
| S→C | `result` | req_id, ok, decision?, event_id?, error? | resolve pending; show `decision.say[lang]` in the originating component |
| S→C | `control` | kind, payload, at | Control Room reducer (member clients ignore) |
| S→C | `pong` | ts | dead-man reset |
| S→C | `error` | code, message | fatal for `bad_token`/`contract_mismatch`; otherwise strip |

### Binding values (`$defs/bv_*`) → component

| Bind key | Value type | Consumed by |
|---|---|---|
| `alerts:active` | `bv_alert[]` {id, severity, title, body (localized), event_id?, verification?{id, claimed_member_id, deadline, status}, escalation?{to, channel, status}, at} | Alert (countdown from `verification.deadline`; "Village is calling you" from `escalation`) |
| `verifications:pending?member=me` | `bv_pending_prompt` \| null | VerificationPrompt |
| `verifications:mine` | `bv_my_verification` {status, state, deadline, say, claimed_name} \| null | ScamCheck states |
| `incidents:open` / `incidents:subject=<id>` | `bv_incident[]` {incident_id, type, severity, status, title, summary, verification_status?, claimed_identity?, amount?, method?, red_flags[], provenance[{label, source}], at} | IncidentCard |
| `facts:dose_event?…valid_at=today` | `bv_dose_day` {date, slots[{slot, status, taken_at, via, lid_color?, meds?}]} | DoseTracker, StatusGrid(?count) |
| `facts:dose_event?…valid_at=week` | `bv_dose_week` {days[bv_dose_day]} | PillOrganizer |
| `rota:current?member=me` | `bv_rota_me` {is_my_turn, on_duty, backup, until, next_shift, answer, status_line?} | HelperAnswer |
| `rota:week` / `rota:current` | `bv_rota_day[]` | CareRota |
| `rota:current.on_duty|backup` | `bv_person` | ContactCard(bind) |
| `timeline:subject=<id>` | `bv_timeline_item[]` {event_id, kind, at, text, source, source_label?, rule_id?, superseded} | Timeline → Fact view |
| `blueprint:life_areas` | `bv_life_area[]` {id, label, status, rules?, trusted_contacts?} | LifeAreas |
| `proposals:pending` | `bv_proposal[]` {proposal_id, title, changes[], evidence_labels[], status, release_id?} | Proposal |
| `…?count` | number | StatusGrid |
| `member:<id>` | `bv_person` | ContactCard |

Localized text resolution: `t(localized, lang) = localized[lang] ?? localized.en ?? first value`.

## 3. Spec → component prop mapping

For each `element` the renderer builds `{...props, _id, _bind: data[props.bind], _lang, _theme, _send}`. Contract props map 1:1 to React props with the same snake_case names (no renaming, so test ids and docs match the schema). Derived props:

| Component | Derived from | Notes |
|---|---|---|
| Screen | `read_aloud` ⇒ ReadAloud button; `village.theme.relationship_words` substituted where the title contains `{care_recipient}` (builder passes a plain title; substitution only for templates) | `data-role`, `data-rev` |
| BigButton | `tone` ⇒ class; `tone: danger` ⇒ ConfirmSheet with `confirm_text`; `action_arg` ⇒ `arg`; `icon` ⇒ inline SVG from the 12-icon set | disabled while pending |
| Alert | `severity_levels` filters `bv_alert[]`; `show_countdown` + `verification.deadline` ⇒ Countdown; `show_escalation_status` ⇒ escalation line; `empty_text` when empty | elder: only the top alert, `≥ 28 px` title |
| ScamCheck | `bv_my_verification.status/state` ⇒ `idle` (no record or closed) · `checking` (pending; countdown) · `denied` · `timeout` · `confirmed`; text = `say[lang]`; tap in `idle` ⇒ chooser with `choices_member_ids` (names from `member:<id>` or `relationship_words`) + `other_label` | `data-state` |
| VerificationPrompt | `bv_pending_prompt` null ⇒ renders nothing; `question_template` ignored when the binding carries `question` (binding wins) | mirrored by PromptOverlay for the `prompt` frame; both share `verification_id` so answering one closes both |
| IncidentCard | severity ⇒ tomato-soft / amber-soft / card; `show_*` toggles; `allow_ack` ⇒ ack button sends `action ack_incident{arg: incident_id}` | `limit` slices |
| HelperAnswer | `answer[lang]` display type; `show_status` ⇒ `status_line`; `show_next_shift` ⇒ `next_shift` via `Intl.DateTimeFormat` | |
| Proposal | `status ∈ {verifying}` ⇒ buttons disabled + strip; `ready` ⇒ Approve/Not now; `applied` ⇒ "Live on every phone" | |
| DoseTracker | slot rows with lid chips; `show_med_names` false ⇒ `meds` dropped before render (elder never sees them even if sent) | `data-slot`, `data-status` |
| PillOrganizer | `days[]` × `slots[]` grid; cell from `bv_dose_week.days[d].slots[s].status`; colors from `lid_colors[i]` | generated custom component in FS-5 may replace this with the family's own; the kit ships a default |
| Timeline | `event_kinds` filter incl. aliases `verification`, `dose_blocked`; `show_superseded` ⇒ struck rows; `show_provenance` ⇒ source line; tap ⇒ Fact view with `event_id` | |
| LifeAreas | `areas[]` order; status chip text from binding; colors health ok-soft / money tomato-soft / people card | |
| ContactCard | `phone` ⇒ `tel:` link + `call_number` action; `member_id` ⇒ `call_member`; `kind: emergency` ⇒ tomato | elder: full-width big |
| ReleaseStrip (control) | `receipt.stages[]` ⇒ 6 tiles; `result` ⇒ caption; `failed` stage ⇒ tomato-soft summary line; `repair_of` ⇒ "Fixed in rev N" link | `data-test="stage-<name>"` |
| DecisionsLog (control) | `control{reasoning kind:decision}` rows {at, text, source, trace_id?} newest first, max 50 | |

## 4. Theme tokens as data
```ts
interface VillageLayer { accent: "#2F6B57"|"#2F6F8F"|"#6A3F7A"|"#2F5FA7"; accentSoft: string; lids: Record<slot, hex>;
  words: Record<member_id, Record<lang, string>>; lang: string; dir: "ltr"|"rtl"; density: "elder"|"family"|"dashboard" }
```
Derived at snapshot time from `village.theme`, `views[role]`, `custom_components[PillOrganizer].config.lid_colors_by_slot` (control) or `PillOrganizer.props.lid_colors` (member). Floor tokens are constants in CSS and have no JS representation (nothing can set them).

## 5. Pages' inputs
- **Scan page:** `LidScanResult` (`lid_scan.schema.json`): uses `page.{lang, tone, headline, lines, read_aloud}`, `slot`, `subject`, `event?.payload.taken_at`, and `decision.escalate` (to show "Le avisamos a Marco" only when the gate said so, from `page.lines`). Error page: `{tone:"error"}` synthesized by Core on 404.
- **Join page:** invite `{village, role_key, display_name, intro}` from the invite URL's JSON (`GET /villages/{id}/qr` JSON for the projector; the invite link itself carries `i=<invite_token>`); submit `{invite_token, first_name, mobile, ai_calls}` → `POST /auth/redeem` → `{member_token, village, member_id}`.
- **Fact view:** `bv_timeline_item` plus `GET /villages/{id}` (coordinator) for history where Core provides `facts` (memory lane); shape `{key, current{value, since, source}, history[{value, from, to, source}], conflict?{claim{value, source, quote}, options[{label, action}]}}`. Until the memory endpoint lands, the view renders from Timeline items with `superseded`.
- **Printables:** `VillageSpec.printables[]` + QR SVG per `token_ref` from `GET /villages/{id}/qr`.
- **Control Room:** whole `VillageSpec` + all `control` payloads + `POST /villages/{id}/ask` → `{answer, sources[{label, kind, ref, url?}]}`.
