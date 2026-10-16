# FS-4 Kit contracts: selectors, test ids and WS handling

This folder adds no new schemas (only the orchestrator edits `contracts/`). It freezes two things other lanes depend on: **(A) the DOM selectors** the release gate (FS-5 generated floor tests, Anchor QA) and `acceptance/` use, and **(B) the WS message handling table** Core's hub tests and the fake WS replay assume. Changing an entry here is a contract change: tell the orchestrator.

## A. Selectors and test ids

Conventions: `data-test` is the primary hook (kebab-case of the catalog type, or a page/region name); `data-*` attributes carry state; every interactive element has an accessible name. Anchor scripts use `page.getByTestId(...)` or `[data-test=…]`; floor tests use `getComputedStyle`.

### App shell
| Selector | Attributes | Used by |
|---|---|---|
| `[data-test="app"]` | `data-role` (elder/coordinator/helper/control), `data-rev`, `data-theme`, `data-lang`, `data-dir` | all checks: identity + rev gap tests |
| `[data-test="ws-status"]` | `data-state` ∈ connecting/open/reconnecting/resync/closed, `data-attempt` | reconnect acceptance (V0), Anchor wait-for-open |
| `[data-test="unknown-types"]` | `data-count`, `data-types` (comma list) | unknown-component test (expects `0` for fixtures) |
| `[data-test="read-aloud"]` | `aria-label` = i18n `read_aloud` (es: "Leer en voz alta"), `aria-pressed` while speaking | floor: read-aloud on every screen |
| `[data-test="reconnect-strip"]` | visible only when `ws-status` ≠ open | — |

### Catalog components (all carry `data-test` + `data-id` = element id)
| Component | `data-test` | State attributes / inner ids |
|---|---|---|
| Screen | `screen` | `data-title`; `h1[data-test="screen-title"]` |
| Stack / Header / Text | `stack` / `header` / `text` | Text: `data-tone`, `data-size` |
| BigButton | `bigbutton` (a `<button>`) | `data-action`, `data-arg`, `data-tone`, `data-pending`; ConfirmSheet: `[data-test="confirm"]` with `[data-test="confirm-yes"]` / `[data-test="confirm-no"]` |
| Alert | `alert` | `data-severity`, `data-count`, `data-verification-status`; `[data-test="countdown"]` (`role="timer"`, `aria-label` "Checking with Marco, N seconds left"), `[data-test="escalation-status"]` |
| StatusGrid | `status-grid` | cells `[data-test="status-cell"][data-label]` |
| ContactCard | `contact-card` | `data-kind`, `data-phone`, `data-member`; the call control is `a[href^="tel:"]` or `button` |
| SourceCard | `source-card` | `data-url` |
| DoseTracker | `dose-tracker` | rows `[data-test="dose-slot"][data-slot][data-status][data-via]`; `[data-test="dose-log"]` button when `allow_log`; med names only inside `[data-test="dose-meds"]` (must be absent on elder) |
| CareRota | `care-rota` | rows `[data-test="rota-day"][data-date][data-on-duty][data-backup][data-me]`; `[data-test="rota-swap"]` |
| Timeline | `timeline` | items `[data-test="timeline-item"][data-kind][data-superseded][data-event-id]`; `[data-test="provenance"]` |
| SymptomLog | `symptom-log` | option buttons `[data-test="symptom-option"][data-value]` |
| CallLog | `call-log` | `[data-test="call-row"]` |
| NeedBoard / ResourceBoard / VerifiedInfoFeed / CheckIn / Checklist | `need-board` / `resource-board` / `verified-info-feed` / `check-in` / `checklist` | rows `[data-test="board-row"][data-id][data-status]`; `[data-test="check-in-ok"]` |
| ScamCheck | `scamcheck` | `data-state` ∈ idle/choosing/checking/denied/timeout/confirmed; choice buttons `[data-test="scam-choice"][data-member]`, `[data-test="scam-other"]`; outcome text in `[data-test="scam-say"]` |
| IncidentCard | `incident` | per card `[data-test="incident-item"][data-incident-id][data-severity][data-status][data-verification-status]`; `[data-test="red-flag"]`; `[data-test="incident-ack"]` |
| LifeAreas | `life-areas` | chips `[data-test="life-area"][data-area][data-status-text]` |
| VerificationPrompt | `verification-prompt` | `data-verification-id`; `[data-test="verify-no"]`, `[data-test="verify-yes"]`, `[data-test="verify-unsure"]` (when offered); `[data-test="countdown"]`; after answer `[data-test="verify-thanks"]` |
| HelperAnswer | `helper-answer` | `data-is-my-turn`; `[data-test="helper-answer-text"]`; `[data-test="helper-status"]`; `[data-test="helper-next"]` |
| Proposal | `proposal` | `[data-test="proposal-item"][data-proposal-id][data-status]`; `[data-test="proposal-approve"]`, `[data-test="proposal-reject"]`; `[data-test="proposal-change"]`, `[data-test="proposal-evidence"]` |
| PillOrganizer | `pill-organizer` | cells `[data-test="pill-lid"][data-day][data-slot][data-status]` with `style="--lid: #…"`, `aria-label` "Tuesday evening taken" |
| PromptOverlay | `prompt-overlay` | `data-verification-id`, `role="dialog"`, `aria-modal`; buttons reuse `verify-no` / `verify-yes`; `[data-test="prompt-banner"]` ("Village is calling you · AI assistant") |
| NEW highlight | any element with `data-new="true"` for 2 s | Evolve acceptance (V4) |

