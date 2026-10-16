# Tasks: FS-7 Pitch kit

Lane `pitch`, worktree `../village-pitch`, branch `lane/pitch`; `acceptance/` and `scripts/reset_demo.sh` are reviewed by core before merge. Tasks are **time-boxed to clock times** (LAYERS cutoffs; `research/winning-execution.md` §6 adjusted to a 15:10 submit). A task that misses its box is cut, not delayed. Columns: **Clock** (start–end), **Ver**, **Min**, **Deps**, **[P]**, **Acceptance** (check or observable), **Principle**.

## 10:00–11:00 · V0 window
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T001 | `acceptance/run.sh` + `lib.sh`: args, cumulative versions, lane filter, `--list/--only/--keep-going`, timeouts, PASS/FAIL/SKIP lines, logs, exit codes | 10:00–10:20 | V0 | 20 | — | | `run.sh V0 --list` prints the V0 checks; a fake failing check yields exit 1 | VII, IV |
| T002 | V0 checks: `01-contracts.all`, `02-gate-model-off.gate`, `03-kit-fixtures.kit`, `04-scan-twice.core`, `05-ws-two-tabs.core`, `06-devpost-v0.pitch` (data-model §4) | 10:20–10:40 | V0 | 20 | T001 | | each runs against the 10:00 stubs: contracts PASS, others FAIL with a clear reason until lanes land | IV, VI |
| T003 | `docs/DEVPOST.md` skeleton with `## V0..V4` headings + V0 section text (plan.md) + Built With; `docs/README.src.md` outline (10 sections, sponsor table) ; `scripts/render_readme.sh` | 10:20–10:45 | V0 | 25 | — | [P] | `06-devpost-v0` PASS; README renders with badges | VIII, VII |
| T004 | `docs/METRICS.json` (data-model §3) + `scripts/fill_measures.py` (`--check`, `--fallback`) + `scripts/devpost.sh` | 10:45–11:00 | V0 | 15 | T003 | [P] | `fill_measures.py --check` lists 11 placeholders; `devpost.sh V0` exits 2 without `--fallback` | VIII |
| T005 | Save the Devpost draft online: name, V0 tagline, repo placeholder, thumbnail placeholder (DirB artboard screenshot) | 10:45–11:00 | V0 | 10 | T003 | [P] | draft exists; link in `docs/DEVPOST.md` header | VII |

## 11:00–12:15 · V1 window
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T006 | V1 checks: `01-tools-denied.voice`, `02-tools-timeout.voice`, `03-dup-webhook.core`, `04-prompt-frame.kit`, `05-incident-ana.core`, `06-arize-spans.evals`, `07-clip-linked.pitch` | 11:00–11:25 | V1 | 25 | T001 | | `run.sh V1 --list` shows 13 checks; voice checks replay `scam_call_tool_requests.json` | IV |
| T007 | `docs/SPONSOR_PITCHES.md` (6 × ≤ 30 s + file path + moment + lap question); print one card | 11:00–11:25 | V1 | 15 | — | [P] | file matches SPONSORS.md wording | IX |
| T008 | **Sponsor lap 1** (Daytona, Arize, SurrealDB, ElevenLabs, Anchor): one sentence each + "what would make this Best Use?"; notes to `docs/SPONSOR_NOTES.md` | 11:30–11:40 | V1 | 10 | T007 | | notes file has 5 entries | — |
| T009 | DEVPOST `## V1` text (plan.md) incl. Safeguards list limited to rules with tests; update README headline | 11:40–12:05 | V1 | 20 | T003 | [P] | `devpost.sh V1 --fallback` prints a complete page | VIII, I |
| T010 | `docs/VIDEO.md`: 30 s clip shot list + capture settings; stand, speaker, phone ready | 11:40–12:05 | V1 | 15 | — | [P] | file present; gear checked | VII |
| T011 | **Record the 30 s clip** the minute V1 is green; trim, captions, upload unlisted; URL first line of `## V1`; paste V1 to Devpost | 12:15–12:35 | V1 | 20 | T009, T010, V1 tag | | `07-clip-linked` PASS; Devpost page shows the clip | VII, VIII |

## 12:15–13:00 · V2 window
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T012 | V2 checks: `01-founding.builder`, `02-join.core`, `03-control-room.kit`, `04-ask-why.core` | 12:35–12:50 | V2 | 15 | T001 | [P] | `run.sh V2 --list` | IV |
| T013 | DEVPOST `## V2` text + "Ask Village why" paragraph; README §3 bullets | 12:35–12:55 | V2 | 20 | T009 | [P] | `devpost.sh V2 --fallback` complete | VIII |
| T014 | `docs/SLIDES.md`: six slides (plan.md) with plain-words substitutions + Q&A sheet; start the deck in Keynote/Slides with DirB tokens | 12:35–13:00 | V2 | 25 | — | [P] | six titled slides; QR slide has the counter placeholder | — |
| T015 | **Sponsor lap 2** (show a working integration on the phone; ask them to scan) | 13:00–13:10 | V2 | 10 | T008 | | notes updated | — |

