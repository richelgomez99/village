# Village

**Village: software that builds itself around your people.**

Talk to Village about your people. It builds what each of them needs, runs it, and rebuilds itself as life changes, without ever acting alone.

Built in one day at the Daytona HackSprint NYC (Oct 16 2026). The demo group is the Reyes family: Carmen, 78, alone in Queens, who speaks Spanish and won't use apps; her daughter Ana, who coordinates; her son Marco, who works shifts. Scammers took $7.75B from older Americans in 2025. A call from "Marco" asking Carmen for $2,000 is the moment the whole product is built around.

---

## The demo arc: Build, Run, Rebuild, Anyone

| Beat | What happens | What it proves |
|---|---|---|
| **Build** | Ana talks to Village about her family. Village asks one or two follow-ups, figures out who's who and what could go wrong, and builds a different app for each person. Judges scan a QR code to join. | Software made per person, not per market |
| **Run** | A caller claiming to be Marco asks Carmen for money. Village tells her (in Spanish, word for word) "Voy a confirmar con Marco ahora mismo. No mande dinero todavía," then checks with the real Marco on his own phone. He taps "That wasn't me." If nobody answers, the safe default is "don't send." | Rules are code, not prompts |
| **Rebuild** | After the second attempt, Village proposes a change to its own software: "Let me answer unknown callers for Mamá." Ana says yes. The change is built and tested in a Daytona sandbox, used by an Anchor browser at phone size, scored by Arize, and then every phone in the room changes. The presenter calls Carmen's line as the scammer; Village answers first and refuses to put him through. | It changes itself, but only after testing and a human yes |
| **Anyone** | The same engine, a different group: a city block during a blackout, generated earlier today. | Not a caregiving app; a way to build one for any group |

