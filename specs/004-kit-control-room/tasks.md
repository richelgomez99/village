# Tasks: FS-4 Kit (generated apps + Control Room)

Lane `kit`, worktree `../village-kit`, branch `lane/kit`. Columns: **Ver** = version the task ships in (LAYERS.md), **Min** = planned minutes, **Deps**, **[P]** = can run in parallel with other [P] tasks in the same phase, **Acceptance** = the check the orchestrator runs (constitution: "tasks cite the acceptance check they satisfy"), **Principle**.

Rule: if a task runs 20 min over plan, stop and report (CLAUDE.md). Nothing in this file touches `contracts/` or another lane's folder.

## Phase V0 · 10:00–11:00 · "fixture specs render in 60 minutes"
| ID | Task | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T001 | Scaffold `kit/` (Vite react-ts, strict TS, deps per plan), `base:"./"`, four entries, `npm test` wired with vitest+jsdom | V0 | 6 | — | | `npm run build` produces 4 HTML entries | IX |
| T002 | `renderer/view.ts`: zod `view` schema (lang, theme, dir, root `s`, elements, needs_served) + `applyViewPatch(view, ops)` using `fast-json-patch` validate on a clone | V0 | 8 | T001 | [P] | `tests/patch.rev.test.ts`: fixture `proposal` ops on elder view yield 7 elements; bad path throws and view unchanged | V, VI |
| T003 | `renderer/Renderer.tsx` + `catalog.ts`: `Node` lookup, unknown ⇒ null + count, children only for Screen/Stack, `data-test`/`data-id` wrapper | V0 | 8 | T002 | [P] | `tests/renderer.unknown.test.tsx`: view with `CustomFoo` renders siblings, `unknown-types[data-count]=1` | V |
| T004 | `renderer/props.ts`: zod per type generated from `village_spec.schema.json#/$defs/props_*` by `scripts/gen-props.ts` (checked in) | V0 | 10 | T001 | [P] | `tests/props.schema.test.ts`: every element in `reyes_spec.json` and `block_spec.json` parses; `BigButton{tone:danger}` without `confirm` fails | V, VI |
| T005 | `theme/floor.css`, `village.css`, `fonts.css` with the exact tokens from plan.md; self-hosted woff2 subsets in `public/fonts/`; `[data-theme=elder]` light + sizes | V0 | 8 | T001 | [P] | `tests/elder.floor.smoke.test.tsx`: computed `min-height ≥ 88`, font-size ≥ 28 on bigbutton, bg `#FBF6EE` | V (D8) |
| T006 | Primitives: Screen (ReadAloud), Stack, Header, Text, BigButton (icons, tones, ConfirmSheet, `speak`), ContactCard (tel:), StatusGrid | V0 | 10 | T003, T005 | [P] | `?fake=carmen` shows 3 buttons + 911; danger tap opens confirm | V |
| T007 | Care components v0: Alert (severity filter, countdown, escalation line), DoseTracker (slots, lid chips, meds hidden on elder), HelperAnswer, Timeline (basic rows + provenance), CareRota (week rows) | V0 | 12 | T006 | [P] | `?fake=ana` and `?fake=marco` render all fixture elements, `unknown-types=0` | V, III |
| T008 | `live/messages.ts` (zod for server frames) + `live/ws.ts` state machine (hello, snapshot, patch rev gate, event merge, prompt, result, ping/pong, backoff 0.5→8 s) + `useLive` | V0 | 12 | T002 | [P] | `tests/ws.reconnect.test.ts` with a mock `WebSocket`: drop mid-session ⇒ reconnect with `last_rev`; `base_rev` mismatch ⇒ hello resent | VII, IX (D4) |
| T009 | `dev/fakeWs.ts`: in-browser server replaying `ws_sequence_scam.json` (`start` + `?tail=`), `lid_scan_sequence.json` (`?seq=lid`), proposal example (`?seq=evolve`), per `?fake=<client>`; records sent frames on `window.__frames` | V0 | 10 | T008 | | quickstart §2 table works offline | VI, VII |
| T010 | `scan.html` + `pages/scan.tsx`: LidStatus ok/report/error from inline JSON or JSON fetch; read-aloud; lid chip | V0 | 8 | T005 | [P] | `/scan.html?fixture=second` shows amber report text verbatim, no red | V, I |
| T011 | `acceptance/run.sh V0 --lane kit` hooks: `npm test` + headless render of three fixture roles (vitest) + selector presence list from contracts/README.md §A | V0 | 6 | T006–T010 | | V0 kit acceptance green; report to orchestrator | IV, VII |

