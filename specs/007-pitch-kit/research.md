# Research: FS-7 Pitch kit

Sources: `research/winning-execution.md` (past winners, 60-second scan, video, slides, risk register, time plan), LAYERS.md, DECISIONS D13–D15, SPONSORS.md, EXPERIENCE.md, FLEET.md, `contracts/openapi.yaml`, `contracts/fixtures/events_reyes_seed.json`.

## R1. The page wins first; write it per version, not at the end
- **Decision:** `docs/DEVPOST.md` holds a complete section per version; `scripts/devpost.sh V<n>` prints the active one. Updated within 10 min of each tag.
- **Rationale:** Round 1 is judged from the page alone; LAYERS "Devpost text for that version updated" is part of the definition of a tagged version. Past winners (Katena, VoiceSRE) put a number and the demo link in the first two lines.
- **Alternatives:** one page written at 14:30 (rejected: a slipped version leaves no page).

## R2. Measured numbers only, enforced by tooling
- **Decision:** `[MEASURE: name]` placeholders; `docs/METRICS.json` entries need `value`, `source` (URL or file), `measured_at`; `fill_measures.py` refuses otherwise; acceptance check `no_placeholders` for V4 lists what remains; honest fallback wording per metric.
- **Rationale:** constitution VIII, CLAUDE.md rule 8, FLEET pitch row ("never invent numbers"). Judges trust "we measured X" more than adjectives.
- **Alternatives:** trust the author (rejected: 14:50 is when numbers get invented).

## R3. Acceptance runner as the single gate for merges and tags
- **Decision:** `acceptance/run.sh V<n> [--lane]` with cumulative, lane-tagged checks under `acceptance/checks/V<n>/`; built first thing at 10:00 with V0 checks that run against stubs.
- **Rationale:** FLEET merge protocol step 3 and principle VII: a version exists only when its acceptance passes; lanes need `--lane` to self-check in worktrees. Shell + Python keeps it dependency-free.
- **Alternatives:** pytest-only (rejected: kit and voice checks need curl/node/playwright); a CI service (no time).

## R4. reset_demo.sh = clear today's rehearsal, reseed, pin, warm
- **Decision:** steps: health → clear today's rows (events after `DEMO_DAY 00:00` for `v_reyes` except seeds) → reseed `events_reyes_seed.json` → clock pin → re-arm dose windows → clear verifications/incidents/proposals from today → tokens (revoke rehearsal members, re-mint "Be Marco") → ensure `published_rev` (Reyes) + block village present → warm Daytona sandbox + Anchor session (heartbeat) → warm builder grammar (one `render_app` tool call; Claude structured-output grammar compile is cached ~24 h) → counters 0 → summary. Idempotent; `--only`.
- **Rationale:** risk register "state dirty from rehearsal", ARCHITECTURE-VALIDATION §4.5 (pre-warm at 13:30), `research/generative-ui.md` (grammar warm-up), D7 blue/green.
- **Alternatives:** full DB wipe (rejected: loses the Oct 9 seed the Evolve act needs; loses release receipts).

## R5. Demo clock pin
- **Decision:** `DEMO_CLOCK` env (default proposed: Thu 2026-10-15 20:00 local → evening window due; lid-scan fixture day; Marco on duty so the kit reads "Le avisamos a Marco" and "Esta noche le cuida Marco"); the scam fixture is Fri 14:02 (Ana on duty) per contracts README §Decisions 1.
- **Rationale:** contracts README asks the orchestrator to "pin the demo clock to Thursday or accept 'Le avisamos a Ana' on Friday"; the artboards (Carmen, Family) show Thursday evening with Marco on.
- **Open:** orchestrator decides; `reset_demo.sh` takes the value from `.env` so either works.

## R6. Thirty-second round-1 clip at V1
- **Decision:** record the real scam moment the minute V1 is green; captions burned; YouTube unlisted; link first on the page by 12:35.
- **Rationale:** LAYERS "Round-1 insurance: a real clip beats a promise"; the TRON/Devpost guidance that the video is the first and often only thing judges see.
- **Alternatives:** wait for the 2-min video (rejected: if the afternoon slips, the page has nothing moving).

## R7. Slides in Direction B, Control Room in A
- **Decision:** deck and thumbnail use Kitchen Table tokens (`design/DirB.dc.html`); live screens shown in the pitch are the real Control Room (A) and phones (B).
- **Rationale:** EXPERIENCE "B for the people and the physical world: onboarding, apps, print kit, Devpost thumbnail, slides"; the contrast between warm slides and the dark system view reads as "people vs engine".

## R8. Video shot list follows the D15 arc, not the older pill-first script
- **Decision:** hook = the scam call; Build → Run → Rebuild (longest) → Anyone → close; the number by 1:45; blackout reveal at 1:48.
- **Rationale:** `research/winning-execution.md` §1 predates D13/D15 (its hook is the double dose); D15 makes the rebuild the climax and keeps the scam as the trigger. Winners' pattern kept: hook ≤ 8 s, one-liner by 0:20, number before the end, generality beat, end card.

## R9. Three sponsors on stage, six on the page
- **Decision:** Daytona, Arize, SurrealDB named in the pitch as the rebuild loop; ElevenLabs, Anchor, AWS get page sections and table pitches.
- **Rationale:** D13 "Prize focus", constitution IX, SPONSORS.md odds; partner prizes are judged across all teams from the page.

## R10. Time plan: time-boxed to clock times
- **Decision:** tasks in `tasks.md` carry start/end clock times from the LAYERS cutoffs and `research/winning-execution.md` §6 (adjusted to the 10:00–15:30 window and the 15:10 submit).
- **Rationale:** the pitch lane's work is deadline-shaped, not dependency-shaped; a late artifact is cut, not delayed.

## Open questions for the orchestrator
- **Q1 Demo clock:** Thursday 20:00 (Marco on) vs Friday 14:02 (Ana on). Default in `.env.example`: `DEMO_CLOCK=2026-10-15T20:00:00-04:00`.
- **Q2 Reset helpers:** core exposes `POST /admin/reset` (scoped: `events_today`, `verifications`, `proposals`, `tokens`, `counters`) and `uv run python -m core.tools.seed` / `warm`; confirm names before 13:30. Until then the script calls them and prints "missing helper" per step.
- **Q3 Video tool:** Screen Studio (if licensed) else QuickTime + CapCut; both produce burned captions. Decide at 13:30 so the draft at V3 uses the final pipeline.
- **Q4 Who presses record at 12:15:** the orchestrator (main session) is busy with V1 merge; the pitch lane owner records; needs the Marco phone and the speaker for 10 min.
