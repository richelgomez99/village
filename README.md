# Village

**Village: software that builds itself around your people.**

Talk to Village about your people. It builds what each of them needs, runs it, and rebuilds itself as life changes, without ever acting alone.

Built in one day at the Daytona HackSprint NYC (Oct 16 2026). Village is a platform; this repo shows two villages it built. The first is the Reyes family: Carmen, 78, alone in Queens, who speaks Spanish and won't use apps; her daughter Ana, who coordinates; her son Marco, who works shifts. The second is a city block on West 147th Street during a blackout. Scammers took $7.75B from older Americans in 2025, and a call from "Marco" asking Carmen for $2,000 is the moment the Reyes demo is built around.

---

**Code:** https://github.com/richelgomez99/village (public; the commit history is the day's log; `DECISIONS.md` D25–D39 are the decisions made during the hackathon).

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

**One renderer, apps shaped like jobs.** The catalog gained six components in contract 1.3.0, all generic: **Right now** (who's on tonight, what's happened today), **What Village did** (what it did on its own, what it asked, what it refused), **Since your turn** (what happened since your last shift), **Plan board** (who brings what, by when), **Screened calls** (who called claiming to be whom, and what Village did), and **Fact card** (what Village knows, with its source and history). **Tabs come from life areas:** each person's bottom tabs are the parts of the group's life their job touches, plus Chat. Ana touches all of them (Home · Pills · Money · People · Chat); Lucía touches one. Nothing in the app code decides who gets what; the spec does.

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

**Same code, no Reyes-specific code outside `data/`** (DECISIONS D30). Verified at 12:30: searching `core/` for the Reyes family's names returns nothing outside the Watcher's test fixtures (it was 231 hits in 35 files). One Core serves both villages, and one gate test runs the same rules against both specs: Carmen's quiet hours (21:30–07:00) suppress a 21:50 reminder for Reyes and not for the block; the money default names each village's own coordinator.

---

## What Village knows