## 13:00–13:40 · V3 window
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T016 | V3 checks: `01-receipt-blocked.release`, `02-receipt-released.release`, `03-anchor-evidence.release`, `04-block-prebuilt.builder`, `05-draft-video.pitch` | 13:10–13:25 | V3 | 15 | T001 | [P] | receipts validate against `release.schema.json` examples | IV |
| T017 | DEVPOST `## V3` text + sponsor sections with file paths; README sponsor table rows filled with real paths from merged lanes | 13:10–13:30 | V3 | 20 | T013 | [P] | `devpost.sh V3 --fallback` complete; paths exist in the repo | VIII |
| T018 | `scripts/reset_demo.sh` skeleton: arg parsing, step runner, `--dry-run`, `--only`, summary; steps call the agreed helpers or print `MISSING` | 13:25–13:40 | V3 | 15 | — | [P] | `reset_demo.sh --dry-run` lists 11 steps | VII |
| T019 | **Draft video at the V3 tag** (same shot list, placeholders allowed), saved locally as insurance | 13:40–13:55 | V3 | 15 | V3 tag, T010 | | `05-draft-video` PASS | VII |

## 13:40–14:15 · V4 window
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T020 | V4 checks: `01-proposal-ready.evals`, `02-approve-patch.core`, `03-fact-view.memory`, `04-metrics-or-fallback.pitch`, `05-no-placeholders.pitch` | 13:55–14:05 | V4 | 10 | T001, T004 | [P] | `run.sh V4 --list` shows all 27 checks | IV, VIII |
| T021 | DEVPOST `## V4` text (number placeholders, limitations), `docs/THUMBNAIL.md` spec, gallery list | 13:55–14:15 | V4 | 20 | T017 | [P] | `devpost.sh V4 --fallback` complete | VIII |
| T022 | Collect metrics from lanes into `METRICS.json` (evals: scams/false alarms/experiment URL; core: latency, build times, block times) with sources | 14:05–14:20 | V4 | 15 | T004 | | `fill_measures.py --check` shows ≤ 2 placeholders or the fallback flag set | VIII |

## 14:15–15:10 · Freeze: reset, video, page, submit
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T023 | `scripts/reset_demo.sh` complete (events, seed, clock, windows, verifications, tokens, villages, warm, counters, summary); run twice; time it | 14:20–14:35 | — | 15 | T018 | | two runs ≤ 120 s each, identical summaries, exit 0 | VII |
| T024 | **Record the 2:00 video** (shot list in plan.md), voiceover, captions; start the YouTube upload | 14:20–14:55 | — | 35 | T019, T023 | [P] | file ≤ 2:00; upload started by 14:55 | VII, VIII |
| T025 | Thumbnail export (DirB artboard 2×, 1200×800) + gallery 02–05 screenshots (architecture Mermaid export, three apps, ReleaseStrip with the caught build, Fact view) | 14:35–15:00 | — | 25 | T021 | [P] | five PNGs in `docs/gallery/` | — |
| T026 | `fill_measures.py` run; `render_readme.sh`; README sponsor table + eval results table; make the repo public | 14:55–15:05 | — | 10 | T022 | [P] | `05-no-placeholders` PASS (or `--fallback` used and noted) | VIII |
| T027 | **Submit Devpost** (`devpost.sh V4` or `V3`), gallery, video URL, Built With tags; reload logged out; check video + links | 15:05–15:10 | — | 5 | T024–T026 | | submitted; checklist in `docs/DEVPOST.md` footer ticked | VII |
| T028 | Small page edits only (typos, swapped video link if processing finished); stop at 15:28 | 15:10–15:28 | — | 18 | T027 | | no edits after 15:28 | VII |

## 15:30–16:00 · After lock
| ID | Task | Clock | Ver | Min | Deps | [P] | Acceptance | Principle |
|---|---|---|---|---|---|---|---|---|
| T029 | **Sponsor lap 3**: "submitted, here's the page, here's the exact line where we use you" | 15:30–15:40 | — | 10 | T027 | | 6 tables visited | IX |
| T030 | Rehearse the pitch 3× with a stopwatch incl. one failure drill (kill Wi-Fi: say the fallback line, switch to the recorded clip within 5 s) | 15:35–15:50 | — | 15 | T014 | | each run ≤ 3:00 | VII |
| T031 | Run `docs/T15.md` (8 items) at 15:45; `reset_demo.sh`; counter reads 0 | 15:45–15:58 | — | 13 | T023 | | all items green or fallback applied | VII |

## Rules of the freeze (constitution VII)
After 15:00 nobody touches the demo path; `reset_demo.sh` may be run, not edited. If a reset step fails at T-15, use the manual command it prints; do not patch Core.

## Critical path
T001 → T002 (gate usable at 10:40) · T003 → T004 → T009 → T011 (clip on the page 12:35) · T017 → T021 → T022 → T026 → T027 (submit 15:10) · T018 → T023 → T031 (reset at T-15). T024 runs in parallel with T025/T026 from 14:20.
