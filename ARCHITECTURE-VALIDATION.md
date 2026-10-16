# Architecture validation: how the stack talks, and what's proven (Oct 16, ~1:30am)

Legend: **✅ verified** (run here or in a subagent with real calls/SDKs), **🟡 likely** (docs + SDK signatures checked, not run), **🔴 unverified** (must test on the Mac tonight or first thing). The spine test (`scratchpad/t_spine.py`) ran a full webhook → gate → SurrealDB → LIVE → WebSocket chain to 12 clients: **p50 2.3 ms local, gate+write 1.1 ms**.

## 1. The map (D15: Build → Run → Rebuild)
```
 Ana (browser mic) ─WebRTC─► ElevenLabs "setup" agent ─webhook (HTTPS)─┐
 Carmen (phone) ─PSTN─► Twilio ─► ElevenLabs "mom-line" ─webhooks─────┤  all via Tailscale Funnel
 Marco (phone)  ◄─PSTN─ Twilio ◄─ ElevenLabs "village-caller" ◄─API───┤  https://richel-macbook.tail8feae0.ts.net
 Phones (PWA) ─HTTPS + WebSocket─────────────────────────────────────►│
                                                              ┌──────┴──────────────── CORE (FastAPI, Mac, :8787) ─────────────────────┐
                                                              │ gate (pure) · verification/dose SMs · WS hub · LIVE subscriber · proxy │
                                                              └───┬────────────┬──────────────┬─────────────┬─────────────┬────────────┘
                                                                  │            │              │             │             │
                                              SurrealDB Cloud (wss)  Agent Memory (REST)  Bedrock Mantle  Daytona (SDK)  Anchor (SDK+CDP)   Arize (OTLP gRPC)
                                              operational + LIVE     facts w/ provenance   Claude 5.5      build+test     real browser QA   traces + evals
```
Core is the only hub. Nothing calls Core except phones, ElevenLabs webhooks and Anchor's browser (which loads the app like a phone). Daytona sandboxes never call out to Core (egress allowlist).

## 2. Edge by edge
| # | Edge | Protocol / lib | Status | Evidence | Risk + mitigation |
|---|---|---|---|---|---|
| 1 | Phone → Core (app, API, WS) | HTTPS + WSS via **Tailscale Funnel** | 🟡 | Funnel's proxy tested via `tailscale serve`: no interstitial, WS ok. Funnel itself not enabled yet (admin click) | Venue DNS may block `ts.net`; fallback Worker front door (`infra/worker-frontdoor`) or quick tunnel. **Never SSE** (quick tunnels buffer it: ✅ measured 8 s) |
| 2 | Core ↔ SurrealDB Cloud | WSS RPC, Python SDK 3.0b | 🟡 | ✅ Local 3.3.4: schema (SCHEMAFULL, record access), LIVE p50 1.3 ms, CAS, live view patches, spine test | Cloud free instance (0.25 vCPU) latency unknown; fallback `surreal start memory` on the Mac (same code). **Gotcha found:** `record<village>` fields need `RecordID("village","reyes")`, not strings; contract ids like `v_reyes` must map to record ids in Core. `DEFINE` can't take `$params`; inline literals |
| 3 | Core → phones (fan-out) | LIVE SELECT → WS hub | ✅ | spine test, 12 clients, p50 2.3 ms local | Single process; fine for ~30 phones. Reconnect = fresh snapshot |
| 4 | ElevenLabs → Core (tools, init, post-call) | HTTPS webhooks, HMAC on post-call | 🟡 | Research: body = our schema; `system__*` dynamic vars; timeout 1–120 s | Init webhook must return **all** declared vars or the call fails. Log the raw first body. Round trip via Funnel ≈ 50–100 ms |
| 5 | Mom-line → `await_verification` (blocking) | tool `response_timeout_secs` ≤ 120 | 🟡 | Procedures: tool → branch on `gate_decision` → `say` verbatim [VERIFY interpolation] | Holding Carmen 30–40 s needs a filler (procedure `say` first + `tool_call_sound`). **In-app prompt is primary** (instant); the call is secondary |
| 6 | Core → Marco (outbound) | ElevenLabs `POST /v1/convai/twilio/outbound-call` → Twilio | 🟡 | API + payload documented; consent gate in Core | **Twilio must be upgraded** (trial = verified numbers only). Ring + answer can exceed the wait → app prompt answers first; if the call lands later, Village calls Carmen back (nice-to-have) |
| 7 | Ana → founding conversation | `@elevenlabs/react` WebRTC, conversation token from Core | 🟡 | SDK + token flow documented; origin must be on the agent allowlist | Mic + HTTPS required (Funnel ok). **Fallback: text box → builder** (no voice) |
| 8 | Core → Claude | `AnthropicBedrockMantle` (SigV4) → fallback `Anthropic()` | 🟡 | ✅ SigV4 path reaches the Mantle endpoint (401 with fake creds); instrumentor emits spans | 5.5 access on the lab account unknown → probe Sonnet 5.5 / Sonnet 5 / Haiku 4.5 at 09:45. Creds expire (~1 h?) → rebuild client on 403; Anthropic key as fallback |
| 9 | Builder output → spec | tool-use `render_app`/`patch_app`, pydantic, template fallback | ✅ | contracts/ validate: 10 schemas, 15 examples, 6 fixtures, OpenAPI 3.1 | Strict/structured outputs not on Mantle → validate + 1 repair. Flat adjacency list avoids recursion |
| 10 | Core → Daytona | Python SDK: snapshot, `fs.upload_files`, session cmd + log stream | 🟡 | SDK calls per docs; egress allowlist known | Snapshot build time unknown (build tonight). 15-min auto-stop → `auto_stop_interval=0`. Tier-1 ≈ 2 medium sandboxes |
| 11 | Phones → generated app | **Option A:** Core proxies `/v/{id}` to Daytona preview (token + skip-warning headers). **Option B (recommended):** after tests pass Core `fs.download_file`s `dist/` and serves it itself | 🟡 / ✅ | Proxy needs streaming + token refresh after stop/start; serving static from Core is trivial | **Choose B.** Daytona stays load-bearing (build + test + the caught failure); the signed preview URL remains the "direct link" talking point. Removes CORS/interstitial/egress risk from the demo path |
| 12 | Core → Anchor QA | `AsyncAnchorbrowser` session + Playwright `connect_over_cdp` → opens the app URL (public Funnel) | 🟡 | SDK 1.0.1 names verified; live view iframes (no X-Frame-Options ✅) | Session create 1.5–4 s → **pre-warm**. Free plan: 5 concurrent. Anchor's browser opens a WS to Core like a phone: fine |
| 13 | Core → Arize | `arize-otel` OTLP gRPC + `update_evaluations` | 🟡 | SDK ✅; `force_flush` returns True even with fake keys ⚠️ | Verify spans in the UI tonight. Online-eval index lag (minutes–hours) → compute evals in-process, log them, keep local copies for the "reads its own evals" step |
| 14 | Core → Agent Memory | REST (`/facts` triples + labels, `/query`, `/history`, `/uncertainty`) | 🟡 | ✅ `pip install --pre surrealdb[memory]` on 3.13; SDK lacks `observed_at` → raw httpx | Never on the safety path; write via outbox. Scopes must be registered first |
| 15 | Rebuild pipeline (climax) | Core orchestrates 9→10→12→13→2→3 | 🟡 | Each hop individually plausible; not yet chained | Budget: patch gen 5–10 s + build/tests 10–25 s + Anchor 8–12 s + evals 5–10 s ≈ **30–55 s**. Pre-warm sandbox + Anchor session; the change adds an already-cataloged component; narrate the strip; receipts are the fallback |

