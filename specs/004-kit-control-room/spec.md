# Feature Specification: FS-4 Kit (generated apps + Control Room)

**Feature branch:** `lane/kit` (worktree `../village-kit`)
**Created:** 2026-10-16 · **Status:** Draft, ready for `/plan`
**Lane:** kit · **Versions:** V0 → V4 · **Folder owned:** `kit/`
**Inputs:** PRODUCT.md §1 (surfaces), FS-4 row, US-04..08, 10, 12, 13, 16, 17, 18 · EXPERIENCE.md (direction A/B, journeys 3, 5, 6, 7, 9) · DECISIONS D4, D8, D10, D13, D15 · LAYERS.md version map · FLEET.md kit row · `contracts/schemas/{village_spec,ws_messages,release,proposal,lid_scan}.schema.json` · `contracts/fixtures/{reyes_spec,ws_sequence_scam,lid_scan_sequence}.json` · `design/*.dc.html` · `research/generative-ui.md`

## Summary

The kit is the only thing a member of a village ever touches with their fingers. It is a Vite + React + TypeScript static app that (1) renders a role view from the flat adjacency `view` object in a VillageSpec using a fixed, tested catalog, (2) keeps that view alive over one WebSocket to Core (snapshot, RFC 6902 patches, events, prompts), (3) routes every tap through Core's gate (never writes data itself), (4) offers the scan-confirmation, join/consent and Fact pages, (5) prints lid stickers and the fridge card, and (6) hosts the projector's Control Room. It owns no safety logic: wording for outcomes comes from the gate's `say`, data comes from `snapshot.data` / `event.data`, and the accessibility floor is a theme that generated tests (FS-5) can measure through stable selectors.

The same bundle serves three audiences: the elder (Carmen, light high-contrast, Spanish, read-aloud), the coordinator (Ana, dense dashboard) and helpers (Marco, Lucía, "Is it my turn?"), plus the judges' projector.

## User scenarios and testing

