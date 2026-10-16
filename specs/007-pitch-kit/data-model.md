# Data Model: FS-7 Pitch kit

Everything is a file in git under `docs/`, `scripts/`, `acceptance/`. The entities below define their shapes so scripts and checks can parse them.

## 1. Version
| Field | Values |
|---|---|
| id | `V0` \| `V1` \| `V2` \| `V3` \| `V4` |
| cutoff | 11:00 · 12:15 · 13:00 · 13:40 · 14:15 |
| headline | LAYERS "Devpost headline" |
| status | `planned` \| `green` (tag exists) \| `cut` |
| acceptance | `acceptance/checks/V<n>/` (cumulative with lower versions) |
State: `planned → green` on `git tag V<n>` after a green run; `planned → cut` at cutoff + 0 min if not green (then the page uses the highest green version).

## 2. Devpost section (`docs/DEVPOST.md`)
```
## V<n> · <headline>
### Title / Tagline / Summary / Inspiration / What it does / How we built it / Challenges / Accomplishments / What we learned / What's next / Built With / Try it
```
Rules: every section complete on its own; metrics only as `[MEASURE: <name>]`; identity lines verbatim; sponsor paragraphs carry `file:` and `moment:`.

## 3. Metric (`docs/METRICS.json`)
```json
{
  "scams_caught":      {"value": null, "unit": "of 30", "source": null, "measured_at": null,
                        "fallback": "the eval set is built (30 scam scripts, 20 benign calls); the number is in the Arize link after the run"},
  "false_alarms":      {"value": null, "unit": "of 20", "source": null, "measured_at": null, "fallback": "see scams_caught"},
  "verify_latency_s":  {"value": null, "unit": "s (tool call → Marco's phone rings)", "source": null, "measured_at": null, "fallback": "measured in Arize spans on the verification path"},
  "gate_tests":        {"value": null, "unit": "tests, model off", "source": "core/gate/tests/", "measured_at": null, "fallback": "all gate rules have tests in core/gate/tests/"},
  "blueprint_s":       {"value": null, "unit": "s", "source": null, "measured_at": null, "fallback": "streamed while the apps build"},
  "apps_s":            {"value": null, "unit": "s", "source": null, "measured_at": null, "fallback": "under a minute in rehearsal"},
  "build_s":           {"value": null, "unit": "s (Daytona build + tests)", "source": null, "measured_at": null, "fallback": "see the receipt"},
  "block_generated_at":{"value": null, "unit": "clock time", "source": null, "measured_at": null, "fallback": "earlier today"},
  "block_build_s":     {"value": null, "unit": "s", "source": null, "measured_at": null, "fallback": "see the receipt"},
  "experiment_url":    {"value": null, "unit": "url", "source": null, "measured_at": null, "fallback": "Arize project link"},
  "phones_connected_peak": {"value": null, "unit": "phones", "source": null, "measured_at": null, "fallback": "live counter on stage"}
}
```
Fill rule: `value !== null && source && measured_at` ⇒ placeholder replaced by `value` (+ unit where the template says so). Otherwise the placeholder stays, and `devpost.sh --fallback` substitutes `fallback` text. Writers: evals lane (scams, false alarms, experiment_url), core (latency, build times, block times), pitch (phones peak, from the counter).

## 4. Acceptance check
File `acceptance/checks/V<n>/NN-<name>.<lane>.sh|py`, `<lane>` ∈ `all | core | gate | kit | voice | builder | release | evals | memory | pitch`.
Contract: prints nothing on success (runner prints `PASS`), prints one line of reason on failure, exit code non-zero; env available: `CORE_URL`, `TUNNEL_URL`, `VILLAGE_LLM` (`off` for gate checks), `FIXTURES` (= `contracts/fixtures`), `TIMEOUT_S` (default 60). Runner output: `PASS|FAIL <V> <NN-name.lane>: <reason> (<secs>s)`; log `acceptance/out/<V>-<HHMM>.log`.

