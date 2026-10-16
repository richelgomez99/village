# Orchestrator handoff (Oct 16, 10:55) — the Claude orchestrator session hit its usage limit

## State of main (`~/village`, tags: gate-v0, spine-v0, voice-v1, kit-v0, V0-green)
- Core (FastAPI) serves `kit/dist` at `/` and the WS at `/ws`; runs on **port 8790** (`uv run uvicorn core.app:app --port 8790`; 8787 is taken by an unrelated process, D27). Public URL via Tailscale Funnel: https://richel-macbook.tail8feae0.ts.net (Funnel ON; verified from Anchor; the Mac itself cannot resolve ts.net).
- 97 tests green offline (`uv run pytest -q`): core spine 16, gate 49, voice 31. Spine measured: check-in tool call → all 3 phones in ~100–130 ms via SurrealDB Cloud.
- Kit: `cd kit && npm test` 35 green; `?fake=carmen|ana|marco|control` works offline; real Core snapshots render.
- Merge helper: `bash scripts/merge_lane.sh <branch>`; `LANE-REPORT.md` merges by union.

## Lanes in flight (worktrees, branches)
| Lane | Where | Runner | Status |
|---|---|---|---|
| core V1 (T012–T018) | `~/village-core-spine-gate` (001-core-spine-gate) | Codex, c11 panel 18 (fresh session, brief in scratchpad) | started 10:55; 2 dirty files from the previous session |
| gate V1 (G008–G010) | `~/village-gate` (lane/gate) | Codex, panel 19 | started 10:55 |
| voice V1b (real ElevenLabs agents) | `~/village-verification-loop` (002) | Codex, panel 16 | 1 commit ahead ("Configure real ElevenLabs tool endpoints"), 13 dirty; was reconnecting through rate limit |
| contracts 1.2.0 (D22 catalog: RefillCard, TonightCard, prescriptions binding, hello.view_as, identity; Reyes rev 5) | `~/village` main, `contracts/**` | Claude Opus subagent | running |
| builder V2 | `~/village-founding-generation` (003) | Claude Opus subagent | running |
| release V3 (Daytona image sandboxes, floor tests, Anchor, evals, self-fixing build) | `~/village-release-gate` (005) | Claude Opus subagent | running |
| kit V0+V1 | merged (V1 member-phone features are on main too: VerificationPrompt, PromptOverlay, IncidentCard, ScamCheck, join page) | done | Control Room is a shell only |
| pitch | merged (README, docs/DEVPOST.md V0, scripts/reset_demo.sh, docs/CHECKPOINTS.md, docs/SLIDES.md) | done | [MEASURE]/[PENDING] placeholders listed in LANE-REPORT.md |

## Known gaps to close next
1. Merge contracts 1.2.0 → tell core (serve `prescriptions:current`, accept `hello.view_as`, send `identity`) and builder; kit already renders RefillCard/TonightCard.
2. OpenAI rate limit (1M TPM/org) cuts Codex turns; sessions were restarted with narrow briefs. If it persists, move core V1 to a Claude subagent.
3. Twilio outbound refused: "Account not authorized to call +1917…" (geo permissions). Operator to enable US voice geo-permissions on the project owning +1 848 257 9221, then retry the ElevenLabs outbound call (`ELEVENLABS_PHONE_NUMBER_ID` is in .env).
4. Missing env: `ANTHROPIC_API_KEY` (Bedrock lab account only has `anthropic.claude-haiku-4-5`), `SURREAL_MEMORY_*` (Agent Memory context `village-demo`), `TWILIO_ACCOUNT_SID/AUTH_TOKEN` (optional).
5. Daytona snapshot creation is denied → release uses image sandboxes (node:22 in 16 s). Sandbox egress fully blocked (by design).
6. Checkpoint reports due: 12:15 V1, 13:00 V2, 13:40 V3, 14:15 V4, 14:20 freeze (`docs/CHECKPOINTS.md`). Submit Devpost by 15:10.