### US-A · A member's phone renders their generated app (US-05, US-08) — P1
Given a valid `?m=<member_token>` in the URL and Core reachable,
When the page loads,
Then the kit sends `hello{contract_version, village, member_token, client:"kit"}` and renders `snapshot.spec` (the member's `views[role]`) with `<html lang dir>` set from the view, within 1 s of the snapshot; the Screen title, every catalog child and the "read aloud" control are visible; `data-test="ws-status"` reads `open`.

Given Marco's helper view (`reyes_spec.json`),
When the snapshot carries `rota:current?member=me`,
Then `HelperAnswer` shows `answer.en` ("No. Ana is on tonight. You're next on Saturday.") in display type and nothing else is invented.

### US-B · Every phone updates live, no refresh (US-05, US-06) — P1
Given three tabs (elder, coordinator, helper) connected at rev 4,
When Core sends the `event{kind: dose, data: {"facts:dose_event?…=today": …}}` frames from `lid_scan_sequence.json`,
Then each tab's `DoseTracker` morning slot shows `taken` and the lid color `#E8B12F`, the coordinator sees med names, the elder never does, and no tab reconnected.

### US-C · Scan confirmation page (US-06) — P1
Given Carmen's phone opens `/s/<slot_token>` (Core renders the page shell with the `LidScanResult` JSON inline),
When the result has `page.tone: ok`,
Then the page shows "Anotado, Carmen", "Pastillas de la mañana a las 8:02", "Su familia ya lo sabe." in `≥ 28 px` type on a light background with the lid-color chip, and reads `page.read_aloud` aloud after the first tap (iOS rule) or immediately where allowed.
When `page.tone: report`,
Then the amber "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco." card renders with no red, no advice, and the headline is the gate's `say` verbatim.
When the token is bad (`404`),
Then "Esta etiqueta no funciona. Llame a Village." with the village number and no ledger side effect.

### US-D · Verification prompt on Marco's phone (US-10) — P1
Given the judge joined as Marco and is connected,
When the `prompt{verification_id, question, detail, options, deadline}` frame arrives,
Then a full-screen overlay "Village is calling you · AI assistant" shows the question in the member's language, two buttons (`no` = "That wasn't me" tomato, `yes` = "Yes, it was me" outlined), a `role="timer"` countdown computed against `snapshot.now`, and the line "If nobody answers, Village tells Mamá not to send money."
When Marco taps "That wasn't me",
Then the kit sends `action{req_id, name:"answer_verification", element_id:"vp", payload:{verification_id, answer:"no"}}`, disables both buttons until `result{req_id}` returns, then shows the thanks state ("Thanks, Marco. Mamá was told it wasn't you…") using the `say` from the result, never its own words.
When a `prompt{…, closed:true}` arrives (answered on the call, or deadline),
Then the overlay dismisses.

### US-E · Elder alert with countdown (US-09, US-11) — P1
Given Carmen's elder view with `Alert{show_countdown:true}`,
When `alerts:active` carries `verification{deadline, status: pending}`,
Then the amber card "No mande dinero todavía / Estamos confirmando con Marco." shows a countdown (`0:23`), and on `status: denied` turns tomato with "Ese no era Marco / No mande dinero. Ana ya lo sabe." (title/body from the binding, not from the kit).

### US-F · Ana's incident card and Fact view (US-12, US-13) — P1/P2
Given the coordinator view with `IncidentCard{bind:"incidents:open"}`,
When `event{kind: incident, data:{"incidents:open":[…]}}` arrives,
Then a card renders with severity color, localized title/summary, red flags as chips, verification status, and a "Source" line listing `provenance[].label`; `allow_ack` shows "I've got it" which sends `ack{event_id, status:"got_it"}`.
When Ana taps a Timeline item or a provenance chip,
Then the Fact view opens: "What we believe now", "History (nothing is overwritten)" with superseded rows, and, when a conflict exists, a "Needs a person" amber block with the two options from the data (the kit never resolves a conflict itself).

### US-G · Join and consent (US-04) — P1
Given a judge opens the "Be Marco" invite URL,
When the Join page loads,
Then it shows "You're joining as Marco", first-name and mobile fields, the consent checkbox with the exact copy from `design/Join.dc.html`, and the "Join the family" button is disabled until the name is non-empty; consent is optional (unchecked → `ai_calls:false`).
When submitted,
Then `POST /auth/redeem` returns a member token; the kit stores it in the URL (`?m=`) and `localStorage`, then connects the WebSocket; on error it shows the server message and keeps the form.

### US-H · Evolve lands on every phone (US-16) — P1
Given Carmen's elder view at rev 4,
When `patch{rev:5, base_rev:4, role:"elder", ops:[add /elements/scam, add /elements/s/children/3], highlight:["scam"]}` arrives,
Then the kit applies the ops with `fast-json-patch` on a clone, validates the result with zod, re-renders, and the new `ScamCheck` card fades in with a "NUEVO" tag for 2 s (none with `prefers-reduced-motion`); rev becomes 5.
When a patch arrives whose `base_rev` ≠ local rev,
Then nothing is applied, the kit re-sends `hello{last_rev}` and waits for a snapshot.

### US-I · Proposal card for the leader (US-14, US-15) — P2
Given the coordinator view with `Proposal{bind:"proposals:pending", allow_approve:true}`,
When `proposals:pending` carries a `ready` proposal,
Then the card lists `changes[]`, `evidence_labels[]` and, with `show_release_status`, the release id; "Approve" sends `action{name:"approve_proposal", arg:<proposal_id>}` and "Not now" sends `reject_proposal`; while `status` is `verifying` the buttons are disabled and the strip shows progress.

### US-J · Control Room on the projector (US-17, US-18, journeys 1, 9) — P1 (V2)
Given `/control?c=<control_token>`,
When connected, the page shows the Direction A layout: header (village tabs, phones-connected counter, demo clock + warp), "What the agent heard" (blueprint assembling from `control{reasoning}`), the three live phones, the verification countdown, the rebuild pipeline strip (`ReleaseStrip` from `control{release}`), the build log, the Anchor live view (`control{qa}.live_view_url` iframe), the safety-gate feed (`control{gate}`), the `DecisionsLog`, and the "Ask Village why" box.
When a judge types "Why did you call Marco and not Lucía?",
Then the kit `POST`s `/villages/{id}/ask` and shows the answer with its cited sources as chips; the box is disabled while a request is in flight.
When `control{counter:{name:"phones_connected"}}` arrives, the counter updates with tabular numerals.

### US-K · Printables (journey 3) — P2
Given the coordinator opens `/print?m=<token>`,
When the spec's `printables[]` are available,
Then a letter-size page renders two lid stickers (MAÑANA yellow `#E8B12F`, NOCHE blue `#2F5FA7`, each with its QR from `/villages/{id}/qr` and the instruction line) and the fridge card (number, family word, "Village nunca pide dinero ni códigos.", the emergency line in tomato); `@media print` hides everything else and uses dashed cut lines.

### Edge cases
- **WS drop mid-patch:** the socket closes after `patch` frame bytes are partially received or before `result` arrives → the pending action's promise rejects with `disconnected`, the UI re-enables the button, the client reconnects with backoff (0.5 s → 8 s, jitter) and sends `hello{last_rev}`; a snapshot replaces local state wholesale; the user sees a thin "Reconnecting…" strip, never a blank screen.
- **Unknown component type** (e.g. `CustomFoo` not in the catalog, or a future contract type): render nothing, log once to console, count it in `data-test="unknown-types"`; siblings render normally. Children of an unknown node are not rendered.
- **Invalid snapshot/patch result** (zod fails): keep the last valid view, show a one-line "Waiting for a valid update" strip, send `hello` to resync.
- **RTL and long strings:** `dir="rtl"` from the view flips layout via logical properties; a 60-char label wraps inside a BigButton without shrinking below floor sizes; a 280-char `Text` wraps; a 600-char localized body in an Alert truncates visually with full text in `aria-label` and read-aloud.
- **Missing language key:** a `localized` value without the view's `lang` falls back to `en`, then to the first key; it never shows `[object Object]`.
- **Offline / Core down:** the PWA shell loads from the service worker; the last snapshot is restored from `sessionStorage` tagged "last seen 14:02" and all actions are disabled; the service worker never caches `/ws`, `/v/`, `/s/`, `/villages`, `/auth`.
- **Countdown past deadline with no event:** the timer stops at `0:00` and shows "waiting for Village" until the gate's event arrives (silence is safe; the kit never writes "denied" itself).
- **Duplicate prompt frames** (same `verification_id`): one overlay; `closed:true` dismisses regardless of order.
- **Two tabs, one member:** both receive frames; an action from one yields `result` only on that socket; the other tab learns from the following `event`.
- **`error{code: bad_token | contract_mismatch}`:** no retry; show the message and the join link.
- **iOS speech:** `speechSynthesis` only after a user gesture; the "read aloud" button is the gesture; `speak` on a BigButton is spoken on tap, before the action, never as the outcome.
- **Role view with zero actions** (phone-only member rendered on the shared tablet): still shows a 911 card and the read-aloud control.

## Functional requirements

| ID | Requirement | Principle |
|---|---|---|
| FR-001 | The renderer MUST accept a `view` (`village_spec.schema.json#/$defs/view`), start at `root:"s"`, and render each element by looking up `type` in the catalog; unknown types MUST render nothing and MUST NOT throw. | V, IX |
| FR-002 | The catalog MUST implement every `catalog_type` in the contract (26 types) plus `ReleaseStrip` and `DecisionsLog` for the Control Room, with every state shown in `design/Cards.dc.html` (ScamCheck ×4, VerificationPrompt ×2, IncidentCard ×3, LifeAreas, LidStatus ×2, HelperAnswer, Proposal, ReleaseStrip, DecisionsLog). | V |
| FR-003 | Props MUST be validated with zod schemas derived from the contract per type; invalid props for one element render nothing for that element only. | V, VI |
| FR-004 | Live data MUST come only from `snapshot.data` / `event.data` keyed by the exact `bind` string; the kit MUST NOT compute bindings (no rota math, no dose math) and MUST treat `null` as "clear". | III, VI |
| FR-005 | The kit MUST open exactly ONE WebSocket per page to `/ws?village=<id>&m=<token>` and send `hello` first; it MUST handle `snapshot, patch, event, prompt, result, control, pong, error`. | IX (D4) |
| FR-006 | Patches MUST be applied with `fast-json-patch` on a structural clone only when `patch.base_rev == local rev`; otherwise the client MUST resync via `hello{last_rev}`. | VI, VII |
| FR-007 | Reconnect MUST use exponential backoff 0.5 s → 8 s with jitter, send `ping` every 15 s, treat 10 s without `pong` as dead, and expect a fresh `snapshot` after reconnect. | VII |
| FR-008 | Every tap MUST become `action{req_id, name, arg?, element_id, payload?, client_ts}` (or `ack`) over the socket (fallback `POST /v/{id}/actions/{name}`); the kit MUST never write to SurrealDB or call the LLM. | I, II |
| FR-009 | Outcome wording shown after an action or verification MUST be the gate's `say[lang]` / binding `title`/`body`; the kit MUST NOT generate or template outcome sentences. Static labels in the kit are limited to the reviewed strings in `kit/src/i18n/*.json`. | V |
| FR-010 | The elder theme MUST be light, `≥ 7:1` contrast, BigButton `≥ 88 px` tall and full width, primary text `≥ 28 px`, tap targets `≥ 48 px`, no med names (`meds` is ignored even if present), confirm dialog on `tone: danger`, read-aloud control on every screen. These values MUST live in `floor.css` and MUST NOT be overridable by the village layer. | V (D8) |
| FR-011 | Safety colors MUST be fixed: stopped/needs-help `#A8331A`, recorded `#2E6F42`, needs-a-person amber `#FCEFD6` on `#7A4B00`; every tone MUST also carry an icon and a word (never color alone). | V |
| FR-012 | The village layer MUST read `village.theme.accent` (restricted to the approved range: sage `#2F6B57`, sky `#2F6F8F`, plum `#6A3F7A`, blue `#2F5FA7`), `theme.relationship_words[member][lang]`, lid colors from `PillOrganizer.lid_colors` / `printables[].color`, and `view.lang/dir`. | V |
| FR-013 | `<html lang>` and `dir` MUST follow the view; layout MUST use CSS logical properties; fonts: Fraunces (display), Atkinson Hyperlegible (body), Noto Sans per-script fallback, JetBrains Mono (logs). | V |
| FR-014 | The kit MUST ship four entries: `index.html` (member app incl. Fact view and `/print`), `scan.html`, `join.html`, `control.html`, built to `kit/dist/` with relative asset paths so Core (and the FS-5 sandbox `vite preview :4173`) can serve them. | IX (D7) |
| FR-015 | PWA: `vite-plugin-pwa` with `registerType: autoUpdate`, manifest per `research/generative-ui.md`, `navigateFallbackDenylist` for `/ws`, `/v/`, `/s/`, `/villages`, `/auth`, `/tools`, `/hooks`; apple touch icon + meta; one-line iOS "Add to Home Screen" hint. | IX |
| FR-016 | The Control Room MUST render from `role: "control"` snapshots (whole VillageSpec) and all `control{kind}` messages: `reasoning` → blueprint/decisions, `build_log` → log pane, `release` → `ReleaseStrip`, `qa` → Anchor pane, `gate` → safety feed, `counter` → counters, `clock` → demo clock. | VIII |
| FR-017 | The Control Room MUST expose "Ask Village why" (`POST /villages/{id}/ask`), rendering the answer and its sources; it MUST be read-only (no actions from the projector except clock warp). | VIII, II |
| FR-018 | Stable selectors: every catalog component MUST carry `data-test="<kebab-type>"` and the attributes listed in `contracts/README.md` of this spec; every interactive element MUST have an accessible name (`aria-label` or visible text). | IV, V |
| FR-019 | `highlight[]` ids in a patch MUST animate as NEW for 2 s (`aria-live="polite"` announcement), disabled under `prefers-reduced-motion`. | V |
| FR-020 | The kit MUST render fixture specs offline through a fake WS (`kit/dev/fakeWs.ts`) that replays `ws_sequence_scam.json` and `lid_scan_sequence.json` per client, so V0 is demonstrable without Core. | VI, VII |
| FR-021 | Printables: `/print` MUST render `printables[]` (lid stickers with QR from `/villages/{id}/qr`, fridge card with `family_word_first` ordering) with `@media print` CSS at letter size; the family word MUST never appear outside the print page and coordinator/control views. | II, III |
| FR-022 | The kit MUST never log tokens; `?m=` is moved into `sessionStorage` and stripped from the address bar after the first connect (`history.replaceState`), except on the Control Room where the control token stays. | II |
| FR-023 | Bundle budget: first paint `< 1.5 s` on a 2019 phone over venue Wi-Fi; JS `≤ 250 kB` gzipped per entry; no runtime dependency beyond `react`, `react-dom`, `fast-json-patch`, `zod`, `qrcode.react`. | IX |
| FR-024 | Read-aloud MUST speak the Screen title and each visible component's accessible summary in `view.lang`, via `speechSynthesis`, cancelable by a second tap. | V |

### Non-functional / constraints
- No CSS-in-JS runtime, no component library (catalog is hand-written on the tokens in `plan.md`).
- No router dependency: path switch by entry file + small in-app view state.
- All strings the kit owns are in `kit/src/i18n/{es,en}.json` and were reviewed; no runtime translation.
- Works at `390×844` (Anchor viewport) and `1920×1080` (projector at 150 % browser zoom).

## Key entities (see data-model.md)
View · Element · Catalog component · Binding value (`bv_*`) · WS session (rev, state) · Pending action (`req_id`) · Prompt overlay · Theme tokens (floor + village layer) · Control Room state (blueprint, receipts, build log, gate feed, decisions, counters, clock) · Printable.

## Constitution check

| Principle | How this spec complies |
|---|---|
| I. Agent acts; code draws lines | The kit has no decision logic: every tap is a gated action; outcome text comes from the gate. |
| II. Right person's say-so | Approve/reject only render for the coordinator's view; verification prompts only reach the named member (`verifications:pending?member=me`); consent captured on Join. |
| III. Facts keep sources | Timeline, IncidentCard and Fact view show `source` and `superseded`; nothing is overwritten client-side. |
| IV. Nothing untested reaches a person | Selectors and test ids (contracts/README.md) exist so FS-5's generated floor tests and Anchor QA can measure the floor; the kit renders only `published_rev` snapshots sent by Core. |
| **V. Built for the person** | Catalog-only renderer (FR-001/003), floor tokens un-themable (FR-010/011), pre-written safety wording (FR-009), any language/script (FR-013), elder always light/high-contrast. |
| VI. Contracts first | Builds against the five schemas + fixtures; fake WS replays fixtures; no private schema forks. |
| VII. Always a working version | V0 renders fixtures offline; each version's features are behind `VITE_LAYERS` flags. |
| **VIII. Observable and honest** | Control Room exposes reasoning, gate decisions, receipts, decisions log and Ask-why; counters only show values Core sends (no invented numbers). |
| IX. Simplicity | One WebSocket, one bundle, config over codegen, no framework runtime for generative UI. |

**Gate result:** PASS. Open points for the orchestrator are listed in `research.md` §Open questions (elder secondary text size; Control Room palette A vs Main.dc.html paper; `/print` route ownership).

## Out of scope
Builder prompts and spec generation (FS-3) · release pipeline and generated tests (FS-5) · voice (FS-2) · Core routes (FS-1) · Devpost/README (FS-7) · zh/ar content (architecture only) · native push, SMS, auth beyond tokens.
