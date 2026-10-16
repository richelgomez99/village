# Feature Specification: FS-7 Pitch kit

**Feature branch:** `lane/pitch` (worktree `../village-pitch`)
**Created:** 2026-10-16 · **Status:** Draft, ready for `/plan`
**Lanes:** pitch (owner) + core (for `scripts/reset_demo.sh` hooks and `acceptance/`) · **Runs:** 10:00 → 15:55, alongside every version
**Folders owned:** `docs/` (DEVPOST.md, README.md source, SLIDES.md, VIDEO.md, THUMBNAIL.md, T15.md, METRICS.json), `scripts/reset_demo.sh`, `acceptance/`
**Inputs:** PRODUCT.md §3 (demo features per version), LAYERS.md (version map, demo arc, plain-words table, round-1 clip), FLEET.md (pitch row; merge protocol: nothing merges unless `acceptance/run.sh V<n>` passes), DECISIONS D13–D15, EXPERIENCE.md (identity lines, direction B for Devpost thumbnail and slides), SPONSORS.md (table + 30 s pitches), `research/winning-execution.md` (Devpost scan, video, slides, README outline, risk register, T-15), `contracts/fixtures/events_reyes_seed.json`, `contracts/openapi.yaml` (`/clock/warp`, `/villages`, `/improve`).

## Summary

The pitch kit makes sure that at every minute of the day there is a submittable Devpost page, a README that matches what runs, and a demo that can be reset to a known state in under two minutes. It produces (1) Devpost text per version V0–V4 with `[MEASURE: …]` placeholders that a script refuses to submit, (2) the README outline with the sponsor table, (3) a 6-slide outline, (4) a 2-minute video shot list plus the 30-second round-1 clip of the scam moment, (5) the Direction B thumbnail spec, (6) `scripts/reset_demo.sh` (prebuild villages, clear events, reset clock, re-arm windows, warm Anchor/Daytona), (7) the `acceptance/` runner `run.sh V<n> [--lane]` that gates every merge and every tag, (8) the T-15 checklist, and (9) the sponsor-table pitches. It never invents a number (constitution VIII) and never touches the demo path after 15:00 (VII).

Round 1 is judged from the Devpost page alone; finalists pitch at 16:00 (3 min + 2 min Q&A). The page therefore has to carry the partner-prize case on its own.

## User scenarios and testing

### US-A · The page is always submittable (LAYERS "always a working version") — P1
Given version `V<n>` was just tagged,
When the pitch lane runs `scripts/devpost.sh V<n>`,
Then `docs/DEVPOST.md` section `## V<n>` becomes the active page text (title, tagline, summary, "what it does", "how we built it", sponsors, "what's next", Built With tags), the README headline matches, and `acceptance/run.sh V<n> --lane pitch` reports which `[MEASURE: …]` placeholders remain.

### US-B · No invented metrics (constitution VIII) — P1
Given `docs/METRICS.json` has `scams_caught: null`,
When anyone runs `scripts/fill_measures.py`,
Then every `[MEASURE: scams_caught]` placeholder stays as-is and the script exits 2 listing it; only when evals writes a value with `source` (an Arize experiment URL) and `measured_at` does the placeholder become "N/30 caught".
Given 15:05 and a placeholder still present in a section the page will show,
When `acceptance/run.sh V4 --lane pitch` runs,
Then it fails with the placeholder's name, and the fallback wording in `data-model.md` §Placeholder fallbacks is pasted instead ("we measured X scenarios; results in the Arize link"), never a made-up number.

### US-C · Round-1 insurance clip (LAYERS §Two additions) — P1
Given V1 is green (≈12:15),
When the pitch lane records the scam moment (Carmen's call on speaker, Marco's phone ringing, "Ese no era Marco"),
Then a ≤ 30 s clip with burned-in captions is uploaded (YouTube unlisted) and linked at the top of the Devpost draft by 12:35, and the Devpost gallery image 1 is the thumbnail placeholder until the real one lands.

### US-D · Demo resets to a known state in < 2 min (risk register "state dirty from rehearsal") — P1
Given Core, SurrealDB Cloud, the Funnel and the kit are up,
When `./scripts/reset_demo.sh` runs,
Then: today's rehearsal events are gone and `events_reyes_seed.json` is re-applied (Oct 3 lisinopril change, Oct 9 money request + timeout + incident, consents, 08:11 morning dose, releases r3/r4); the demo clock is pinned to `DEMO_CLOCK`; dose windows are re-armed (evening slot `due`); verifications, incidents from today and pending proposals are cleared; rehearsal member tokens are revoked and the "Be Marco" invite re-minted; `published_rev` for Reyes is the last good rev and the blackout block is present; one Daytona sandbox from `village-kit` and one Anchor session are warm (heartbeat); the builder's structured-output grammar is warmed by one `render_app` call; the phones counter reads 0; the script prints a 12-line summary and exits 0. Runtime ≤ 120 s. Idempotent: running it twice yields the same summary.

