# Research: FS-4 Kit

Each entry: decision · rationale · alternatives considered. Sources are local (`research/generative-ui.md`, DECISIONS.md, contracts, design artboards).

## R1. Renderer shape: our own A2UI-flavoured flat adjacency list
- **Decision:** `view{lang, theme, dir, root:"s", elements{id→{type, props, children?}}}` rendered by a ~60-line `Node` component; unknown `type` ⇒ `null`.
- **Rationale:** `research/generative-ui.md` compared A2UI v0.9.1, json-render, AI SDK 6, AG-UI, MCP Apps, Thesys. The flat list is what Claude emits without recursive schemas, is trivially patchable with RFC 6902, and keeps safety in the catalog. No runtime dependency to debug at 14:00.
- **Alternatives:** `@json-render/react` (closest; rejected for API learning curve under the clock and because the contract already fixes the shape); A2UI React renderer (maturity unverified).

## R2. One WebSocket, snapshot + patch, rev-gated
- **Decision:** exactly as `ws_messages.schema.json`: `hello` first, `snapshot` on connect and after any gap, `patch` applied only when `base_rev == rev`, `event.data` merges bindings so the kit never computes them.
- **Rationale:** D4 (quick tunnels buffer SSE; WS passes in 10–20 ms). Rev gating makes dropped frames safe: the worst case is a resync, never a wrong screen.
- **Alternatives:** SSE (rejected D4); applying patches optimistically (rejected: a wrong screen for Carmen is worse than a 200 ms resync).

## R3. `fast-json-patch` with `validate=true` on a structural clone
- **Decision:** `applyPatch(structuredClone(view), ops, true, false).newDocument` then zod `view` parse; any throw ⇒ discard and resync.
- **Rationale:** the library is on the mandated stack; `validate` catches bad paths (`/elements/s/children/99`) before they corrupt state; cloning keeps React state immutable.
- **Alternatives:** hand-rolled apply (no); mutate in place with `mutateDocument=true` (breaks React re-render guarantees).

## R4. Zod props schemas derived from the contract, not hand-written
- **Decision:** a `scripts/gen-props.ts` (dev-time) reads `contracts/schemas/village_spec.schema.json#/$defs/props_*` + `common.schema.json` leaf defs and emits `renderer/props.ts`; checked in, regenerated on contract bump. Union discriminated on `type`.
- **Rationale:** FR-003 and principle VI; a drift between pydantic (Core) and zod (kit) would let a bad element through on one side only. json-render's `catalog.prompt()` idea in reverse.
- **Alternatives:** write zod by hand (fast at first, drifts by 13:00); `json-schema-to-zod` at runtime (bundle weight, slow).

## R5. Floor as CSS custom properties in `floor.css`, village layer as data attributes
- **Decision:** floor tokens (safety colors, sizes, contrast pairs) live in `floor.css` on `:root` and `[data-theme=elder]`; the village layer only sets `--accent`, `--accent-soft`, `--lid-<slot>` and strings, via `data-accent` and inline `style` on the Screen. No mechanism exists for the spec to set arbitrary CSS.
- **Rationale:** D8 "fixed floor + village layer", principle V ("cannot be themed away"). Generated tests (FS-5) read computed styles through the frozen selectors.
- **Alternatives:** theme object in JS merged with spec (rejected: too easy for a generated value to override a floor size).

## R6. Elder view: always light, high-contrast, no dark mode
- **Decision:** `[data-theme=elder]` ignores `prefers-color-scheme`; 7:1 pairs listed in plan.md.
- **Rationale:** PRODUCT §1 and constitution V: "the elder view is always light and high-contrast". Low-vision users do worse with dark inverted UIs at small phone sizes under kitchen lighting.
- **Alternatives:** respect OS dark mode (rejected by decision).

## R7. Speech: `speechSynthesis` on gesture only; `speak` before action
- **Decision:** `ReadAloud` button on every Screen (`aria-label` from i18n), speaks title + accessible summaries in `view.lang`; `BigButton.speak` is spoken on tap, before sending the action, and never describes an outcome. Scan page speaks `page.read_aloud` after the first tap on iOS, immediately elsewhere.
- **Rationale:** iOS requires a user gesture; the builder prompt forbids `speak` as an outcome; outcome text is gate-owned (FR-009).
- **Alternatives:** ElevenLabs TTS in the kit (rejected: network dependency on the safety path, cost, latency).