### Pages
| Page | Selectors |
|---|---|
| Scan (`scan.html`) | `[data-test="scan-page"][data-tone=ok\|report\|error][data-slot]`; `[data-test="lid-status"]`; `[data-test="lid-chip"]` (`style="--lid"`); `[data-test="scan-headline"]`, `[data-test="scan-line"]`; `[data-test="read-aloud"]` |
| Join (`join.html`) | `[data-test="join-form"]`, `[data-test="join-role"]`, `input[data-test="join-name"]`, `input[data-test="join-phone"]`, `input[type=checkbox][data-test="join-consent"]`, `button[data-test="join-submit"]`, `[data-test="join-error"]` |
| Fact view | `[data-test="fact-view"][data-key]`, `[data-test="fact-current"]`, `[data-test="fact-history"]` rows `[data-test="fact-row"][data-superseded]`, `[data-test="fact-uncertain"]` with `[data-test="fact-option"]`, `[data-test="fact-back"]` |
| Print | `[data-test="print-page"]`, `[data-test="lid-sticker"][data-slot]`, `[data-test="sticker-qr"]`, `[data-test="fridge-card"][data-family-word-first]` |

### Control Room (`control.html`)
`[data-test="control"]`, `[data-test="village-tab"][data-village]`, `[data-test="phones-counter"]` (`data-value`), `[data-test="demo-clock"]` (`data-now`, `data-offset`), `[data-test="clock-warp"]`, `[data-test="blueprint"]` with `[data-test="blueprint-person"][data-member]`, `[data-test="blueprint-area"][data-area]`, `[data-test="blueprint-rule"]`, `[data-test="live-moment"]` + `[data-test="countdown"]`, `[data-test="release-strip"][data-release-id][data-result]` with `[data-test="stage-spec|daytona_build|tests|anchor_qa|arize_evals|live"][data-status]` and `[data-test="release-caught"]`, `[data-test="build-log"]`, `[data-test="anchor-live"]` (iframe, `data-url`), `[data-test="gate-feed"]` rows `[data-test="gate-row"][data-rule][data-decision]`, `[data-test="decisions-log"]` rows `[data-test="decision-row"]`, `[data-test="ask-why"]` with `input[data-test="ask-why-input"]`, `button[data-test="ask-why-send"]`, `[data-test="ask-why-answer"]`, `[data-test="ask-why-source"]`, `[data-test="join-qr"][data-member]`.

