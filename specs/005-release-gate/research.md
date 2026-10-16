# Research: Release gate (FS-5)

Sources read: `research/daytona.md`, `research/anchor.md`, `research/arize-bedrock.md`, `research/innovation-scout.md` (#4 vision judge, Anchor self-healing), ARCHITECTURE-VALIDATION.md edges 10–13/15, smoke scripts 03/04/05/07. Status marks: ✅ verified tonight · 🟡 docs + SDK signatures · 🔴 untested. Each open item names the smoke script (or the new one) that closes it.

## Decisions already made (do not reopen)
| Decision | Source | Consequence here |
|---|---|---|
| Serve `dist/` from Core after tests; Daytona = build + test + caught failure | ARCH-VAL §4.1 (11-B), CLAUDE.md gotchas | No proxy, no preview token refresh, no interstitial on phones; `vite base './'` |
| Evals in-process, logged to Arize, local mirror | ARCH-VAL §4.4 | `update_evaluations` + `var/evals/`; never wait for online-eval index lag |
| Pre-warm one sandbox + one Anchor session at 13:30 | ARCH-VAL §4.5, D15 | Pool of 1 each with heartbeat |
| Deterministic Playwright at 390×844, not `agent.task` | `research/anchor.md` recommended decisions, D12 | Repeatable, effectively free, role selectors from the kit's aria-labels |
| Receipts on stage; live rebuild with recorded fallback | D13, D15 | `RELEASE_BUDGET_S` + fallback frame |
| Snapshot name `village-kit`; containers, not VMs; no fork | `research/daytona.md` §6, smoke 04 | "Try a variant" = second build dir, not fork |

## Open items

| # | Question | Status | Resolved by | Fallback if bad |
|---|---|---|---|---|
| R-01 | Snapshot build time and cold create → first command for `village-kit`; does `/opt/kit-template` hold the **real** `kit/` (catalog + renderer) or only the smoke package.json? | 🟡 (smoke 04 built the toolchain-only image) | `uv run smoke/04_daytona_snapshot.py --name village-kit-v2` after T003 adds `add_local_dir("kit", "/opt/kit-template")` | Upload `kit/src` with the bundle each build (+2–4 s, more bytes) |
| R-02 | `vite build` + `vitest run` wall time at the snapshot's resources (1 vCPU/1 GiB default vs 2/2) and whether OOM appears | 🔴 | smoke 04 `--keep` then time `bash build.sh` in the sandbox (T004 records `[MEASURE]`) | `Resources(cpu=2, memory=2)` on the snapshot; drop `render.test.tsx` to the three cheapest roles |
| R-03 | `fs.download_file` on a 1–3 MB `dist.tgz`: latency and whether the async SDK returns bytes or streams | 🟡 (signature verified in docs) | T004 build smoke | `sb.fs.download_file` per file for `index.html` + assets list |
| R-04 | Anchor `create_session` / `connect_over_cdp` / `goto(TUNNEL_URL)` latency; does the Anchor browser reach `*.ts.net` (Funnel)? Does `live_view_url` iframe cleanly from the Control Room on the Funnel origin? | 🟡 (iframe headers ✅; latency from benchmarks only) | `uv run smoke/05_anchor.py` with `PREVIEW_URL=$TUNNEL_URL/health` (T010 records `[MEASURE]`) | Worker front door URL for QA; if still blocked, Anchor stage `skipped` with a reason and evals run on a local Playwright screenshot (not Anchor) — stated honestly on the strip |
| R-05 | Claude vision (image content block) on the Mantle endpoint for `BEDROCK_SONNET_MODEL`; TTFT with a 390×844 PNG | 🔴 | `uv run smoke/01_llm.py --vision` (new flag, T013) | `Anthropic()` client for this one eval; else `judge_unavailable` |
| R-06 | `ArizeClient().spans.update_evaluations` → time until `eval.<name>.label` is visible in the UI and filterable with `ax.spans.list(filter="eval.X.label = ...")`; exact filter grammar | 🟡 | `uv run smoke/07_arize.py` extended with an `update_evaluations` call (T014) | Local mirror is the source for "reads its own evals"; Arize is shown as the dashboard |
| R-07 | Recording availability delay after `delete_session`; `fetch_primary_recording` streaming shape in the async client | 🟡 | smoke 05 `--keep` → delete → poll (T011) | Receipt released without `video_url`; patched in later |
| R-08 | Anchor pre-warmed session survival: does `idle_timeout` count a CDP `page.evaluate` as activity? Max `max_duration` on the Free plan? | 🔴 | T017 prewarm test: hold a session 10 min with the keep-alive, then run QA | Re-create the session at T-60 s before the Rebuild beat (operator button in the Control Room) |
| R-09 | Daytona Tier after the coupon: concurrent sandbox quota (pool + active + the blackout run) | 🟡 | smoke 02/04 output + dashboard | Pool size 0 (cold creates, +3–6 s) |
| R-10 | Vitest in jsdom for `render.test.tsx` of all roles with the WS client mocked; does `vite-plugin-pwa` break `vitest`? | 🔴 | kit lane's local `npm test` + T005 | Exclude the PWA plugin in test mode (`mode === 'test'`) |
| R-11 | Shadow village reset cost (`reset_village(<id>_qa)`) on SurrealDB Cloud | 🟡 (local CAS/LIVE ✅) | smoke 06b timing + T008 | Keep `v_reyes_qa` warm; reset only the tables QA touches |

## Items explicitly out of scope (noted, not pursued)
- Daytona sandbox fork and warm pools (support-gated, VM only).
- Anchor Automation Tasks with self-healing (judge appeal, stretch only after V4).
- Arize online continuous evals (index lag); Signal (cadence 3 h) — enable if time, never on the demo path.
- Org-level Daytona OTel → Arize (bonus).
