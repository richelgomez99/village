# FS-7 Pitch kit contracts: `acceptance/run.sh`, `scripts/reset_demo.sh`, metrics

No schema changes. This file fixes the command-line interfaces every lane and the orchestrator rely on, and the two Core helpers the scripts call (core owns their implementation; names agreed here).

## A. `acceptance/run.sh`

```
acceptance/run.sh V<n> [--lane <lane>] [--list] [--only <NN-name>] [--keep-going] [--core <url>]
```
| Flag | Meaning |
|---|---|
| `V<n>` | target version; runs `checks/V0..V<n>` in order (cumulative) |
| `--lane <lane>` | only checks whose filename ends `.<lane>.sh|py` or `.all.sh|py` |
| `--list` | print the checks that would run, no execution |
| `--only <NN-name>` | run one check (any version) |
| `--keep-going` | don't stop at the first FAIL (summary at the end) |
| `--core <url>` | override `CORE_URL` (default `http://localhost:8787`) |

Exit codes: `0` all PASS · `1` a check failed · `2` runner misuse (unknown version/lane) · `3` Core unreachable for a check that needs it (reason printed).
Output line format: `PASS|FAIL|SKIP V<n> <NN-name.lane>: <reason> (<secs>s)`; `SKIP` only when a check's `# requires:` header lists an env var that is unset (e.g. `ANCHORBROWSER_API_KEY`), and never for `all`/`gate`/`kit` checks at V0.
Logs: `acceptance/out/V<n>-<HHMM>.log` (git-ignored). Each check gets `TIMEOUT_S` (default 60, override with `# timeout: 120` header).
Environment passed to checks: `CORE_URL`, `TUNNEL_URL`, `FIXTURES=contracts/fixtures`, `VILLAGE_LLM` (`off` forced for `gate` checks), `OUT_DIR`.
Check header convention (first lines of the file):
```
#!/usr/bin/env bash
# requires: CORE_URL
# timeout: 90
# verifies: V1 US-D, FR-004 (FS-7); FS-2 FR-00x
```
Selectors used by kit checks come from `specs/004-kit-control-room/contracts/README.md` §A; WS frames from `contracts/schemas/ws_messages.schema.json`.

The orchestrator tags only on `acceptance/run.sh V<n>` (no `--lane`) exit 0.

## B. `scripts/reset_demo.sh`

```
scripts/reset_demo.sh [--dry-run] [--only <step>] [--keep-tokens] [--clock <RFC3339>] [--village v_reyes]
```
Steps (in order; names for `--only`): `health, events, seed, clock, windows, verifications, tokens, villages, warm, counters, summary` (details in `data-model.md` §5). Guarantees: idempotent; ≤ 120 s; prints a summary table; non-zero exit names the failed step and the manual command. Requires `.env` with `CORE_URL`, `TUNNEL_URL`, `DEMO_CLOCK`, `VILLAGE_ADMIN_SECRET`, `DAYTONA_API_KEY`, `ANCHORBROWSER_API_KEY` (warm step `SKIP`s without the last two and says so).

### Core helpers the script calls (owned by core; agreed names)
| Call | Purpose |
|---|---|
| `GET /health` | step 1 |
| `POST /admin/reset` body `{scope: "events_today"\|"dose_windows"\|"verifications_today"\|"incidents_today"\|"proposals"\|"tokens"\|"counters", village}` header `X-Village-Admin: $VILLAGE_ADMIN_SECRET` | steps 2, 5, 6, 7, 10; returns `{deleted: n}` |
| `uv run python -m core.tools.seed <fixture.json>` | step 3; idempotent upsert by event id |
| `POST /clock/warp {now}` (openapi) | step 4 |
| `GET /villages/{id}/qr` (JSON) | step 7 (print URLs) |
| `uv run python -m core.tools.invites --mint be_marco --revoke-others` | step 7 |
| `GET /villages/{id}` + release list via `control{release}` replay or `uv run python -m core.tools.releases --last-good` | step 8 |
| `uv run python -m core.tools.warm --daytona --anchor --builder` | step 9; prints sandbox id/age, Anchor session id/age, builder warm latency |
Until a helper exists, the script prints `MISSING <helper>` for that step and continues (exit 1 at the end).

## C. `docs/METRICS.json` and `scripts/fill_measures.py`
```
scripts/fill_measures.py [--check] [--fallback] <file>...
```
- Default: replace `[MEASURE: name]` with `value` when `value`, `source`, `measured_at` are all set; leave others; exit 0.
- `--check`: no writes; list remaining placeholders; exit 2 if any.
- `--fallback`: replace remaining placeholders with the metric's `fallback` sentence (used only by `devpost.sh V4 --fallback` after 15:00).
Writers must include `source` (Arize URL, receipt id, test path) and `measured_at` (RFC 3339). The evals lane owns `scams_caught`, `false_alarms`, `experiment_url`; core owns `verify_latency_s`, `blueprint_s`, `apps_s`, `build_s`, `block_*`; pitch owns `phones_connected_peak`.

## D. `scripts/devpost.sh`
```
scripts/devpost.sh V<n> [--fallback] [--copy]
```
Prints the `## V<n>` section of `docs/DEVPOST.md` with metrics filled (`--fallback` for placeholders), fails with exit 2 if `[MEASURE:` remains and `--fallback` is not given; `--copy` puts it on the clipboard (`pbcopy`). It also prints the Built With tag list and the gallery file names in order.

## E. Artifacts the pitch lane publishes and where
| Artifact | Path | Deadline |
|---|---|---|
| Devpost text V0..V4 | `docs/DEVPOST.md` | each tag + 10 min |
| README | `/README.md` (rendered from `docs/README.src.md`) | 15:05 |
| 30 s clip | YouTube unlisted; URL in DEVPOST V1 | 12:35 |
| Draft video | `docs/video/draft-v3.mp4` (local) | 13:55 |
| Final video | YouTube unlisted; URL in DEVPOST V4 | 14:55 upload start |
| Thumbnail + gallery | `docs/gallery/01-hero.png … 05-fact.png` | 15:00 |
| Slides | `docs/SLIDES.md` + exported PDF | 15:45 |
| T-15 | `docs/T15.md` | 15:45 run |
| Sponsor pitches | `docs/SPONSOR_PITCHES.md` | 11:25 |