The fact-history card (`docs/hero/phone-ana-fact.png`, Ana's Pills tab): lisinopril is 10 mg since Oct 3, from a call (conv_setup_0003, 88 s in: "The doctor changed her lisinopril from five to ten on October third."). The 5 mg fact is kept as history, not overwritten, and asking "as of Oct 2" returns 5 mg. Facts are typed, time-aware, supersede rather than overwrite, are traced to their source, and are shared across agents (SurrealDB Agent Memory, `core/memory/`).

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
uv run pytest -q                # 379 Python tests, model off, no network
cd kit && npm test              # 114 kit tests
acceptance/run.sh V1            # demo-path checks per version
scripts/acceptance_summary.sh   # which acceptance checks exist and pass, and the version tags
```

With no SurrealDB URL set, Core uses an in-process store with the same interface. With `VILLAGE_LLM=off` (the test default), no model is called.

---

## Sponsors: what each one does in Village

Three bullets, one measured number (`RESULTS.md`) and the code for each. Twilio carries the phone calls under ElevenLabs.

### Daytona: build and test every version before anyone sees it
- Every version of a village's software is built in a Daytona sandbox: upload → `vite build` → floor tests generated for that village (elder text at least 28 px, contrast at least 7:1, buttons at least 88 px, a 911 contact) → `dist` download. Sandboxes start from an image, because snapshot creation is denied on our tier; one warm sandbox is reused by label.
- The Builder fixed its own failing build: rev 3 was blocked with "contrast 4.1:1 on elder Text (needs 7:1)", the model changed #4C80B4 to #2D5A8C, Daytona rebuilt and rev 4 went live.
- Sandbox egress is blocked by design: code an AI wrote for a family can't reach the internet; Core pulls the results out.

**Measured:** Reyes release 14957 ms warm; West 147th block 13409 ms with 33 floor tests.  
**Code:** `core/release/pipeline.py`, `core/release/floor_tests.py`, `core/release/daytona_svc.py`, `scripts/release_smoke.py`  
[PENDING 14:00: receipt line "Built in Daytona sandbox `<id>` · 33/33 floor tests · build 2.1 s"]

### SurrealDB: shared, time-aware memory, pushed live to every phone
- SurrealDB Cloud LIVE queries fan every change out to every phone: a check-in reaches all three family phones in about 130 ms.
- Agent Memory facts are typed, time-aware, supersede rather than overwrite, and are traced to their source: lisinopril is 10 mg since Oct 3 (source: call conv_setup_0003 at 88 s, "The doctor changed her lisinopril from five to ten on October third."), the 5 mg fact is kept as history, and asking "as of Oct 2" returns 5 mg.
- The memory is shared across agents: the voice line's post-call transcripts, the ledger and the Watcher's nightly rounds write and read the same facts, scoped per village and per member; the fact card shows who wrote each fact ("written by voice", "written by seed").

**Measured:** Agent Memory writes p50 630 ms; LIVE fan-out to three phones about 130 ms.  
**Code:** `core/db.py`, `core/live.py`, `core/memory/`

### Arize: the agent's senses, and what decides a release ships
- Every agent step is a span with `session.id=village-<id>`; every gate decision is a GUARDRAIL span; every release eval is an EVALUATOR span.
- The scam eval set runs as an Arize experiment (dataset `village-scam-eval`, experiment `scam-model-20261016T153959Z`).
- The Watcher reads its own evals and traces to propose changes: a session eval flagged the Oct 9 call as possible fraud (0.95), and that pattern is the evidence behind the receptionist proposal.

**Measured:** 30/30 scam calls caught, 0/20 false alarms on our 50-case eval set.  
**Code:** `core/obs/tracing.py`, `evals/`, `core/release/evals.py`

### Anchor Browser: a real phone-sized browser checks every build
- Every candidate build is opened in an Anchor browser at phone size (390×844) and clicked through before release.
- The receipt carries a screenshot and the live-view URL as evidence.
- A build Anchor hasn't checked doesn't reach anyone's phone.

**Measured:** 5.2 s per check, warm (5211 ms).  
**Code:** `core/release/anchor_qa.py`  
[PENDING 14:00: the session recording (MP4) linked on the receipt in place of the live-view URL]

### ElevenLabs: the whole product, for the person who won't use apps
- Carmen's Village line is a real number, +1 848 257 9221, in Spanish, formal (usted), and it says it's a program before anything else.
- Mid-call tools `report_money_request` and `await_verification` call Core; the gate's lines are spoken word for word ("Ese no era Marco. No mande dinero.").
- First live call at 12:23, end to end: init webhook → `report_money_request` → Marco's tap on his own phone → the refusal spoken to the caller.

**Measured:** text to speech 656 ms for a 50 KB clip.  
**Code:** `agents/`, `core/voice/` (success-evaluation criteria and data collection are in `agents/agent_configs/mom-line.json`; [PENDING: confirm they are pushed to the live agent])

### AWS: the reasoning fallback that kept the day running
- Claude Haiku 4.5 on Bedrock (Mantle) is the fallback model; in the morning, before the Anthropic key worked, it ran every role, and it ran the scam extraction, the release evals and the Builder's repair.
- The primary path is the direct Anthropic API with Claude Sonnet 5.5 and Haiku 5.5 (the founding intake ran on Sonnet 5.5), through one `llm()` factory that falls back to Bedrock.
- The scam eval set's model-on run (30/30, 0/20) used Bedrock Haiku 4.5 for extraction; a Bedrock Haiku 4.5 blueprint stream starts in 1.1 s.

**Measured:** time to first token about 520–600 ms on Bedrock Haiku 4.5.  
**Code:** `core/llm.py`  
[PENDING 14:00: model chip on the receipt, "Bedrock · claude-haiku-4-5"]

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

114 gate tests pass offline with the model off (`uv run pytest core/gate -q`, gate lane report).

---

## What is real vs mocked today

Updated from `LANE-REPORT.md` at each merge. Tags in `main`: V0-green, V1-green, core-v2, kit-v2, release-v3, memory-v4, evals-v4.

**What ran live today, what was recorded, what is designed only.** Live on the demo Core: the first real call to Carmen's line (12:23: the money report, Marco's tap on his own phone, the refusal spoken) and the live rebuild (13:00: Ana tapped Approve, every phone patched 12 s later). Live on a test Core: Thanksgiving through the family chat (proposal, approval, each app grows the right card). Recorded: the founding conversation, replayed at its own pace on stage (Sonnet 5.5, this morning). Designed only: everything under "What's next".

**Real and tested**
- The gate: the rules above, the verification state machine and the dose-window state machine, 114 tests with the model off.
- The spine: tool call → gate → SurrealDB Cloud write → change feed → every connected phone, about 130 ms to the last of 3 clients.
- The verification loop in Core: prompt frames go only to the claimed member; answers commit with compare-and-swap; past-deadline checks time out to the safe default, including after a restart; duplicate webhooks return the same decision.
- The release pipeline with real Daytona, real Anchor and Arize export, for both villages (numbers above), including the caught-and-fixed build.
- Agent Memory with real SurrealDB: facts with sources, supersession and as-of queries.
- The nightly round on seeded data: 3 things done alone, 1 question to a person, 1 refused.
- The rebuild loop: a resolved verification triggers a proposal (receptionist chosen over two other options), Ana's yes runs the real release pipeline and patches every phone in 7705 ms.
- The first live call to Carmen's line (12:23): init webhook → `report_money_request` → Marco's tap → refusal spoken.
- The scam eval set as an Arize experiment: 30/30 caught, 0/20 false alarms on our 50-case set.
- The Control Room and phone apps (`kit/`), 57 tests, runnable offline against a fake Core.

**Partly real**
- Voice: agent configs, tool webhooks, init and post-call hooks are merged and tested against fakes; live agent and procedure pushes are still dry-run. ElevenLabs text to speech works live.
- The outbound call to Marco uses a fake dialer in tests; live calls were blocked by Twilio geographic permissions at last report.
- Anchor checks static views at phone size; the scam and scan tap flows are not run yet.
- Anchor reached the build through Daytona's signed preview, not yet through Core's public URL.
- The Anthropic API key returned 400 until a workspace id was supplied; the release pipeline and scam evals were measured on Bedrock Haiku 4.5, the founding intake on Sonnet 5.5.

**Not built or not merged yet**
- Founding intake (D29): runs as a replay of the recorded intake (real model, real DailyMed check); the consent call's answer is scripted, and the live-voice intake is not yet run end to end.
- Receptionist mode on the live phone line (`screen_caller` voice tool exists; the stage run is the V4 beat).

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
| Tests | 379 Python (114 of them gate), 114 kit |
| Founding intake, full 11 questions to a valid spec and three apps (Sonnet 5.5) | 65.8 s total; who's-who draft 11.5 s; three apps rendered in 16.9 s; resume path starts at 8 of 10 |
| **Live rebuild on the demo Core (13:00), Ana's yes to every phone patched** | **12 s**, six stages passed |
| Rebuild, evolve lane runs (real pipeline) | 7705 ms (first run 13381 ms) |
| First live call (12:23): hold line / refusal after Marco's tap | 18 s / 31 s into the call |
| Scam pattern to proposal on screen (auto trigger) | 2166 ms |

---

## Decision log

Every design call and its reason is in `DECISIONS.md`. How the day itself was run (who built what, what was cut and why) starts at **D25**; the platform framing is **D30**. Version map and cut lines: `LAYERS.md`.

---

## Team

Solo builder: **Richel Gomez**. A Claude session orchestrated the day: it wrote the specs, briefed each lane, merged, tested and tagged. Codex sessions implemented core, gate, voice and contracts until a shared OpenAI rate limit made them drop turns; from then on Claude sessions implemented core V1, the builder, the phone apps and Control Room, the release pipeline, evals, memory and this pitch kit, each in its own git worktree. Codex remains the implementer of record for the early core, gate, voice and contracts work (DECISIONS D25, D26, D28).
