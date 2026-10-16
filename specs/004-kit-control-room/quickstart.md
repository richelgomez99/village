# Quickstart: FS-4 Kit

For the kit lane at 10:00, and for anyone who needs the member app, scan page, join page or Control Room running in under five minutes.

## 0. Prerequisites
Node 22+, npm 10+. The worktree: `git worktree add ../village-kit -b lane/kit` (FLEET.md). Contracts and fixtures are read from `../contracts/` (symlinked into `kit/dev/fixtures` at `postinstall`).

## 1. Scaffold (T001–T003)
```
cd kit
npm create vite@latest . -- --template react-ts
npm i fast-json-patch zod qrcode.react && npm i -D vite-plugin-pwa vitest jsdom @testing-library/react @testing-library/jest-dom
npm run dev -- --host
```
Open `http://localhost:5173/?fake=marco`. You should see "Is it my turn?" rendered from `contracts/fixtures/reyes_spec.json` (helper view) with the fixture's `rota:current?member=me` answer.

## 2. Try every client against fixtures (no Core)
| URL | What you see |
|---|---|
| `/?fake=carmen` | elder view (es, light, 3 big buttons, 911), then the scam `start` frames: amber "No mande dinero todavía" with the countdown |
| `/?fake=carmen&tail=denied` | → tomato "Ese no era Marco" |
| `/?fake=carmen&tail=timeout` | → "No pude confirmar con Marco" (safe default) |
| `/?fake=marco` | prompt overlay "Did you just call Mamá asking for $2,000?"; tap "That wasn't me" → `result` → thanks state |
| `/?fake=ana` | coordinator dashboard: LifeAreas, IncidentCard appears at 14:02:21, Timeline, PillOrganizer |
| `/?fake=ana&seq=lid` | lid-scan frames: morning slot turns green, second scan → escalation alert |
| `/?fake=ana&seq=evolve` | patch rev 4→5 from `proposal.schema.json` example: ScamCheck flashes NEW on the elder iframe, Proposal card on Ana |
| `/scan.html?fixture=first` / `?fixture=second` / `?fixture=bad` | "Anotado, Carmen" / "Esta tapa ya se anotó a las 8:02." / error page |
| `/join.html?fake=marco` | Join as Marco form; submit → fake token → redirects to `/?fake=marco` |
| `/control.html?fake=control` | Control Room replaying `start` + `denied` and the `rel_reyes_r3`/`r4` receipts |
`&speed=10` replays frames 10× faster.

## 3. Against the real Core
```
VITE_CORE_URL=http://localhost:8787 npm run dev -- --host
```
Then open the member URL Core prints (`/?m=<member_token>`) or the QR from `GET /villages/v_reyes/qr`. Through the Funnel URL use `VITE_CORE_URL=https://richel-macbook.tail8feae0.ts.net`.

## 4. Tests and build
```
npm test                 # renderer.unknown, patch.rev, ws.reconnect, props.schema, elder.floor.smoke, i18n.rtl
npm run build            # kit/dist: index.html scan.html join.html control.html + assets + sw.js
npm run preview -- --port 4173
```
`npm run build` must finish in < 20 s on the MacBook (FS-5's sandbox budget is 30 s).

## 5. Hand-off checklist (what the orchestrator checks before merging)
- `acceptance/run.sh V0 --lane kit` passes: fixture renders for three roles, `unknown-types` count 0, patch rev gap resyncs, reconnect within 8 s.
- No file outside `kit/` changed; `contracts/` untouched.
- `kit/README.md` lists the selectors (copy of `contracts/README.md` §A).
- Bundle size printed by `vite build` ≤ 250 kB gz per entry.

## 6. Common problems
- **Blank screen, console "unknown type":** the fixture or Core sent a type the catalog lacks; the count is in `[data-test="unknown-types"]`. Siblings should still render; if the whole screen is blank, the `Screen` itself failed zod: check `props.title`.
- **Countdown wrong:** drift is computed from `snapshot.now`; with `?fake=` the fake server's clock is the fixture's `t`.
- **iOS doesn't speak:** tap "Leer en voz alta" once; speech needs a gesture.
- **Fonts missing offline:** `public/fonts/` must contain the woff2 subsets (T005).