### Floor measurements (what FS-5's generated tests read)
- Elder: every `[data-test="bigbutton"]` `getBoundingClientRect().height ≥ 88` and `width ≥ 0.9 × viewport`; font-size of `[data-test="bigbutton"]`, `[data-test="screen-title"]`, `[data-test="alert"] [data-test="alert-title"]`, `[data-test="scam-say"]` ≥ 28 px; contrast of each text/background pair ≥ 7:1 (computed via `getComputedStyle` color/background walking up to the first opaque ancestor); `[data-test="dose-meds"]` absent; `[data-test="read-aloud"]` present; every `[data-tone="danger"]` button has `data-confirm="true"`.
- Everyone: interactive elements ≥ 48 × 48; contrast ≥ 4.5:1; colors `#A8331A`, `#2E6F42`, `#FCEFD6/#7A4B00` unchanged on `[data-tone]`/`[data-severity]`; every tone element contains an `svg[data-icon]` and visible text.
- Actions: clicking any `[data-test="bigbutton"]` produces exactly one `action` frame (fake WS records) and no `fetch` to anything but `/v/{id}/actions/*`.

## B. WS message handling table

| Message | Precondition | Kit behaviour | Observable (selector / frame) |
|---|---|---|---|
| `hello` (C→S) | socket open | first frame; `client` per entry (`kit`, `control`, `scan_page`) | — |
| `snapshot` | after hello / resync | replace view+data+now; `<html lang dir>`; theme attrs; clear `prompt` unless `verifications:pending?member=me` is non-null | `app[data-rev]` = rev; `ws-status=open` |
| `patch` | `base_rev == rev` | clone → `applyPatch(validate)` → zod → commit; `highlight[]` ⇒ `data-new` | `app[data-rev]` = patch.rev; new element present within 100 ms |
| `patch` | `base_rev != rev` | ignore; send `hello{last_rev}` | `ws-status=resync` then `open` after snapshot |
| `event` | live | merge `data` (null deletes); Control Room: feed panes | component re-renders from the binding |
| `prompt` | live, `closed` falsy | show PromptOverlay (dedupe by `verification_id`) | `prompt-overlay[data-verification-id]` |
| `prompt` | `closed: true` | dismiss overlay; mark VerificationPrompt closed | overlay absent |
| `result` | `pending[req_id]` exists | resolve/reject; show `decision.say[lang]` in the component; re-enable | `bigbutton[data-pending=false]`; `verify-thanks` |
| `result` | unknown `req_id` | ignore, console.warn | — |
| `control` | role = control | reducer by `kind` (reasoning/build_log/release/qa/gate/counter/clock) | region selectors above |
| `control` | member client | ignore | — |
| `pong` | — | clear dead-man | — |
| `error{bad_token\|contract_mismatch}` | — | close, no retry | `ws-status=closed[data-reason]` + join link |
| `error{bad_message\|not_allowed\|rate_limited}` | — | strip message 5 s; state unchanged | `reconnect-strip` text |
| socket `close` / dead-man | — | reject pending with `disconnected`; backoff 0.5→8 s ±20 %; reconnect with `last_rev` | `ws-status=reconnecting[data-attempt]` |
| `action` (C→S) | live | one frame per tap; `req_id = r_<member>_<n>`; button disabled until `result` or 10 s timeout | fake WS records; `data-pending` |
| `ack` (C→S) | live | from Alert/IncidentCard/escalation banner | — |
| `ping` (C→S) | live | every 15 s | — |

Frames the kit never sends: anything with `type` outside `hello|ack|action|ping`. Fields the kit never reads: `snapshot.spec.printables[].family_word` on non-coordinator roles (Core strips it; the kit also masks it outside `/print`).

## C. HTTP the kit calls (from `contracts/openapi.yaml`)
`POST /auth/redeem` (join) · `POST /v/{id}/actions/{name}` (fallback when the socket is down and the action is non-safety, e.g. `check_in_ok`; verification answers never use the fallback) · `GET /villages/{id}/qr` (control + print) · `GET /villages/{id}` (control, Fact view) · `POST /villages/{id}/ask` (control) · `POST /clock/warp` (control) · `GET /s/{slot_token}` with `Accept: application/json` (scan page fallback only).
