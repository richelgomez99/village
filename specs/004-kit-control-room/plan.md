# Implementation Plan: FS-4 Kit (generated apps + Control Room)

**Branch:** `lane/kit` · **Spec:** `specs/004-kit-control-room/spec.md` · **Contract:** 1.0.0
**Stack (CLAUDE.md, do not substitute):** Vite 7, React 19, TypeScript 5, `fast-json-patch`, `zod` 4, `qrcode.react`, `vite-plugin-pwa` 1.x, `vitest` (+ `@testing-library/react`) for the kit's own tests.

## Technical context
- **Language:** TypeScript strict. **Build:** `vite build` (multi-entry). **Test:** `vitest` + jsdom for renderer/WS/props tests; the generated *floor* tests belong to FS-5 and run in the Daytona sandbox against this bundle.
- **Serving:** Core serves `kit/dist/` (ARCHITECTURE-VALIDATION §4.1: download `dist/` from the sandbox after tests pass); FS-5's sandbox runs `vite preview --port 4173` from the same project layout. Asset paths are relative (`base: "./"`).
- **Realtime:** one WebSocket (D4). No SSE. No direct SurrealDB.
- **Targets:** 390×844 phones (Anchor viewport), 1920×1080 projector at 150 % zoom.
- **Constraints:** no router, no UI library, no CSS-in-JS; JS ≤ 250 kB gz per entry.

## Constitution re-check (post-design)
V: catalog-only renderer + `floor.css` with `!important`-free but non-overridable custom properties (village layer sets only `--accent`, `--lid-*`, relationship words). VIII: Control Room renders only Core-sent messages; counters never seeded client-side. IX: single bundle, single socket. PASS.

## Project structure

```
kit/
  package.json              vite.config.ts  tsconfig.json  index.html  scan.html  join.html  control.html
  public/                   icon-192.png icon-512.png apple-touch-icon.png (placeholders at V0)
  src/
    main.tsx                member app entry (App → Renderer; in-app pages: fact, print)
    pages/scan.tsx          LidStatus page (reads inline JSON or fetches with Accept: application/json)
    pages/join.tsx          Join + consent → POST /auth/redeem
    pages/control.tsx       Control Room
    pages/fact.tsx          Fact view (current, history, needs-a-person)
    pages/print.tsx         printables (stickers + fridge card)
    renderer/
      Renderer.tsx          <Node id> lookup, unknown → null, highlight ring
      catalog.ts            CATALOG: Record<string, Component> (26 + ReleaseStrip, DecisionsLog)
      props.ts              zod schemas per type, derived from village_spec.schema.json
      view.ts               zod for view, applyPatch(view, ops) with validation
      binds.ts              useBind(bind) → data[bind]; localized() helper
    live/
      ws.ts                 VillageSocket (state machine, backoff, ping/pong, req_id map)
      useLive.ts            React hook: {state, rev, view, data, now, prompt, send, ack}
      messages.ts           zod for every server message (ws_messages.schema.json)
    components/             one file per catalog type (Screen.tsx … PillOrganizer.tsx), ReleaseStrip.tsx, DecisionsLog.tsx, PromptOverlay.tsx, Countdown.tsx, ReadAloud.tsx, ConfirmSheet.tsx
    theme/
      floor.css             locked tokens + sizes (D8)
      village.css           village-layer variables (accent, lid colors), applied via data attributes
      a.css                 Direction A (Night Watch) tokens for the Control Room
      fonts.css             Fraunces, Atkinson Hyperlegible, Noto Sans fallbacks, JetBrains Mono
      print.css
    i18n/es.json en.json    reviewed kit-owned strings only
    util/time.ts            countdown against server `now` + local drift; Intl formatting
  dev/
    fakeWs.ts               replays fixtures per client (?fake=marco|carmen|ana|control|scan)
    fixtures/ → ../../contracts/fixtures (symlink or copy at build)
  tests/                    vitest: renderer.unknown.test.tsx, patch.rev.test.ts, ws.reconnect.test.ts, props.schema.test.ts, elder.floor.smoke.test.tsx, i18n.rtl.test.tsx
```