## R8. Countdown against server `now`
- **Decision:** store `drift = Date.parse(snapshot.now) - Date.now()`; countdown = `deadline - (Date.now() + drift)`; stops at 0:00 and waits for the gate's event.
- **Rationale:** demo time-warp (`POST /clock/warp` broadcasts `control{clock}`); phones' clocks differ; silence must be safe (the kit never writes "denied").
- **Alternatives:** local clock (wrong under warp); server pushes each second (wasteful).

## R9. Scan page: Core-rendered shell, kit-built page
- **Decision:** `scan.html` is a kit entry; Core's `GET /s/{token}` returns this HTML with `<script id="lid-scan" type="application/json">{LidScanResult}</script>` injected. If the inline JSON is missing (dev), the page fetches the same URL with `Accept: application/json` (safe: the 10 s dedupe guarantees no second ledger row).
- **Rationale:** `lid_scan.schema.json` says the route renders a one-screen HTML page; the kit owns the look; no LLM, no WS needed for the scan page (it may connect later for live confirmation, but the decision is already made server-side).
- **Alternatives:** scan page as an SPA route (needs the token in JS before the decision; worse on slow phones).

## R10. Join page: `POST /auth/redeem`, token kept out of the address bar
- **Decision:** after redeem, token goes to `sessionStorage` + `localStorage` (so the PWA reopens), URL rewritten with `history.replaceState`. Consent copy is the reviewed `design/Join.dc.html` text.
- **Rationale:** D11; FR-022; tokens in screenshots/projector would leak.
- **Alternatives:** cookie set by Core (fine in prod; skipped to keep Core stateless for Funnel + Worker fallback).

## R11. Control Room palette: Direction A tokens with `Main.dc.html` arrangement
- **Decision:** the Control Room uses `DirA` (Night Watch) tokens; the layout regions come from `Main.dc.html` (which was drawn on paper tokens). Embedded phones remain light.
- **Rationale:** PRODUCT §1 and EXPERIENCE assign A to system/projector surfaces; `Main.dc.html` predates that assignment. A dark projector surface also makes the light phones read as "the people".
- **Open:** confirm with the orchestrator (Q2 below).

## R12. PWA with `vite-plugin-pwa`, never cache live paths
- **Decision:** per `research/generative-ui.md`; `navigateFallbackDenylist` for `/ws`, `/v/`, `/s/`, `/villages`, `/auth`, `/tools`, `/hooks`; `theme_color #2F6B57`, `background_color #FBF6EE`.
- **Rationale:** offline shell + last snapshot gives a non-blank screen when venue Wi-Fi drops; caching an API path would show stale safety state.

## R13. No router, four HTML entries
- **Decision:** `index.html`, `scan.html`, `join.html`, `control.html`; in-app pages (fact, print) are view state.
- **Rationale:** principle IX; Core maps `/`, `/s/*`, `/join`, `/control`, `/print` to these files; FS-5's `vite preview` serves them identically.

## R14. Fixtures replayed by a fake WS for V0
- **Decision:** `dev/fakeWs.ts` implements the server side of `ws_messages` in-browser (`?fake=<client>`): sends the role's view from `reyes_spec.json` + `data` from the fixture `connect` snapshot, then replays `ws_sequence_scam.json` (`start` + chosen tail) and `lid_scan_sequence.json` frames for that client with real timing (or `?speed=10`).
- **Rationale:** FLEET "kit: a fake WS server that sends snapshot then replays frames"; lets V0 render in 60 min with Core still a stub.

## Open questions for the orchestrator
- **Q1 Elder text floor.** D8 says elder text ≥ 28 px; artboards show button labels 22–25 px and secondary lines 17–22 px. Proposed: primary/actionable text ≥ 28 px, nothing under 22 px on elder; FS-5's generated test should assert that split. Needs a line in DECISIONS.md.
- **Q2 Control Room palette.** A (dark) per EXPERIENCE vs `Main.dc.html` (paper). Proposed A; flag if the projector contrast in JFK27 argues for paper.
- **Q3 `/print` ownership.** Printables are in the kit (FR-021) but QR SVGs come from `GET /villages/{id}/qr`; confirm Core serves `/print` → `index.html` and that the family word is in the coordinator snapshot's `printables`.
- **Q4 Projector phones.** Region B embeds member apps via iframes with projector-only tokens; needs Core to mint three read-only member tokens (or the Control Room shows the `ws_sequence_scam` client views from the whole-spec snapshot without actions). Default: whole-spec snapshot, actions disabled.
