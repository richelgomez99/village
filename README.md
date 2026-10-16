# Village

**Village: software that builds itself around your people.**

Talk to Village about your people. It builds what each of them needs, runs it, and rebuilds itself as life changes, without ever acting alone.

Built in one day at the Daytona HackSprint NYC (Oct 16 2026). Village is a platform; this repo shows two villages it built. The first is the Reyes family: Carmen, 78, alone in Queens, who speaks Spanish and won't use apps; her daughter Ana, who coordinates; her son Marco, who works shifts. The second is a city block on West 147th Street during a blackout. Scammers took $7.75B from older Americans in 2025, and a call from "Marco" asking Carmen for $2,000 is the moment the Reyes demo is built around.

---

## The demo arc: Build, Run, Rebuild, Anyone

| Beat | What happens | What it proves |
|---|---|---|
| **Build** | The Control Room opens on the platform: a "Village" header, a village switcher, "New village". Ana talks to Village about her family. Village asks one question at a time, reflects back what it heard, and skips what it already knows, until it understands every person, how to reach them, what could go wrong and Carmen's own rules. Then it builds a different app for each person. Judges scan a QR code to join. | Software made per person, not per market |
| **Run** | A caller claiming to be Marco asks Carmen for money. Village tells her (in Spanish, word for word) "Voy a confirmar con Marco ahora mismo. No mande dinero todavía," then checks with the real Marco on his own phone. He taps "That wasn't me." If nobody answers, the safe default is "don't send." | Rules are code, not prompts |
| **Rebuild** | After the second attempt, Village proposes a change to its own software: "Let me answer unknown callers for Mamá." Ana says yes. The change is built and tested in a Daytona sandbox, used by an Anchor browser at phone size, scored by Arize, and then every phone in the room changes. The presenter calls Carmen's line as the scammer; Village answers first and refuses to put him through. | It changes itself, but only after testing and a human yes |
| **Anyone** | Switch to the West 147th Street village: same engine, a completely different group. "Same code, no Reyes anywhere in it. Describe your group and it builds yours." | Not a caregiving app; a way to build one for any group |