Docs (FS-7 owns `docs/`; this lane contributes `kit/README.md` only: run, test, selectors).

## Component props table (derived from `village_spec.schema.json#/$defs/props_*`)

| Type | Required props | Optional props | Binds / data read | Built-in action |
|---|---|---|---|---|
| Screen | title | subtitle, read_aloud | — | — |
| Stack | — | direction, gap, title | — | — |
| Header | text | level (1–3) | — | — |
| Text | text (≤280) | size m/l/xl, tone | — | — |
| BigButton | label, action | action_arg, icon, tone, confirm, confirm_text, speak | — | `action{name, arg}`; danger ⇒ ConfirmSheet |
| Alert | source, bind | severity_levels, dismissible, empty_text, show_escalation_status, show_countdown | `alerts:active` → `bv_alert[]` | dismiss (local) |
| StatusGrid | labels[], binds[] | title | each `…?count` → number | — |
| ContactCard | name, kind (+ phone \| member_id \| bind) | label, big | `member:<id>` → `bv_person` | `call_member` / `call_number` (tel: link + action) |
| SourceCard | source_name, url | refresh_minutes, bind | `claims:topic=…` | — |
| DoseTracker | subject, slots[], bind | title, show_med_names, allow_log, big | `facts:dose_event?…` → `bv_dose_day` | `log_dose{arg: slot:<id>}` if allow_log |
| CareRota | bind | title, period, highlight_current_user, allow_swap, show_backup | `rota:week|current` → `bv_rota_day[]` | `swap_shift` |
| Timeline | bind | title, subject, event_kinds[], show_superseded, show_provenance, limit | `timeline:subject=…` → `bv_timeline_item[]` | opens Fact view |
| SymptomLog | subject, fields[], bind | title, options[], allow_voice_entry, big | `facts:symptom?…` | `report_symptom{payload}` |
| CallLog | line_ids[], bind | title, show_policy_decisions, limit | `calls:line=…` | — |
| NeedBoard | bind, priority_order[] | title, show_fields, redact_for_roles, allow_match | `needs:open|matched` | `approve_match` |
| ResourceBoard | bind | resource_types, title, show_constraints | `resources:available` | `offer_resource` |
| VerifiedInfoFeed | bind, topics[] | title, trust_levels_shown, hide_unverified_for_roles | `claims:topic=…` | `check_rumor` |
| CheckIn | subjects[], bind | title, interval_minutes, escalate_after_minutes, big | `checkins:village|overdue` | `check_in_ok` |
| Checklist | items[] | title, owners[], recurring, bind | — | local check state (no write) |
| ScamCheck | label, choices_member_ids[], bind=`verifications:mine` | other_label, speak, big | `bv_my_verification` → states idle / checking / denied / timeout / confirmed | `start_verification{arg: member_id|other}` |
| IncidentCard | bind | title, subject, show_red_flags, show_verification, show_provenance, allow_ack, limit | `incidents:open|subject=…` → `bv_incident[]` | `ack_incident{arg}` |
| LifeAreas | bind=`blueprint:life_areas`, areas[] | title, show_rules, show_contacts | `bv_life_area[]` | — |
| VerificationPrompt | bind=`verifications:pending?member=me`, yes_label, no_label | question_template, show_countdown | `bv_pending_prompt` (null ⇒ renders nothing) | `answer_verification{payload}` |
| HelperAnswer | question, bind | subject, show_status, show_next_shift | `rota:current?member=me` → `bv_rota_me` | — |
| Proposal | bind | title, allow_approve, show_evidence, show_release_status | `proposals:pending` → `bv_proposal[]` | `approve_proposal` / `reject_proposal{arg}` |
| PillOrganizer | subject, slots[], lid_colors[], labels[], bind | title, days[], show_today_only | `facts:dose_event?…valid_at=week` → `bv_dose_week` | — |
| ReleaseStrip (control) | receipt | — | `control{release}` | — |
| DecisionsLog (control) | rows | — | `control{reasoning kind=decision}` | — |

