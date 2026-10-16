# CLAUDE.md: Village (Daytona HackSprint NYC, Oct 16 2026)

Copy this file into the root of the product repo at 10:00. It tells every Claude Code session and subagent how to work here.

## What we're building
Village: software made for one group. Read `LAYERS.md` (plan of record: layers, cut lines), then `DECISIONS.md`, then `SPEC.md`. DECISIONS.md overrides SPEC.md where they differ (realtime is WebSockets, not SSE; public URL is Tailscale Funnel; demo arc Generate → Protect → Evolve → Anyone). SPEC.md is the source of truth for architecture, data model, APIs, policy rules, tiers and the demo script. Research behind each decision is in `research/*.md`. Demo data is in `data/`, and voice and builder prompts are in `prompts/`.

## Hard deadlines
- Follow the layer cutoffs in LAYERS.md (every layer tagged `L<n>-green` before the next starts). Freeze at 14:20, Devpost submitted by 15:10 (locks at 15:30).
- If a task will take more than 20 minutes longer than planned, stop and say so. Scope gets cut, the deadline doesn't move.

## Stack (do not substitute)
- **Core:** Python 3.13, `uv`, FastAPI, httpx, pydantic v2, pytest. One process: `uv run uvicorn core.app:app --port 8790`. Exposed publicly with Tailscale Funnel (`tailscale funnel --bg 8787`, stable `*.ts.net` URL in `TUNNEL_URL`); fallback: the Cloudflare Worker front door in `infra/worker-frontdoor/`.
- **LLM:** `anthropic` SDK. `AnthropicBedrockMantle` (models `anthropic.claude-sonnet-5-5`, `anthropic.claude-haiku-5-5`) with fallback to `Anthropic()`. Use one `llm()` factory in `core/llm.py`. No boto3 Converse.
- **Kit:** Vite + React + TypeScript, `fast-json-patch`, `zod`, `qrcode.react`, `vite-plugin-pwa`. Realtime = one WebSocket to Core (no SSE: quick tunnels buffer it; no direct browser→SurrealDB). Visual tokens and screens: `design/*.dc.html`, interaction/state rules in `design/INTERACTIONS.md` (read it before building any card), DECISIONS D8/D17–D23.
- **Daytona:** `daytona` Python SDK; snapshot `village-kit`; Core reverse-proxies `/v/{id}/*` to the sandbox.
- **ElevenLabs:** agents as code in `agents/` (ElevenLabs CLI); webhooks into `core/voice/`.
- **SurrealDB:** Cloud instance (operational, LIVE SELECT) plus Agent Memory (`pip install --pre 'surrealdb[memory]'`; raw httpx for `observed_at` and uncertainty resolve).
- **Anchor:** `anchorbrowser>=1.0.1` (`AsyncAnchorbrowser`, env `ANCHORBROWSER_API_KEY`) plus Playwright `connect_over_cdp`.
- **Arize:** `arize-otel` `register()`, `openinference-instrumentation-anthropic`, OITracer decorators.

## Integration gotchas (verified)
- SurrealDB `record<...>` fields need `RecordID("village","reyes")`, never strings; Core maps contract ids (`v_reyes`, `m_marco`) to record ids on every write. `DEFINE` statements can't take `$params`; inline literals. The `event.kind` ASSERT list must equal `contracts/schemas/event.schema.json` kinds.
- Serve the built app from Core (download `dist/` from the sandbox after tests pass); Daytona = build + test + caught failure. The in-app verification prompt is primary; the outbound call is secondary. See ARCHITECTURE-VALIDATION.md §4.

## Rules that matter
1. **Safety path is deterministic.** `core/gate/` is pure Python with no LLM calls, no Agent Memory reads and no network. Every gate change needs a test in `core/gate/tests/`. Run `uv run pytest core/gate -q` before every commit that touches it. Tests run with the model OFF.
2. **The agent acts on its own; code draws the lines it can't cross.** Voice tools, app actions and spec patches all go through the gate. Generated UI never writes data directly.
3. **Catalog-only UI.** The builder emits specs from the fixed catalog in SPEC §4.3. Unknown types render nothing. Validate with pydantic on the server and zod on the client. On failure: one repair retry, then the template fallback in `data/`.
4. **Trace everything.** Every agent step, tool call, gate decision (GUARDRAIL span) and build or QA step is a span with `graph.node.id`/`graph.node.parent_id`, `session.id=village-<id>`, and `user.id` where known.
5. **Provenance on every write.** Each event carries `source{kind, ref, secs|url}`. Agent Memory writes carry labels `src=…`, `agent=…`, `village=…`.
6. **Idempotent webhooks.** Key on `(conversation_id, tool_call_id)` and return the cached decision for duplicates.
7. **Secrets** stay in `.env` (never commit it). Never log keys. `.env.example` lists every variable.
8. **No placeholder metrics** in README, Devpost or the pitch. Measure them.
9. **Commit small and often** with clear messages. The judges will read the history.

## Subagent lanes (each owns its folder; don't edit others' folders without asking)
| Lane | Folder | First task |
|---|---|---|
| core (main session) | `core/` except listed subfolders | app, settings, llm, tracing, memory svc, live, proxy, control room |
| gate | `core/gate/` | rules + 27 tests from `data/datasets/policy_cases.md` |
| builder | `core/builder/`, `evals/` | render/patch tools, validation, Prompt Hub fetch, experiments, improve loop |
| kit | `kit/` | catalog components, renderer, `useLive`, elder/family themes, PWA |
| integrations | `core/daytona_svc.py`, `core/anchor_svc.py` | snapshot sandbox build/serve, QA release gate, official-page reads |
| voice | `agents/`, `core/voice/` | mom-line, setup, village-caller configs; tool + init + post-call webhooks; outbound calls |

## Useful references (local, offline)
- Sponsor docs: `docs/` (grep the llms-full files), and the installed skills `daytona`, `anchorbrowser-cli`, `surrealdb-agent-memory-docs`, `surrealdb-js`, `surrealdb-python`, `arize-*`, `agents` (ElevenLabs).
- Each `research/<sponsor>.md` ends with "Recommended decisions" and "Open risks"; read the relevant one before integrating a sponsor.
- Results of last night's smoke tests: `RESULTS.md` (overrides research where they disagree).

## Commands
```
uv run uvicorn core.app:app --reload --port 8790
uv run pytest -q
cd kit && npm run dev
/Applications/Tailscale.app/Contents/MacOS/Tailscale funnel --bg 8787
./scripts/reset_demo.sh
```