Which of these beats runs live today is tracked in [What is real vs mocked today](#what-is-real-vs-mocked-today). The version plan is in `LAYERS.md`.

---

## How Village builds any group

One pipeline, keyed by village id. Nothing in it knows about a particular family.

```
 intake conversation ─► village spec ─► catalog render per role ─► pure gate ─► release pipeline ─────────────────────────────► live patch
 (one question at a     (people, how     (one renderer, one          (rules are    Daytona build + floor tests                     on every phone
  time, 8–12 turns)      to reach them,   component catalog;          parameters    ─► Anchor phone-size run (390×844)              (WebSocket)
                         what could go    each person gets            of the spec:  ─► Arize evals
                         wrong, rules)    their own view)             quiet hours,  ─► blue/green: last good version stays live
                                                                      verifiers,       until the new one passes
                                                                      family word)
```

- **Intake conversation.** The Founder asks one question at a time and ends when it knows every person and role (including outsiders: a neighbor, an aide, the pharmacy), how each may be reached, health, money and impersonation exposure, household needs, and the center person's own rules and consent (DECISIONS D29).
- **Village spec.** Everything the rest of the pipeline needs, as data. Fixtures in `data/` and `contracts/fixtures/` are replays of that output.
- **Catalog render per role.** The same catalog and renderer draw every village's views (`kit/`). Carmen gets three big Spanish buttons; Marco gets one question, "Is it my turn?"
- **Pure gate.** Rules read their values from the spec: Carmen's quiet hours, who may verify, escalation order. The code is the same for every village.
- **Release pipeline.** Every version is built and tested in a Daytona sandbox (floor tests: elder text at least 28 px, contrast at least 7:1, buttons at least 88 px, a 911 contact), run by an Anchor browser at phone size, scored by Arize evals, and only then swapped in (`core/release/`).
- **Live patch.** The new version reaches every connected phone over the WebSocket.

**Both villages, same pipeline (real Daytona, real Anchor, Arize export on; `RESULTS.md`):**

| | Reyes family | West 147th St block |
|---|---|---|
| Release, warm sandbox | 14957 ms (rev 5) | 13409 ms (rev 2) |
| Release, warm, with a caught-and-fixed build | 19908 ms | — |
| Release, cold sandbox, with a caught-and-fixed build | 29731 ms | — |
| Floor tests in the build | [MEASURE: Reyes floor test count from the release receipt] | 33 passing |
| Anchor phone-size run | 5359 ms (warm) | 5398 ms |
| Arize evals | 3096 ms (warm) | 1667 ms |

The caught-and-fixed build: rev 3 was blocked with "contrast 4.1:1 on elder Text (needs 7:1)"; the model changed the color #4C80B4 to #2D5A8C, the build re-ran and rev 4 went live. Trace: AGENT → TOOL daytona_build ✗ → LLM → TOOL daytona_build ✓.

**Same code, no Reyes-specific code outside `data/`** (DECISIONS D30). The platform sweep that enforces this is being verified.

---

## Architecture

Core is the only hub. Phones, the voice line and the browser checker call Core; Core calls the sponsors. Daytona sandboxes never call out (egress is blocked by design; Core pulls results).

```
 Ana (browser, voice or text) ──► ElevenLabs "setup" agent ──webhook (HTTPS)──┐
 Carmen (phone) ─PSTN─► Twilio ─► ElevenLabs "mom-line" ──── tool webhooks ───┤  via Tailscale Funnel
 Marco (phone)  ◄─PSTN─ Twilio ◄─ ElevenLabs outbound call ◄──── API ─────────┤  (public HTTPS URL to the Mac)
 Phones (web app) ──── HTTPS + WebSocket ────────────────────────────────────►│
                                                                              │
          ┌───────────────────────────── CORE (FastAPI) ──────────────────────┴──────────┐
          │ /tools/*  ─►  gate (pure Python, no model)  ─►  decision row  ─►  write        │
          │ verification + dose-window state machines · WebSocket hub · change feed     │
          │ release pipeline · nightly rounds (Watcher) · Agent Memory outbox           │
          └────┬──────────────────┬────────────────┬──────────────┬──────────────┬───────┘
               │                  │                │              │              │
        SurrealDB Cloud      Claude (Anthropic   Daytona        Anchor         Arize
        records + LIVE;      API; Bedrock        build + test   phone-size     traces, guardrail
        Agent Memory facts   fallback)           each version   browser run    spans, evals
```

The agent is a hand-written tool-use loop over Claude with five roles (Founder, Watcher, Verifier, Builder, Explainer). Every tool call that changes something is a proposal; the gate decides allow, deny, or ask a human. Details: `AGENT.md`.

---

## How to run

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
cp .env.example .env            # fill in what you have; Core runs with none of it set
uv sync
uv run uvicorn core.app:app --port 8790    # 8790 per D27; set CORE_URL=http://127.0.0.1:8790 in .env
```

In a second terminal, the phone apps and the Control Room:

```bash
cd kit && npm install && npm run dev
# offline, no Core needed: /control.html?fake=control&seq=founding|scam|release|evolve
```

Reset the demo to a known state (clears today's events, verifications, proposals, tokens and counters; reloads the fixtures; warms the Daytona sandbox; sets the clock to Friday 20:50 ET):

```bash
scripts/reset_demo.sh
```

Tests and acceptance:

```bash
uv run pytest -q                # 245 Python tests, model off, no network
cd kit && npm test              # 57 kit tests
acceptance/run.sh V1            # demo-path checks per version
scripts/acceptance_summary.sh   # which acceptance checks exist and pass, and the version tags
```

With no SurrealDB URL set, Core uses an in-process store with the same interface. With `VILLAGE_LLM=off` (the test default), no model is called.

---

## Stack: each sponsor's job in the loop

| Sponsor | Its job | Where |
|---|---|---|
| **Daytona** | Builds and tests every version of a village's software in an isolated sandbox before it reaches anyone. A failing build is caught, fixed by the Builder and re-released in the same loop. | `core/release/daytona_svc.py`, `core/release/floor_tests.py` |
| **Arize** | Traces every step the agent takes, with the gate's decisions as guardrail spans. Session evals flag the scam pattern that triggers the rebuild; release evals score each version; the scam eval set runs as an Arize experiment. | `core/obs/`, `core/release/evals.py`, `evals/` |
| **SurrealDB** | The shared record: villages, members, events, decisions, verifications, with LIVE queries pushing every change to every phone. Agent Memory keeps facts with their source and history: lisinopril 10 mg since Oct 3 supersedes 5 mg, and asking "as of Sep 15" still returns 5 mg. | `core/db.py`, `core/live.py`, `core/memory/` |
| **ElevenLabs** | The voice for the person who won't use apps: Carmen's Spanish phone line with safety lines spoken word for word, and the outbound call that checks with Marco. | `agents/`, `core/voice/` |
| **Anchor Browser** | A real browser at phone size (390×844) opens every generated version and checks it the way Carmen would see it, with a recording as evidence. | `core/release/anchor_qa.py` |
| **Claude** | The reasoning. Core uses Claude Sonnet 5.5 and Haiku 5.5 through the Anthropic API, with Claude Haiku 4.5 on AWS Bedrock as the fallback. The measured runs on this page used Bedrock Haiku 4.5. | `core/llm.py` |
| Twilio | The phone number Carmen calls and that rings Marco. | via ElevenLabs |

---

## Safety rules (code, tested with the model off)

The gate is pure Python in `core/gate/`. It reads the village's state and a proposed action, and returns a decision and, where something is spoken, the exact sentence. The voice model never chooses a safety sentence. Rule definitions and test cases: `data/datasets/policy_cases.md`.

| Rule | What it says | Test |
|---|---|---|
| **R-MONEY-NEVER** | Village never moves money, buys gift cards or crypto, or asks for, repeats or stores account numbers. No family member can override this. | `test_T42_village_never_moves_money`, `test_T43_money_model_output_blocked` |
| **R-MONEY-VERIFY** | A money request in a family member's name opens a check with that member through a channel the caller doesn't control (their app, their number on file). | `test_T29_money_request_matches_contract_example` |
| **R-MONEY-DEFAULT** | Not confirmed means "don't send," and Ana is told. Even a confirmed request gets "talk to Ana first." | `test_T30_denied_answer_returns_do_not_send`, `test_await_after_30_seconds_sets_default_spoken` |
| **R-MONEY-UNKNOWN** | A caller who isn't in the village ("the bank," a "grandson" who doesn't exist) is treated as unverified. | `test_T36_unknown_claimed_identity_no_verification_and_incident`, `test_T41_unknown_bank_details_redacts_digits` |
| **R-VERIFY-CONSENT** | Village only places verification calls to people who agreed to receive them; everyone else gets the in-app prompt only. | `test_T44_no_ai_call_gets_app_prompt_only`, `test_T38_lucia_gets_app_prompt_only_no_call`, `test_T45_no_reachable_channel_unreachable_default` |
| **R-DOUBLE** | A second dose report only reports ("already recorded at 8:02; I'm telling Marco"). Never dosing advice. | `test_T28_second_lid_scan_reports_only_verbatim`, `test_T05_duplicate_already_happened_escalates_without_dose_advice` |
| **R-911** | Emergency words get "call 911" first, then everyone is notified. Nothing can downgrade it. Village never dials 911 itself. | `test_T17_911_cannot_be_downgraded` |
| **P-QH-01** | No non-emergency calls to Carmen in her quiet hours; the family still gets escalations. In last night's round: "Blocked by code: Carmen's rule, no calls after 9:30 PM." | `test_T27_quiet_hours_suppress_care_recipient_call_but_not_family_escalation` |

110 gate tests pass offline with the model off (`uv run pytest core/gate -q`, gate lane report).

---

## What is real vs mocked today

Updated from `LANE-REPORT.md` at each merge. Tags in `main`: V0-green, V1-green, core-v2, kit-v2, release-v3, memory-v4, evals-v4.

**Real and tested**
- The gate: the rules above, the verification state machine and the dose-window state machine, 110 tests with the model off.
- The spine: tool call → gate → SurrealDB Cloud write → change feed → every connected phone, about 130 ms to the last of 3 clients.
- The verification loop in Core: prompt frames go only to the claimed member; answers commit with compare-and-swap; past-deadline checks time out to the safe default, including after a restart; duplicate webhooks return the same decision.
- The release pipeline with real Daytona, real Anchor and Arize export, for both villages (numbers above), including the caught-and-fixed build.
- Agent Memory with real SurrealDB: facts with sources, supersession and as-of queries.
- The nightly round on seeded data: 3 things done alone, 1 question to a person, 1 refused.
- The scam eval set as an Arize experiment: 30/30 caught, 0/20 false alarms on our 50-case set.
- The Control Room and phone apps (`kit/`), 57 tests, runnable offline against a fake Core.

**Partly real**
- Voice: agent configs, tool webhooks, init and post-call hooks are merged and tested against fakes; live agent and procedure pushes are still dry-run. ElevenLabs text to speech works live.
- The outbound call to Marco uses a fake dialer in tests; live calls were blocked by Twilio geographic permissions at last report.
- Anchor checks static views at phone size; the scam and scan tap flows are not run yet.
- Anchor reached the build through Daytona's signed preview, not yet through Core's public URL.
- The Anthropic API key returned 400 until a workspace id was supplied; measured runs used Bedrock Haiku 4.5.

**Not built or not merged yet**
- The founding intake conversation (D29) and generation (builder lane): not in `main`.
- Receptionist mode (the rebuild's change, D19): V4 work behind a flag.
- The live rebuild on stage, end to end from Ana's yes to every phone: [MEASURE: seconds on stage].
- The platform sweep (no Reyes-specific code outside `data/`, D30): being verified.

---

## Measured numbers

Only numbers from `RESULTS.md` and `LANE-REPORT.md`. Anything not there is not claimed.

| What | Result |
|---|---|
| Scam eval set, model on (Bedrock Haiku 4.5 extraction + pure gate), our 50-case set | **30/30 scams caught, 0/20 false alarms** (49/50 exact decision match); Arize experiment `scam-model-20261016T153959Z` |
| Scam eval set, model off (rules only) | 28/30 caught, 0/20 false alarms |
| Release, warm (Reyes rev 5 / West 147th rev 2) | 14957 ms / 13409 ms |
| Release, cold, with a caught-and-fixed build | 29731 ms |
| Nightly round (seeded data, budget 3) | 3 acted alone · 1 asked a person · 1 refused |
| Tool call to last WebSocket frame on 3 clients | about 130 ms |
| SurrealDB Cloud LIVE, insert to notification (10/10) | p50 22 ms, p95 77 ms, max 103 ms |
| Agent Memory write / history / recall query | p50 630 ms / p50 248 ms / 3.7 s (never on a request path) |
| Claude Haiku 4.5 on Bedrock, time to first token | about 520–600 ms |
| ElevenLabs text to speech (50 KB mp3) | 656 ms |
| Tests | 245 Python (110 of them gate), 57 kit |
| Founding, conversation to three apps | [MEASURE: seconds] |
| Live rebuild on stage, Ana's yes to every phone changed | [MEASURE: seconds] |

---

## Decision log

Every design call and its reason is in `DECISIONS.md`. How the day itself was run (who built what, what was cut and why) starts at **D25**; the platform framing is **D30**. Version map and cut lines: `LAYERS.md`.

---

## Team

Solo builder: **Richel Gomez**. A Claude session orchestrated the day: it wrote the specs, briefed each lane, merged, tested and tagged. Codex sessions implemented core, gate, voice and contracts until a shared OpenAI rate limit made them drop turns; from then on Claude sessions implemented core V1, the builder, the phone apps and Control Room, the release pipeline, evals, memory and this pitch kit, each in its own git worktree. Codex remains the implementer of record for the early core, gate, voice and contracts work (DECISIONS D25, D26, D28).