Parallel arrays (`labels`/`binds`, `slots`/`lid_colors`/`labels`) are zipped at render; length mismatch ⇒ the element renders nothing (FR-003).

## Theme tokens (exact values from `design/*.dc.html`)

**Floor, light (B "paper") — `floor.css`:**
`--paper #FBF6EE` · `--card #FFFFFF` · `--ink #26211C` (elder views: `--ink #1F1A15`, `--ink2 #4A423A`) · `--ink2 #5B5249` · `--line #E5DACB` (join inputs `#CDBFAD`; print `#CFC3B3`) · safety: `--tomato #A8331A` (stopped / needs help, white text) · `--tomato-soft #FBE6DF` · `--ok #2E6F42` (recorded) · `--ok-soft #E4F1E6` · `--amber-soft #FCEFD6` + `--amber-ink #7A4B00` (needs a person) · `--sage #2F6B57` · `--sage-soft #E3EFE8` · `--plum #6A3F7A` · `--plum-soft #F1E7F4` · `--violet-soft #ECE6F5` · `--blue-soft #E3ECF8` · `--blue-ink #234C8A` · `--gray-soft #ECEAE5` · `--night #1E1A16` · `--night2 #2B2520` · `--lid-blue #2F5FA7` · `--lid-yellow #E8B12F`.
Fonts: `--display 'Fraunces', Georgia, serif` · `--body 'Atkinson Hyperlegible','Noto Sans',system-ui,sans-serif` · `--mono 'JetBrains Mono',ui-monospace,monospace` · `--hand 'Caveat'` (thumbnail/slides only).
Sizes (floor): elder title 40 px / 650 (Carmen.dc), elder BigButton `min-height: 104px` (floor minimum 88 px), elder label 28 px / 700 (floor; artboards show 22–25 px, see research §Q1), elder secondary 22 px, radius 16–20 px, border 3 px on soft buttons; family/dashboard: title 30 px, card radius 16–18 px, body 15–17 px, chips 12–13 px uppercase; tap target min 48 px everywhere; VerificationPrompt "no" button `min-height 68px` on Marco's page (60 px inside cards); Proposal buttons 48–54 px.
Contrast pairs verified ≥ 7:1 for elder: `#1F1A15` on `#FBF6EE`, white on `#A8331A`, white on `#2E6F42`, `#7A4B00` on `#FCEFD6`, `#1F1A15` on `#E3EFE8`. (FS-5 measures these; the kit must not drift.)

**Village layer — `village.css` (data attributes set from the spec):** `--accent` ∈ {`#2F6B57` Reyes sage, `#2F6F8F` sky, `#6A3F7A` plum, `#2F5FA7` blue} from `village.theme.accent`; `--accent-soft` computed table (sage→`#E3EFE8`, sky→`#E3ECF8`, plum→`#F1E7F4`, blue→`#E3ECF8`); `--lid-<slot>` from `PillOrganizer.lid_colors` / `printables[].color`; relationship words from `theme.relationship_words[member][lang]`; density from `view.theme` (`elder | family | dashboard`); `lang`/`dir` on `<html>`.

**Direction A (Night Watch) — `a.css`, Control Room only:** `--night #100D0A` · `--panel #1B1612` · `--panel2 #241D17` · `--line #3A3028` · `--text #F3EADF` · `--muted #B5A898` · `--amber #F2A541` (countdown, flow lines) · `--coral #FF7A59` (LIVE dot, the quoted amount) · `--mint #62D9A0` (rule bullets) · links `#F2A541`/hover `#FFC37A` · phone mock-ups inside stay light (`#FBF6EE` on a `#2C2621` 10 px bezel). Animations: `pulse 1.2s` (live dot), `flow 1s linear` (dashed amber connectors); both off under reduced motion.