**V0 exit (11:00):** fixture Reyes renders elder/coordinator/helper; lid-scan frames update all three fake tabs; scan page shows the two wordings; `unknown-types=0`; tests green.

## Phase V1 · 11:00–12:15 · verification on a phone
| ID | Task | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T012 | VerificationPrompt (binding-driven, countdown, yes/no/unsure, pending state, thanks state from `result.decision.say`) | V1 | 12 | T007, T008 | [P] | `?fake=marco` tap `verify-no` ⇒ one `action` frame with payload `{verification_id, answer:"no"}`; `verify-thanks` text equals fixture `say.en` | I, V |
| T013 | PromptOverlay for the `prompt` frame ("Village is calling you · AI assistant", dialog, shares answer path; `closed:true` dismisses) | V1 | 8 | T012 | [P] | overlay appears at `start`, dismisses on `denied`/`timeout_tail` closed frame | II |
| T014 | IncidentCard (3 outcomes, red flags, provenance, ack ⇒ `ack_incident`) | V1 | 10 | T007 | [P] | `?fake=ana&tail=denied` shows "Scam stopped"-class card with `data-verification-status=denied`; ack sends frame | III |
| T015 | Alert countdown + ScamCheck states (idle/choosing/checking/denied/timeout/confirmed from `verifications:mine`, chooser from `choices_member_ids`, `start_verification` action) | V1 | 12 | T007 | [P] | states render from a hand-built `bv_my_verification` set; `?fake=carmen` countdown reaches 0:00 and waits | V, I |
| T016 | `join.html` + `pages/join.tsx`: form, consent copy, `POST /auth/redeem`, token to storage, URL scrub, error state | V1 | 10 | T008 | [P] | `/join.html?fake=marco` submit ⇒ redirect connected as marco; empty name disables submit | II |
| T017 | i18n: `es.json`/`en.json` for all kit-owned strings; `t(localized, lang)` fallback; RTL smoke with a `dir:rtl` fixture view; long-string wrap test | V1 | 8 | T006 | [P] | `tests/i18n.rtl.test.tsx`: `<html dir=rtl>`, 60-char label wraps, button height ≥ 88 | V |
| T018 | Read-aloud: Screen summary builder per component (`aria-label` summaries), `speechSynthesis` on gesture, cancel on second tap | V1 | 6 | T006 | | manual: Carmen view speaks title + alert + buttons in es | V |
| T019 | V1 acceptance hooks: scam fixture replay through the real `/ws` (Core stub) on two tabs; Anchor-ready selectors verified by a Playwright smoke at 390×844 (`kit/tests/e2e.smoke.ts`, optional) | V1 | 8 | T012–T016 | | `acceptance/run.sh V1 --lane kit` green | IV |