### Check list by version (initial)
| V | Check | Lane | Expected |
|---|---|---|---|
| V0 | 01-contracts | all | `contracts/validate.py` prints `OK contract 1.0.0` |
| V0 | 02-gate-model-off | gate | `VILLAGE_LLM=off uv run pytest core/gate -q` green, no network (socket patched) |
| V0 | 03-kit-fixtures | kit | `cd kit && npm test` + headless render of elder/coordinator/helper from `reyes_spec.json`, `unknown-types=0` |
| V0 | 04-scan-twice | core | `GET /s/<token>` → JSON `decision.decision=record`; again after window → `report_already_logged`, `escalate.channel=both`; bad token → 404 |
| V0 | 05-ws-two-tabs | core | two WS clients (carmen, ana) receive the `dose` event with `facts:dose_event…` within 1 s of the scan |
| V0 | 06-devpost-v0 | pitch | `docs/DEVPOST.md` has `## V0`; README renders |
| V1 | 01-tools-denied | voice | replay `scam_call_tool_requests.json` `denied` → `await_verification` returns `say.es` = fixture |
| V1 | 02-tools-timeout | voice | `timeout` variant returns the safe default at ≤ 30 s |
| V1 | 03-dup-webhook | core | `duplicate_webhook` returns the cached decision, one ledger row |
| V1 | 04-prompt-frame | kit | marco client receives `prompt`, answers, gets `result.ok` |
| V1 | 05-incident-ana | core | `incidents:open` for ana contains `inc_ver_…` with provenance |
| V1 | 06-arize-spans | evals | a trace with GUARDRAIL + TOOL spans for `session.id=village-v_reyes` exists (or local mirror) |
| V1 | 07-clip-linked | pitch | `docs/DEVPOST.md` V1 has the 30 s clip URL |
| V2 | 01-founding | builder | `POST /villages` from a fixture sentence → VillageSpec validates; blueprint events streamed |
| V2 | 02-join | core | `GET /villages/{id}/qr` → invite → `POST /auth/redeem` → token → WS snapshot for helper |
| V2 | 03-control-room | kit | `control` snapshot + `reasoning` frames render blueprint regions |
| V2 | 04-ask-why | core | `POST /villages/{id}/ask` returns `answer` + ≥ 1 `sources[]` |
| V3 | 01-receipt-blocked | release | a receipt validating against `release.schema.json` with `result=blocked` and a failed `tests` stage |
| V3 | 02-receipt-released | release | a `released` receipt with `repair_of` set; `live_rev` advanced |
| V3 | 03-anchor-evidence | release | `anchor_qa.evidence_url` or `live_view_url` present |
| V3 | 04-block-prebuilt | builder | `block_spec.json`-shaped village exists with its own receipt |
| V3 | 05-draft-video | pitch | `docs/VIDEO.md` lists the draft file path; file exists |
| V4 | 01-proposal-ready | evals | `/improve` yields a proposal `status=ready` validating against `proposal.schema.json` |
| V4 | 02-approve-patch | core | approve → three clients receive `patch` with `highlight` containing `scam` |
| V4 | 03-fact-view | memory | fact history endpoint returns `history[]` with a superseded row |
| V4 | 04-metrics-or-fallback | pitch | `METRICS.json` `scams_caught` has value+source, or `--fallback` wording is in the active section |
| V4 | 05-no-placeholders | pitch | `devpost.sh V4` output contains no `[MEASURE:` (fails loudly otherwise) |

## 5. Reset step (`scripts/reset_demo.sh`)
| # | Name (`--only`) | Action | Verifies |
|---|---|---|---|
| 1 | health | `GET $CORE_URL/health`; SurrealDB ping via Core; Funnel URL reachable | all 200 |
| 2 | events | `POST /admin/reset {scope: events_today, village: v_reyes}` | count of deleted rows printed |
| 3 | seed | `uv run python -m core.tools.seed contracts/fixtures/events_reyes_seed.json` | seed ids present (`ev_1009_1921_money`, `ev_1003_med_change`, …) |
| 4 | clock | `POST /clock/warp {now: $DEMO_CLOCK}` | `control{clock}` broadcast received |
| 5 | windows | `POST /admin/reset {scope: dose_windows}` → evening `due` | `facts:dose_event…today` evening `due` |
| 6 | verifications | `POST /admin/reset {scope: verifications_today, incidents_today, proposals}` | `incidents:open` = [] for today; Oct 9 incident kept |
| 7 | tokens | revoke rehearsal member tokens (unless `--keep-tokens`); re-mint "Be Marco" invite; print QR URLs | `GET /villages/v_reyes/qr` JSON |
| 8 | villages | ensure `published_rev` (Reyes) = last released; block village present | receipts list |
| 9 | warm | Daytona: create/keep one sandbox from `village-kit`, heartbeat; Anchor: one session alive; builder: one `render_app` tool call (grammar compile) | ages printed |
| 10 | counters | `POST /admin/reset {scope: counters}` | phones counter 0 |
| 11 | summary | table of steps with ✓/✗ and durations; exit code | ≤ 120 s total |
Flags: `--dry-run` (print calls), `--only <name>`, `--keep-tokens`, `--clock <iso>`. Env: `CORE_URL`, `TUNNEL_URL`, `DEMO_CLOCK`, `VILLAGE_ADMIN_SECRET`.

## 6. Slide / Shot / Pitch / Checklist item
- **Slide:** {n, title (judging word), visual (artboard ref), spoken line, plain-words substitutions, t_start, t_end}.
- **Shot:** {t_start, t_end, source (screen | phone | card), caption, speed, placeholder metrics}.
- **Sponsor pitch:** {sponsor, text ≤ 30 s, file_path, moment, on_stage: bool}.
- **Checklist item:** {n, text, verifies (command or observation), owner}.

## 7. Placeholder fallbacks (verbatim, used by `devpost.sh --fallback`)
- scams_caught/false_alarms: "We built a 50-case eval set (30 scam scripts across voice, text and 'bank' variants; 20 benign family calls about money) and run it as an Arize experiment against the money gate; the result table is at the Arize link."
- verify_latency_s: "Latency from the tool call to Marco's phone ringing is measured as Arize spans on the verification path."
- gate_tests: "Every gate rule has a test in `core/gate/tests/`; they run with the model off."
- build times: "See the release receipt on the Control Room; every stage carries its start and end time."