**Direction B (Kitchen Table) — not in the kit;** used by FS-7 for thumbnail/slides: `--table #E4D3BA`, `--grain #DCC9AD`, `--paper #FFFCF6`, `--ink #2A231C`, `--amber #C9821B`, `--pen #1D3F8F`, Caveat 600.

## WS client state machine (`live/ws.ts`)

States: `idle → connecting → hello_sent → live(rev) → resync → reconnecting(attempt n) → closed(reason)`.

| From | On | To | Side effects |
|---|---|---|---|
| idle | `connect()` | connecting | `new WebSocket(url)`; url = `${CORE_WS}/ws?village=${v}&m=${token}` |
| connecting | `open` | hello_sent | send `hello{contract_version:"1.0.0", village, member_token, last_rev?, client}` |
| hello_sent | `snapshot` | live(rev) | replace view+data+now; clear pending prompt if not in data; emit `ready` |
| hello_sent | `error{bad_token\|contract_mismatch}` | closed(reason) | no retry; UI shows join link |
| live | `patch` with `base_rev == rev` | live(patch.rev) | clone → applyPatch(ops, validate=true) → zod → commit; highlight ids |
| live | `patch` with `base_rev != rev` | resync | send `hello{last_rev: rev}` |
| live | `event` | live | merge `data` keys (null deletes); append to local event ring (Timeline uses binding, not ring) |
| live | `prompt` | live | `closed ? dismiss(verification_id) : show(prompt)` |
| live | `result{req_id}` | live | resolve pending[req_id]; `ok:false` ⇒ reject with `error` |
| live | `control` | live | Control Room reducer only (ignored by member clients) |
| live | `pong` | live | clear dead-man timer |
| live | 15 s tick | live | send `ping{ts}`; arm 10 s dead-man |
| any open | `close` / dead-man | reconnecting(n) | reject all pending with `disconnected`; wait `min(8000, 500·2^n) ± 20 %`; then connecting with `last_rev` |
| resync | `snapshot` | live(rev) | as above |
| reconnecting | `connect` ok | hello_sent | — |
| any | `error{bad_message\|not_allowed\|rate_limited}` | same | surface in `ws-status` strip; no state change |

Pending actions: `Map<req_id, {resolve, reject, element_id, sentAt}>`; `req_id = r_<member>_<counter>` matching `^[A-Za-z0-9_-]{4,64}$`. Server `now` is stored with `Date.now()` drift so countdowns use `deadline - (now + drift)`.

## Control Room layout regions (`pages/control.tsx`, Direction A, 1440×900 from `Main.dc.html` arrangement)

| Region | Grid | Source messages | Component |
|---|---|---|---|
| Header | full width | `control{counter}`, `control{clock}`, snapshot spec `village.name` | village tabs (Reyes / West 147th), `data-test="phones-counter"`, `data-test="demo-clock"` + "+30 min" (`POST /clock/warp`) |
| A · "What the agent heard" | cols 1–4 | `control{reasoning source:builder kind:plan\|note}`; snapshot `blueprint` | Blueprint assembling: quoted description with life-area highlights (health amber-soft, money tomato-soft, people sage-soft), people cards with channels, "Safety rules switched on", "Building now" |
| B · Three phones | cols 5–9 top | member snapshots are not visible to control; the Control Room embeds three `<iframe>`s of `/` with fake-free member tokens Core mints for the projector (`GET /villages/{id}/qr` JSON) | Carmen / Ana / Marco bezels, light inside |
| C · Live moment | cols 5–9 overlay | `control{gate}` with `decision.verification`, `event verification_*` | Scam-moment layout from `DirA`: quote, waveform, countdown ring (`role="timer"`, amber conic), Village node, flow lines to the two phones |
| D · Rebuild pipeline | cols 5–9 bottom | `control{release}` receipt, `control{build_log}`, `control{qa}` | `ReleaseStrip` (6 stages spec → daytona_build → tests → anchor_qa → arize_evals → live; status colors ok-soft/tomato-soft/sage; "rev 3 caught: contrast 4.1:1… Fixed in rev 4") + build log `<pre>` (night bg, mono 13 px) + Anchor live view iframe (390/600 aspect) |
| E · Safety gate feed | cols 10–12 top | `control{gate}` | cards: tomato-soft "Scam stopped", ok-soft "Recorded evening dose"; footer "Every decision is code, tested with the model off · traced in Arize" |
| F · DecisionsLog | cols 10–12 middle | `control{reasoning kind:decision}` | night card, mono timestamps, newest first, `data-test="decisions-log"` |
| G · Ask Village why | cols 10–12 bottom | `POST /villages/{id}/ask` | input + answer + source chips, `data-test="ask-why"` |
| H · Join | cols 5–9 (V2 founding) | `GET /villages/{id}/qr` | three QR tiles (Ana, Be Marco highlighted sage, Mom line number) |