## Phase V2 · 12:15–13:00 · Control Room, blueprint, three apps
| ID | Task | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T020 | `theme/a.css` (Direction A tokens) + `control.html` + `pages/control.tsx` shell: header (tabs, `phones-counter`, `demo-clock` + warp), 12-col grid, scene reducer | V2 | 12 | T008 | | `/control.html?fake=control` renders header + regions; counter follows `control{counter}` | VIII |
| T021 | Blueprint region ("What the agent heard"): quote with life-area highlights, people cards with channels, rules, "Building now", fed by `control{reasoning}` + snapshot blueprint | V2 | 12 | T020 | [P] | fixture `block_spec.json` shows different areas/people without code change | VIII, V |
| T022 | Live-moment region: quote, waveform, countdown ring, Village node, flow lines; triggered by `control{gate}` money decision; off under reduced motion | V2 | 10 | T020 | [P] | `start` replay shows the ring at 0:45→0:00; `denied` collapses it | VIII |
| T023 | Three-phones region: whole-spec snapshot rendered as three read-only `Renderer`s (actions disabled) in bezels; optional iframes when Core mints projector tokens (research Q4) | V2 | 10 | T020, T007 | [P] | three views visible, elder light inside dark frame | V |
| T024 | Safety-gate feed + DecisionsLog (`control{gate}`, `control{reasoning kind:decision}`) | V2 | 8 | T020 | [P] | rows appear newest-first with rule ids | VIII, I |
| T025 | Ask Village why box: `POST /villages/{id}/ask`, answer + source chips, disabled in flight | V2 | 8 | T020 | [P] | mocked endpoint returns `{answer, sources}` ⇒ rendered; empty question ignored | VIII, II |
| T026 | Join QR tiles region (`GET /villages/{id}/qr`, `qrcode.react` fallback from URLs) | V2 | 6 | T020 | [P] | three tiles, "Be Marco" highlighted sage | II |
| T027 | LifeAreas + PillOrganizer (default) + StatusGrid polish for the coordinator; CareRota swap; Timeline event-kind aliases | V2 | 10 | T007 | [P] | `?fake=ana` matches `Family.dc.html` structure; `pill-lid` cells carry `--lid` colors | V |
| T028 | PWA: `vite-plugin-pwa` config, manifest, icons, denylist, iOS hint, offline shell restoring last snapshot (actions disabled) | V2 | 8 | T001 | [P] | Lighthouse "installable"; airplane mode shows last view with "last seen" strip | IX |
| T029 | V2 acceptance: Control Room replays `start`+`denied`; blueprint from both fixtures; `acceptance/run.sh V2 --lane kit` | V2 | 5 | T020–T028 | | green | IV |

## Phase V3 · 13:00–13:40 · receipts
| ID | Task | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T030 | `ReleaseStrip` (6 stages, statuses, caught line, repair link, evidence/trace links) from `control{release}`; `build-log` pane from `control{build_log}`; Anchor live-view iframe from `control{qa}.live_view_url` | V3 | 14 | T020 | | replay `rel_reyes_r3` then `r4` ⇒ tomato "rev 3 caught: contrast 4.1:1…" then sage Live | IV, VIII |
| T031 | Block village (`block_spec.json`) components: NeedBoard, ResourceBoard, VerifiedInfoFeed, CheckIn, Checklist, SourceCard, SymptomLog, CallLog rendering from fixture data shapes (`?fake=tanya`) | V3 | 14 | T007 | [P] | all block elements render, `unknown-types=0`; "Not confirmed · not sent" chip on unverified claims | V, I |
| T032 | Village-tab switch on the Control Room (Reyes ↔ West 147th) using two control snapshots; "Generated 1:12 PM · same pipeline · trace ↗" caption from receipt | V3 | 6 | T030, T031 | | tab switch < 300 ms, no reconnect | VIII |
| T033 | V3 acceptance: receipts strip from the release lane's real `control{release}` frames | V3 | 4 | T030 | | `acceptance/run.sh V3 --lane kit` green | IV |

## Phase V4 · 13:40–14:15 · Evolve live, Fact view, printables
| ID | Task | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T034 | Patch highlight (`data-new`, 2 s, `aria-live`, reduced-motion off) + "NUEVO/NEW" tag on ScamCheck/IncidentCard | V4 | 6 | T008 | [P] | `?seq=evolve` elder gains ScamCheck with `data-new=true` | V |
| T035 | Proposal card (changes, evidence labels, release status, approve/reject actions, verifying state) | V4 | 10 | T007 | [P] | approve sends `action{name:"approve_proposal", arg}`; `status: verifying` disables | II |
| T036 | Fact view (`pages/fact.tsx`): current, history with superseded rows, "Needs a person" block with options as gated actions; entry from Timeline/provenance | V4 | 12 | T007 | [P] | `Fact.dc.html` states render from a hand-built fact object; back returns to the dashboard without reconnect | III, II |
| T037 | Printables (`pages/print.tsx` + `print.css`): two lid stickers with QR, fridge card (`family_word_first` ordering), cut lines, letter size; family word masked elsewhere | V4 | 10 | T026 | [P] | print preview matches `Kit.dc.html`; `fridge-card[data-family-word-first]` flips with the `spec_ops` example | II, III |
| T038 | V4 acceptance: live patch on three real phones via Core (`POST …/approve` ⇒ patch), Fact view opens from an incident | V4 | 6 | T034–T037 | | `acceptance/run.sh V4 --lane kit` green | IV, VII |

