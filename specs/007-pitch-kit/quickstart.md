# Quickstart: FS-7 Pitch kit

For the pitch lane at 10:00 and for the orchestrator who runs the gate.

## 0. Setup (10:00)
```
git worktree add ../village-pitch -b lane/pitch && cd ../village-pitch
mkdir -p docs acceptance/checks/{V0,V1,V2,V3,V4} acceptance/out scripts
cp ../village-prep/SPONSORS.md docs/SPONSOR_PITCHES.md     # trim to the pitches + file paths
```
`.env` needs `CORE_URL`, `TUNNEL_URL`, `DEMO_CLOCK`, `VILLAGE_ADMIN_SECRET`.

## 1. Run the gate
```
acceptance/run.sh V0 --list            # what would run
acceptance/run.sh V0 --lane kit        # a lane's self-check in its worktree
acceptance/run.sh V2                   # the orchestrator's merge/tag gate (cumulative V0..V2)
acceptance/run.sh V1 --only 02-tools-timeout
```
Expected: `PASS V0 01-contracts.all: OK contract 1.0.0 (1s)` … and exit 0. A `FAIL` line names the check and the reason; fix the lane, re-run.

## 2. Keep the page current
```
scripts/devpost.sh V1 --copy           # paste into Devpost after the V1 tag
scripts/fill_measures.py --check docs/DEVPOST.md README.md     # lists remaining [MEASURE: …]
scripts/render_readme.sh               # docs/README.src.md → README.md with metrics filled
```
Never hand-edit a number: put it in `docs/METRICS.json` with `source` and `measured_at`, then re-run.

## 3. Reset the demo
```
scripts/reset_demo.sh --dry-run        # shows every call
scripts/reset_demo.sh                  # ≤ 120 s; summary table; exit 0
scripts/reset_demo.sh --only warm      # re-warm Daytona/Anchor/builder before the pitch
scripts/reset_demo.sh --only tokens    # re-mint "Be Marco" after a rehearsal
```
A failed step prints the manual command; steps are independent.

## 4. Record the 30 s clip (12:15, right after V1 is green)
1. `scripts/reset_demo.sh`; Control Room on the projector tab; Marco's phone on the stand.
2. Start screen capture (Mac mirror 1920×1080) + phone capture; call the Mom line on speaker; say Carmen's line; wait for the ring; tap "That wasn't me".
3. Trim to ≤ 30 s, burn captions (`docs/VIDEO.md` §clip), export 1080p, upload unlisted, paste the URL as the first line of `## V1` in `docs/DEVPOST.md`.

## 5. Submission (15:05–15:10)
`scripts/devpost.sh V4` (or `V3` if V4 was cut) → paste every field; gallery `docs/gallery/01..05`; video URL; Built With tags; make the repo public; submit; reload logged out and check the video plays and links work. Small edits only until 15:28; nothing after.

## 6. T-15 (15:45)
Run `docs/T15.md` top to bottom; stop at the first red and apply its fallback (the list names it).