Region visibility is driven by a `scene` reducer (`founding | live | rebuild | anyone`) advanced by message kinds (first `reasoning` ⇒ founding; `gate money_request` ⇒ live; `release in_progress` ⇒ rebuild) and overridable with keys 1–4 for the presenter.

## Build / preview commands
```
cd kit && npm ci
npm run dev                      # vite dev, http://localhost:5173/?fake=marco (fake WS)
npm run dev -- --host            # phones on the same Wi-Fi
VITE_CORE_URL=http://localhost:8787 npm run dev     # real Core
npm test                         # vitest run
npm run build                    # → kit/dist (index, scan, join, control)
npm run preview -- --port 4173   # what FS-5's sandbox runs
```
`vite.config.ts`: `base: "./"`, `build.rollupOptions.input = {index, scan, join, control}`, `VitePWA({registerType:"autoUpdate", workbox:{navigateFallbackDenylist:[/^\/ws/,/^\/v\//,/^\/s\//,/^\/villages/,/^\/auth/,/^\/tools/,/^\/hooks/]}, manifest:{name:"Village", short_name:"Village", id:"/", start_url:"/?source=pwa", display:"standalone", orientation:"portrait", background_color:"#FBF6EE", theme_color:"#2F6B57", lang:"es", icons:[192, 512 maskable]}})`.

## How FS-5 consumes the kit (the bundle contract)
1. FS-5's `sandbox/` template copies `kit/` (sources, not `dist/`) into the Daytona snapshot `village-kit` with `node_modules` pre-installed.
2. Per release it writes the build pack into `kit/village/`: `theme.json` (accent, lid colors, relationship words), `i18n/<lang>.json` overlays, `manifest.json` fragment, `custom/PillOrganizer.tsx` (generated; the kit's `catalog.ts` imports `./village/custom/index.ts` which exports `{}` by default), and `tests/floor/*.test.ts` (generated floor tests that import the catalog and render each role view from the spec at 390×844).
3. It runs `vite build && vitest run` then `vite preview --port 4173`; Anchor drives `/scan.html?fixture=…` and `/?m=<test token>` against a mock Core or the real one.
4. On pass, Core downloads `dist/` and serves it at `published_rev`; the live spec still comes from Core over `/ws`, so a bundle only changes when custom components, theme or tests change (D7).
Selectors the generated tests use are frozen in `contracts/README.md` of this spec; changing one is a contract change (orchestrator).

## Risks and mitigations
- Artboard copy vs gate `say`: the kit shows gate text; artboard strings are only used for kit-owned chrome (headings, buttons, hints).
- Fonts offline at the venue: self-host woff2 in `public/fonts/` (Fraunces, Atkinson, JetBrains Mono subset); Noto Sans falls back to system.
- iOS speech and vibration: speak only on gesture; `vibrate` guarded.
- Projector zoom: Control Room uses `clamp()` type and a 12-col grid; tested at 150 % zoom.