## Freeze · 14:15–15:00 · hardening only
| ID | Task | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|
| T039 | Projector pass at 1920×1080 / 150 % zoom; font sizes `clamp()`; fallback lines visible ("Reconnecting…") | — | 10 | T030 | [P] | manual on the mirrored display | VII |
| T040 | Bundle budget check (`vite build` sizes), remove dead components from entries that don't use them (scan/join entries ≤ 60 kB gz) | — | 6 | T001 | [P] | sizes printed ≤ budget | IX |
| T041 | `kit/README.md`: run, test, selectors table (copy of contracts/README.md §A), fake WS URLs | — | 6 | — | [P] | file present; FS-7 links it | VIII |

After 15:00 nobody touches `kit/` on the demo path (constitution VII).

## Dependency graph (critical path)
T001 → T002 → T003 → T006 → T007 → T012/T014/T015 → T020 → T030 → T034/T035 → T038. T008 (WS) and T004 (props) run in parallel with T003–T007 and must land before T009/T011.

## Parallel execution example (V0, two subagents)
- Agent A: T001 → T002 → T003 → T006 → T007 → T011.
- Agent B (after T001): T004, T005, T008, T009, T010 in that order.
Both report at 10:50 with `npm test` output and the quickstart §2 table checked.

## Addendum (D18, Oct 16 ~3:30am): captions and concrete copy
- T042 [kit, V2, 25 min] Control Room caption layer: every Spanish string rendered on projector surfaces (Control Room mirrors, Founding, Rebuild, scam moment) gets an English caption beneath in muted type; captions come from the spec's `localized` fields (es/en) or, for live call turns, from `control{kind: caption}` frames (ElevenLabs transcript → Claude translation in Core, ≤1 s). Acceptance: no Spanish-only text visible on any projector surface in `acceptance/v2.sh` screenshots. Principle V, VIII.
- T043 [kit, V0–V4, ongoing] Copy rule: no abstract verbs on screen ("reads its traces", "what could go wrong"); every panel states the specific thing with a number or a name. Source copy: `design/*.dc.html` (updated). Acceptance: pitch-lane review at each version tag.

## Addendum (D21): identity-driven views, visibly
- T044 [kit, V2, 20 min] Identity chip component on every member view ("You're Marco · Reyes village" / "You're family"), bound to `member:me`. Principle V.
- T045 [kit+core, V2, 30 min] Control Room "View as" switcher (Carmen / Ana / Marco): sends `hello{view_as: member_id}` on an admin WS session; Core re-issues that member's snapshot; the projector app morphs in place (no reload). The three-apps screen shows the shared URL above the phones. Acceptance: switching views changes components/language/theme within 1 s; captured in `acceptance/v2.sh`. Principle VIII.

## Addendum (D22): refill card, no lid pages
- Replace `LidStatus`/scan page tasks with `RefillCard` (helper/coordinator): "Sunday refill · Marco · lisinopril 10 mg (changed Oct 3, Dr. Lee; was 5 mg) · metformin 500 · atorvastatin 20 · apixaban 5", bound to `prescriptions:current` with the superseded line struck through. Elder view = 3 BigButtons: Llamar a Village · Llamar a Ana · Necesito ayuda, plus "Esta noche cuida Marco". Printables = fridge card only.

## Addendum (D24): P2 component, design-only P3 boards
- T046 [kit + watcher, P2 only if V4 green by 14:00, 25 min] `HandoffCard`: at each rota turn change the Watcher composes one `ChatMessage` kind `relayed` to the incoming caregiver from the day's events; same text as "Since the last turn" on their home card. No new table (`source: events[]`).
- Boards only (no code today): Charter, Needs, Modes, GuestNote, MyVillageKnows, Digest, Handoff. See `docs/VILLAGE-FEATURES.md` and `design/INTERACTIONS.md`.