### US-E · Acceptance gates merges and tags (FLEET merge protocol) — P1
Given a lane reports "ready to merge" for V2,
When the orchestrator runs `acceptance/run.sh V2`,
Then every check in `acceptance/checks/V0..V2` runs in order (cumulative), prints `PASS`/`FAIL` with a one-line reason, exits non-zero on the first failing check, and writes `acceptance/out/V2-<time>.log`. With `--lane kit`, only checks tagged `kit` or `all` run. The orchestrator tags `V2` only on a green run.

### US-F · The 3-minute pitch and Q&A (US-18 on stage) — P2
Given the final 8,
When the presenter runs the deck,
Then the six slides follow LAYERS' arc (Build → Run → Rebuild → Anyone → Close) with plain words only ("it figured out who's who", "nothing reaches her untested"), the QR slide shows the live phones counter, the close slide shows the measured number or its honest fallback, and the Q&A sheet gives one-sentence answers with a pointer to proof (trace, test file, receipt).

### US-G · Sponsor tables (SPONSORS.md) — P2
Given sponsor laps at 11:30, 13:00 and 15:30,
When the presenter visits a table,
Then the 30-second pitch for that sponsor names the exact file path and the on-screen moment, and asks "what would make this Best Use?"; answers go into `docs/SPONSOR_NOTES.md`.

### Edge cases
- **A version is cut** (e.g. V4 misses 14:15): the page falls back to the V3 text; the "what's next" section absorbs the cut layer honestly ("Evolve is built but not demoed live; receipts show…").
- **Video upload still processing at 15:05:** submit with the 30 s clip link already on the page; swap the 2-min link before 15:30 (small edits allowed until lock).
- **Arize experiment not finished:** placeholder fallback wording; the close line becomes "we built the eval set; the number lands after the pitch" — never a guess.
- **reset_demo.sh fails mid-way** (e.g. SurrealDB timeout): it prints which step failed and the manual command for it; steps are independent and re-runnable with `--only <step>`.
- **Venue blocks `ts.net`:** T-15 step 1 fails → switch `TUNNEL_URL` to the Worker front door and re-run `reset_demo.sh --only invites` to re-mint QR URLs.
- **Devpost lock at 15:30 with an unsaved edit:** the page text lives in git (`docs/DEVPOST.md`); the last pasted version is what counts; no edits after 15:28.
- **Judges don't scan:** the mirrored "Ana" phone on the projector carries the live-sync proof; the counter stays honest (it may read 1).

## Functional requirements