## 3. Feasibility verdict
- **V0–V1 (spine + scam loop):** feasible, mostly verified. The only hard external dependencies are Funnel (DNS wait) and Twilio/ElevenLabs config; both have fallbacks (Worker; in-app prompt + web call).
- **V2 (founding + generation):** feasible; the builder is plain tool-use with validation. Latency 15–40 s for blueprint + 3 views in parallel; stream the blueprint so the room has something to watch.
- **V3 (Daytona + Anchor + Arize release gate):** feasible but the most *integration* work (3 SDKs, 2 pre-warms). Serving dist from Core (11-B) removes the riskiest piece.
- **V4 (live rebuild):** feasible at ~30–55 s if V3 is solid and pre-warmed. This is the one place where a recorded fallback must exist before 14:00.
- **Single points of failure:** Funnel (everything), Core process (everything), Bedrock creds (LLM → Anthropic fallback), SurrealDB Cloud (→ local surreal).

## 4. Decisions this validation forces (adopt)
1. **Serve the built app from Core** (download `dist/` after tests); keep Daytona for build + test + caught failure; signed preview URL as a talking point. (11-B)
2. **In-app verification prompt is primary; outbound call secondary.** The demo never depends on the ring.
3. **Record ids:** Core maps contract ids (`v_reyes`, `m_marco`) to `RecordID` on every write; schema `kind` list must equal the contract's event kinds (apply via inline literals).
4. **Evals in-process** (Claude judges + code checks), logged to Arize; the "reads its own evals" step reads Arize via SDK **with a local mirror as fallback**.
5. **Pre-warm at 13:30:** one Daytona sandbox from the snapshot and one Anchor session, kept alive by heartbeat.
6. **Founding fallback:** a text box that feeds the same builder; voice is the preferred path.

## 5. Tonight / 09:45 tests that close the 🔴/🟡 gaps (in order)
1. Enable Funnel; open `https://richel-macbook.tail8feae0.ts.net/health` from the phone on cellular **and** a WS echo (smoke 08 + `wscat`).
2. Twilio upgrade; import the number into ElevenLabs; make one inbound call that hits `/tools/log` on the Mac (smoke 09); one outbound call to your phone.
3. SurrealDB Cloud: create the free instance + Agent Memory context; run smoke 06/06b against Cloud (latency).
4. Arize: smoke 07, then confirm the span in the UI.
5. Daytona: smoke 02 (egress), 04 (snapshot build time), 03 (preview); time `vite build` in the sandbox.
6. Anchor: smoke 05; time create_session; iframe the live view.
7. 09:45: Bedrock probe (smoke 01) with lab creds.