Which of these beats runs live today is tracked in [What is real vs mocked today](#what-is-real-vs-mocked-today). The version plan is in `LAYERS.md`.

---

## Architecture

Core is the only hub. Phones, the voice line and the browser checker call Core; Core calls the sponsors. Daytona sandboxes never call out (egress is blocked by design; Core pulls results).

```
 Ana (browser, voice or text) ──► ElevenLabs "setup" agent ──webhook (HTTPS)──┐
 Carmen (phone) ─PSTN─► Twilio ─► ElevenLabs "mom-line" ──── tool webhooks ───┤  via Tailscale Funnel
 Marco (phone)  ◄─PSTN─ Twilio ◄─ ElevenLabs outbound call ◄──── API ─────────┤  (public HTTPS URL to the Mac)
 Phones (web app) ──── HTTPS + WebSocket ────────────────────────────────────►│
                                                                              │
          ┌───────────────────────────── CORE (FastAPI, :8787) ───────────────┴──────────┐
          │ /tools/*  ─►  gate (pure Python, no model)  ─►  decision row  ─►  write        │
          │ verification + dose-window state machines · WebSocket hub · change feed     │
          └────┬──────────────────┬────────────────┬──────────────┬──────────────┬───────┘
               │                  │                │              │              │
        SurrealDB Cloud      Claude on AWS      Daytona        Anchor         Arize
        records + LIVE       Bedrock            build + test   phone-size     traces, guardrail
        push to phones       (Haiku 4.5)        each version   browser run    spans, evals
```

The agent is a hand-written tool-use loop over Claude with five roles (Founder, Watcher, Verifier, Builder, Explainer). Every tool call that changes something is a proposal; the gate decides allow, deny, or ask a human. Details: `AGENT.md`.

---

## How to run

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
cp .env.example .env            # fill in what you have; Core runs with none of it set
uv sync
uv run uvicorn core.app:app --port 8787
```

In a second terminal, the phone app (the `kit/` folder; it lands in `main` when the kit lane merges):

```bash
cd kit && npm install && npm run dev
```

Reset the demo to a known state (clears today's events, verifications, proposals and tokens; reloads the Reyes fixtures; warms sandboxes; sets the clock to Friday 20:50 ET):

```bash
scripts/reset_demo.sh
```

Tests and acceptance:

```bash
uv run pytest -q                # core + gate tests, model off, no network
acceptance/run.sh V0            # the V0 demo-path check
scripts/acceptance_summary.sh   # which acceptance checks exist and pass, and the version tags
```

With no SurrealDB URL set, Core uses an in-process store with the same interface. With `VILLAGE_LLM=off` (the test default), no model is called.

---

## Stack: each sponsor's job in the loop

| Sponsor | Its job | Where |
|---|---|---|
| **Daytona** | Builds and tests every version of a group's software in an isolated sandbox before it reaches anyone. A failing build is caught and fixed in the same loop. | release lane (`core/release/`, in progress) |
| **Arize** | Traces every step the agent takes, with the gate's decisions as guardrail spans. Evals on calls detect the scam pattern that triggers the rebuild; release evals score each version; the scam eval set gives the measured number. | `core/obs/`, `evals/` (in progress) |
| **SurrealDB** | The shared record: villages, members, events, decisions, verifications. LIVE queries push every change to every phone. Agent Memory keeps facts with their source and history (lisinopril 5 mg superseded by 10 mg, never overwritten). | `core/db.py`, `core/live.py`, `core/schema.surql` |
| **ElevenLabs** | The voice for the person who won't use apps: Carmen's Spanish phone line with safety lines spoken word for word, and the outbound call that checks with Marco. | `agents/`, `core/voice/` |
| **Anchor Browser** | A real browser at phone size uses every generated version the way Carmen would before it is released; the live view goes on the projector. | release lane (in progress) |
| **AWS Bedrock** | Claude does the reasoning. The lab account gives us Claude Haiku 4.5 only, so every role runs on Haiku 4.5 today. | `core/llm.py` |
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
| **P-QH-01** | No non-emergency calls to Carmen in her quiet hours; the family still gets escalations. | `test_T27_quiet_hours_suppress_care_recipient_call_but_not_family_escalation` |

49 gate tests pass offline (`uv run pytest core/gate -q`), per `RESULTS.md`.

---

## What is real vs mocked today

Updated from `LANE-REPORT.md` at each merge. As of the voice merge (core, gate and voice code in `main`, 10:43):

**Real and tested in `main`**
- The gate: all rules above, the verification state machine (pending, confirmed, denied, timeout, late answers, duplicates) and the dose-window state machine, with tests that run with the model off.
- The spine: a tool call (`POST /tools/log_dose`) goes through the gate, is written to SurrealDB Cloud, comes back on the change feed, and reaches every connected WebSocket client. Measured below.
- Prescription history with supersession (lisinopril 5 mg to 10 mg) served from the Reyes fixtures.
- Verification rows persisted with compare-and-swap; duplicate webhooks for the same tool call return the same cached decision and create one verification.
- The demo clock (`POST /clock/warp`) and the fixture seed.

**Partly real**
- SurrealDB: Cloud writes work; Core keeps an in-process mirror, and the local asyncio feed is the live source the acceptance test uses. Agent Memory is not wired yet.
- The model: `core/llm.py` calls Claude Haiku 4.5 on Bedrock when enabled; tests run with it off.
- `POST /admin/reset` accepts the scope list but resets the whole Reyes village regardless of scopes.

**Stubbed or not merged yet**
- `core.tools.warm` prints "warm OK (stub)": no Daytona sandbox or Anchor session is pre-warmed yet.
- Voice (`agents/`, `core/voice/`): the ElevenLabs agent configs, tool webhooks, init hook, post-call hook and outbound-call code are merged and tested, but against fakes. Live agent, tool and procedure pushes are still dry-run; the outbound call uses a fake dialer because Twilio geographic permissions block live calls. ElevenLabs text to speech works live.
- Phone app (`kit/`), founding and generation (`003-founding-generation`, model-off template path today), release pipeline with Daytona + Anchor + Arize (`005-release-gate`), memory and rebuild (`006-memory-evolve`): on their branches, not in `main`.
- Receptionist mode (the rebuild's change, D19) is V4 work behind a flag; not built.

---

## Measured numbers

Only numbers from `RESULTS.md`. Anything not there is not claimed.

| What | Result |
|---|---|
| Tool call to last WebSocket frame on 3 clients (gate + SurrealDB Cloud write + change feed) | about 130 ms |
| SurrealDB Cloud LIVE, insert to notification (10 of 10 delivered) | p50 22 ms, p95 77 ms, max 103 ms |
| Claude Haiku 4.5 on Bedrock, time to first token | about 520–600 ms |
| ElevenLabs text to speech (50 KB mp3) | 656 ms |
| Tests passing offline | 16 core + 49 gate |
| Scam eval set (30 scams, 20 benign calls) | [MEASURE: scams caught / 30, false alarms / 20] |
| Rebuild, approval to every phone changed | [MEASURE: seconds] |
| Village's rounds: acted alone / asked a human / refused | [MEASURE: counts from one nightly round] |

---

## Decision log

Every design call and its reason is in `DECISIONS.md`. How the day itself was run (who built what, what was cut and why) starts at **D25**. Version map and cut lines: `LAYERS.md`.

---

## Team

Solo builder: **Richel Gomez**. The work was orchestrated by a Claude session that wrote the specs, briefed each lane, merged and tested. Implementation lanes were Codex sessions (core, gate, voice) and Claude sessions (kit, release, pitch), each in its own git worktree (DECISIONS D25, D26).