| ID | Requirement | Principle |
|---|---|---|
| FR-001 | `docs/DEVPOST.md` MUST contain one complete section per version `V0..V4` (title, tagline, 2–3 sentence summary, inspiration, what it does, how we built it, challenges, accomplishments, what we learned, what's next, Built With, Try it), each self-sufficient so any version can be pasted alone. | VII |
| FR-002 | Every metric in Devpost, README, slides and video captions MUST be written as `[MEASURE: <name>]` until `docs/METRICS.json` holds a value with `source` and `measured_at`; `scripts/fill_measures.py` MUST refuse to fill without both. | VIII |
| FR-003 | `acceptance/run.sh V<n> [--lane <lane>] [--list] [--only <check>]` MUST run cumulative checks for V0..V<n>, filter by lane tag, print `PASS/FAIL <check>: <reason>`, exit non-zero on failure, and log to `acceptance/out/`. Checks are shell or Python files under `acceptance/checks/V<n>/NN-<name>.<lane>.(sh\|py)`. | IV, VI, VII |
| FR-004 | The V0 check set MUST include: `uv run pytest core/gate -q` with the model off (`VILLAGE_LLM=off`), kit fixture renders (three roles, `unknown-types=0`), lid scan twice over the real `/s/` route producing `record` then `report_already_logged` and two tabs updating. V1 adds the verification loop (`scam_call_tool_requests.json` variants `denied`, `timeout`, `duplicate_webhook`) and Arize spans present. V2 adds founding → spec validation → QR → join. V3 adds a receipt validating against `release.schema.json` with one `blocked` and one `released`. V4 adds proposal approve → patch on three clients and a `METRICS.json` entry for `scams_caught` or the fallback flag. | IV |
| FR-005 | `scripts/reset_demo.sh` MUST implement the steps in `contracts/README.md` §reset_demo, be idempotent, finish in ≤ 120 s, support `--dry-run`, `--only <step>`, `--keep-tokens`, and print the summary table; it MUST NOT touch `contracts/` or generated code. | VII |
| FR-006 | The README MUST follow `research/winning-execution.md` §README outline (10 sections) with the sponsor table columns `Tool · What it does here · Code path · Where judges see it`, Mermaid architecture, badges, and the measured-results table or its fallback. | VIII |
| FR-007 | The slide deck MUST be six slides named with the judging words (idea, advantages, safeguards) and use Direction B (Kitchen Table) tokens: `#E4D3BA/#DCC9AD` table, `#FFFCF6` paper, `#2A231C` ink, `#2F6B57` sage, `#A8331A` tomato, `#C9821B` amber, Caveat hand notes in `#1D3F8F`. | — |
| FR-008 | The 2-minute video MUST have burned-in captions, the hook in the first 8 s, the measured number (or fallback) by 1:45, the blackout reveal, and an end card with repo URL and sponsor row; the 30 s clip MUST be cut from real footage of the V1 moment, not a mock. | VIII |
| FR-009 | The thumbnail (1200×800, 3:2) MUST follow Direction B: kitchen table, two phones (Carmen's Spanish hold card, Marco's "Did you just call Mamá asking for $2,000?"), the headline "Is this really Marco?", the blue NOCHE lid and the fridge card corner, no logo collage. | — |
| FR-010 | The T-15 checklist MUST be executable in order in 15 min and include the network test on two phones, `reset_demo.sh`, the test call, Marco's phone settings, tab order, `caffeinate`, mirroring/zoom and the opening line. | VII |
| FR-011 | Sponsor-table pitches MUST be ≤ 30 s each, name one file path and one on-screen moment, and match SPONSORS.md; on stage only Daytona, Arize and SurrealDB are named. | IX |
| FR-012 | The pitch lane MUST NOT modify `core/`, `kit/`, `agents/` or `contracts/`; it may add `acceptance/`, `scripts/reset_demo.sh` (core reviews the hooks it calls) and `docs/`. | VI |
| FR-013 | Every published text (Devpost, README, slides) MUST use the identity lines from EXPERIENCE.md/D15 verbatim: identity "Village: software that builds itself around your people.", opening "Apps are built for millions. Village builds one for your people.", close "It takes a village. Now every group can have one." and the autonomy line "The agent acts on its own; code draws the lines it can't cross." | — |
| FR-014 | Safety claims MUST be scoped honestly (no "HIPAA-compliant", no "prevents all scams"); the Devpost "Safeguards" section lists only rules that have tests in `core/gate/tests/`. | VIII, I |

### Non-functional
- All artifacts are Markdown in git; the Devpost form is filled by paste. No Devpost API.
- Video: 1920×1080, 30 fps, ≤ 2:00, captions ≥ 32 px; audio normalized; filmed phones readable at 50 % size.
- Reset script: bash, `set -euo pipefail`, uses `curl` + `uv run python -m core.tools.*` helpers that core exposes; no direct SurrealDB SQL from bash except the documented `reset` helper.

## Key entities (see data-model.md)
Version (V0–V4, cutoff, status) · Devpost section · Metric (name, value, source, measured_at, fallback) · Acceptance check (version, lane, command, expected) · Reset step · Slide · Shot · Sponsor pitch · Checklist item.

## Constitution check

| Principle | How this spec complies |
|---|---|
| I / II | Pitch artifacts make no decisions and trigger no actions; `reset_demo.sh` only calls Core helpers that themselves go through the gate or are explicit admin resets. |
| III | Seed events re-applied by reset carry their fixture `source`; nothing is overwritten (reset is a clear-and-reseed of *today's* rehearsal rows only). |
| IV | `acceptance/` is the gate for tags; V3/V4 checks verify a receipt and a patch, not a claim. |
| V | Slides use the floor's safety colors and plain words; nothing here changes generated UI. |
| VI | Checks read the contracts and fixtures; the pitch lane never edits them. |
| **VII** | Per-version Devpost text, draft video at V3, 30 s clip at V1, reset script, freeze discipline (no demo-path edits after 15:00; small page edits only until 15:28). |
| **VIII** | `[MEASURE: …]` placeholders enforced by script and by an acceptance check; sponsor claims point at file paths and traces; honest fallbacks. |
| IX | Three sponsors on stage; the rest on the page; one runner script; no tooling beyond bash/python. |

**Gate result:** PASS. Open points in `research.md` (demo clock pin; who owns the `/admin/reset` helper; video tool).

## Out of scope
Product code · the actual Arize experiment (evals lane produces the number; FS-7 only consumes `METRICS.json`) · Devpost API automation · printed collateral beyond the fridge card already in FS-4.
