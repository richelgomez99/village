# Devpost page, per version

Rules for this file:
- Paste the section for the **latest confirmed version**. A version section stays `[PENDING Vn]` until the orchestrator confirms it on real phones; a lane tag alone is not a confirmation.
- Every number is copied from `RESULTS.md` or `LANE-REPORT.md`, or written `[MEASURE: what]`. Nothing with a `[MEASURE]` or `[PENDING]` left in it gets pasted into Devpost: cut the sentence instead.
- Plain words (DECISIONS D18, LAYERS.md "On stage, plain words only"). No "agentic", "seamless", "intelligent", "leverage", "empower".
- Never claim a P2 or P3 feature works. They go in "What's next" only.
- The scam number is always said with its caveat: "on our 50-case eval set".

Devpost draft link: [PENDING: paste the draft URL once saved]

Tags in `main` at the last merge: V0-green, V1-green, core-v2, kit-v2, release-v3, memory-v4, evals-v4.

---

## Fixed fields (all versions)

**Name:** Village

**Tagline:** Software that builds itself around your people, and rebuilds itself as their life changes, without ever acting alone.

**Built with** (services actually called today, per `RESULTS.md` / `LANE-REPORT.md`):
daytona · arize · surrealdb · surrealdb-agent-memory · elevenlabs · anchor-browser · anthropic-claude · aws-bedrock · twilio · tailscale · python · fastapi · uv · pytest · react · typescript · vite · vitest · playwright

---

## Shared page body (all versions; the version sections below add to it)

### Summary
Village is a platform that turns a conversation about a group of people into working software for each of them, then keeps watch. It built two villages today: the Reyes family (Carmen, 78, alone in Queens, Spanish-speaking, won't use apps; Ana, who coordinates; Marco, who works shifts) and a city block on West 147th Street during a blackout. Every action the agent wants to take goes through a gate written in plain code, every new version is built, tested and tried at phone size before anyone sees it, and on our 50-case scam eval set it caught 30 of 30 scam calls with 0 false alarms out of 20.

**What ran live today, what was recorded, what is designed only.** Live on the demo Core: the first real call to Carmen's line (12:23: the money report, Marco's tap on his own phone, the refusal spoken) and the live rebuild (13:00: Ana tapped Approve, every phone patched 12 s later). Live on a test Core: Thanksgiving through the family chat (proposal, approval, each app grows the right card). Recorded: the founding conversation, replayed at its own pace on stage (Sonnet 5.5, this morning). Designed only: everything under "What's next".

### Inspiration
Older people want to stay in their own homes. What ends that is rarely one big event: a refill where the dose changed and nobody noticed, a call from "your son" asking for $2,000, two siblings each thinking the other was visiting. Scammers took $7.75B from older Americans in 2025. The families doing this work coordinate it in a group chat. Apps are built for millions of people; a family is five. We wanted software made for one group, that changes when their life changes, and that can't be talked into doing the wrong thing.

### How Village builds any group
One pipeline, keyed by village id:
1. **Intake conversation.** Village asks one question at a time (8–12 turns), reflects back what it heard and skips what it already knows, until it understands every person and role (including the neighbor, the aide, the pharmacy), how each may be reached, health, money and impersonation risk, household needs, and the center person's own rules.
2. **Village spec.** All of that, as data.
3. **Catalog render per role.** One renderer and one component catalog draw every person's app. Carmen gets three big Spanish buttons; Ana gets the whole picture; Marco gets one question, "Is it my turn?"
4. **Pure gate.** The safety rules read their values from the spec: Carmen's quiet hours, who may verify, escalation order. Same code for every village.
5. **Release pipeline.** Daytona builds the version and runs the floor tests (elder text at least 28 px, contrast at least 7:1, buttons at least 88 px, a 911 contact) → an Anchor browser runs it at phone size (390×844) → Arize evals score it → blue/green swap, so the last good version stays live until the new one passes.
6. **Live patch.** The new version reaches every connected phone over a WebSocket.

| Same pipeline, real Daytona + Anchor + Arize | Reyes family | West 147th St block |
|---|---|---|
| Release, warm sandbox | 14957 ms | 13409 ms |
| Release, warm, with a caught-and-fixed build | 19908 ms | — |
| Release, cold sandbox, with a caught-and-fixed build | 29731 ms | — |
| Floor tests | [MEASURE: Reyes floor test count] | 33 passing |

**One renderer, apps shaped like jobs.** The catalog gained six components in contract 1.3.0, all generic: **Right now** (who's on tonight, what's happened today), **What Village did** (what it did on its own, what it asked, what it refused), **Since your turn** (what happened since your last shift), **Plan board** (who brings what, by when), **Screened calls** (who called claiming to be whom, and what Village did), and **Fact card** (what Village knows, with its source and history). **Tabs come from life areas:** each person's bottom tabs are the parts of the group's life their job touches, plus Chat. Ana touches all of them (Home · Pills · Money · People · Chat); Lucía touches one. Nothing in the app code decides who gets what; the spec does.

Same code, no Reyes-specific code outside `data/`: verified at 12:30, searching Core for the family's names returns nothing outside test fixtures (it was 231 hits in 35 files). One Core serves both villages, and one gate test runs the same rules against both specs: Carmen's quiet hours (21:30–07:00) suppress a 21:50 reminder for Reyes and not for the block.

### Hero screenshots (gallery order; files in `docs/hero/`, captured from the live Core on 8790)
1. **The scammer never reached her** (V4 GIF) [PENDING: record the receptionist refusal]; until then `room-rebuild.png`.
2. `room-rebuild.png` (1920×1080) / `room-rebuild-full.png`: *"The Control Room during the rebuild: what Village heard, the Watcher's pattern and proposal, its rounds, the family chat, the proposal with its evidence, What Village knows, and the three phones under one address."*
3. `phone-ana-fact.png`: *"What Village knows, and how it knows it. Lisinopril is 10 mg since Oct 3, from a call 1:28 in. The old 5 mg is kept as history, not overwritten, and "As of Oct 2" still shows 5 mg. Typed, time-aware, supersedes rather than overwrites, traced to source, shared across agents: SurrealDB Agent Memory."*
4. `phone-ana.png`: *"Ana's app is a brief: right now, what needs her yes, what Village did."*
5. `phone-ana-did.png`: *"What Village did on its own, what it asked, and what it refused itself: 'Blocked by code: Carmen's rule, no calls after 9:30 PM.'"*
6. `phone-marco.png`: *"Marco's app answers one question: is it my turn?"*
7. `phone-carmen.png`: *"Carmen's app: Spanish, big buttons, read aloud, nothing to learn."*
8. The caught-and-fixed build receipt (rev 3 blocked at contrast 4.1:1, rev 4 live) [PENDING: screenshot].

### Sponsor tools (three bullets, one measured number, the code)

#### Daytona: build and test every version before anyone sees it
- Every version of a village's software is built in a Daytona sandbox: upload → `vite build` → floor tests generated for that village (elder text at least 28 px, contrast at least 7:1, buttons at least 88 px, a 911 contact) → `dist` download. Sandboxes start from an image, because snapshot creation is denied on our tier; one warm sandbox is reused by label.
- The Builder fixed its own failing build: rev 3 was blocked with "contrast 4.1:1 on elder Text (needs 7:1)", the model changed #4C80B4 to #2D5A8C, Daytona rebuilt and rev 4 went live.
- Sandbox egress is blocked by design: code an AI wrote for a family can't reach the internet; Core pulls the results out.

**Measured:** Reyes release 14957 ms warm; West 147th block 13409 ms with 33 floor tests.  
**Code:** `core/release/pipeline.py`, `core/release/floor_tests.py`, `core/release/daytona_svc.py`, `scripts/release_smoke.py`  
[PENDING 14:00: receipt line "Built in Daytona sandbox `<id>` · 33/33 floor tests · build 2.1 s"]

#### SurrealDB: shared, time-aware memory, pushed live to every phone
- SurrealDB Cloud LIVE queries fan every change out to every phone: a check-in reaches all three family phones in about 130 ms.
- Agent Memory facts are typed, time-aware, supersede rather than overwrite, and are traced to their source: lisinopril is 10 mg since Oct 3 (source: call conv_setup_0003 at 88 s, "The doctor changed her lisinopril from five to ten on October third."), the 5 mg fact is kept as history, and asking "as of Oct 2" returns 5 mg.
- The memory is shared across agents: the voice line's post-call transcripts, the ledger and the Watcher's nightly rounds write and read the same facts, scoped per village and per member; the fact card shows who wrote each fact ("written by voice", "written by seed").

**Measured:** Agent Memory writes p50 630 ms; LIVE fan-out to three phones about 130 ms.  
**Code:** `core/db.py`, `core/live.py`, `core/memory/`

#### Arize: the agent's senses, and what decides a release ships
- Every agent step is a span with `session.id=village-<id>`; every gate decision is a GUARDRAIL span; every release eval is an EVALUATOR span.
- The scam eval set runs as an Arize experiment (dataset `village-scam-eval`, experiment `scam-model-20261016T153959Z`).
- The Watcher reads its own evals and traces to propose changes: a session eval flagged the Oct 9 call as possible fraud (0.95), and that pattern is the evidence behind the receptionist proposal.

**Measured:** 30/30 scam calls caught, 0/20 false alarms on our 50-case eval set.  
**Code:** `core/obs/tracing.py`, `evals/`, `core/release/evals.py`

#### Anchor Browser: a real phone-sized browser checks every build
- Every candidate build is opened in an Anchor browser at phone size (390×844) and clicked through before release.
- The receipt carries a screenshot and the live-view URL as evidence.
- A build Anchor hasn't checked doesn't reach anyone's phone.

**Measured:** 5.2 s per check, warm (5211 ms).  
**Code:** `core/release/anchor_qa.py`  
[PENDING 14:00: the session recording (MP4) linked on the receipt in place of the live-view URL]

#### ElevenLabs: the whole product, for the person who won't use apps
- Carmen's Village line is a real number, +1 848 257 9221, in Spanish, formal (usted), and it says it's a program before anything else.
- Mid-call tools `report_money_request` and `await_verification` call Core; the gate's lines are spoken word for word ("Ese no era Marco. No mande dinero.").
- First live call at 12:23, end to end: init webhook → `report_money_request` → Marco's tap on his own phone → the refusal spoken to the caller.

**Measured:** text to speech 656 ms for a 50 KB clip.  
**Code:** `agents/`, `core/voice/` (success-evaluation criteria and data collection are in `agents/agent_configs/mom-line.json`; [PENDING: confirm they are pushed to the live agent])

#### AWS: the reasoning fallback that kept the day running
- Claude Haiku 4.5 on Bedrock (Mantle) is the fallback model; in the morning, before the Anthropic key worked, it ran every role, and it ran the scam extraction, the release evals and the Builder's repair.
- The primary path is the direct Anthropic API with Claude Sonnet 5.5 and Haiku 5.5 (the founding intake ran on Sonnet 5.5), through one `llm()` factory that falls back to Bedrock.
- The scam eval set's model-on run (30/30, 0/20) used Bedrock Haiku 4.5 for extraction; a Bedrock Haiku 4.5 blueprint stream starts in 1.1 s.

**Measured:** time to first token about 520–600 ms on Bedrock Haiku 4.5.  
**Code:** `core/llm.py`  
[PENDING 14:00: model chip on the receipt, "Bedrock · claude-haiku-4-5"]

### How we built it
- **Core:** Python 3.13, FastAPI, one process. The gate (`core/gate/`) is pure Python with no model calls and no network: 114 tests, all passing with the model off.
- **The agent:** a hand-written tool-use loop over Claude with five roles: Founder (the intake), Watcher (nightly rounds, pattern detection), Verifier (the money checks), Builder (changes and releases), Explainer ("Ask Village why"). Every tool call that changes something is a proposal the gate decides.
- **Claude:** Sonnet 5.5 and Haiku 5.5 through the Anthropic API, with Claude Haiku 4.5 on AWS Bedrock as the fallback. The founding intake was measured on Sonnet 5.5; the release pipeline, scam evals and repair on Bedrock Haiku 4.5.
- **SurrealDB Cloud** holds villages, members, events, decisions and verifications; LIVE queries feed a WebSocket hub that pushes each change to every phone (p50 22 ms insert to notification). **SurrealDB Agent Memory** keeps facts with their sources: lisinopril 10 mg since Oct 3 supersedes 5 mg, and an as-of-Sep-15 query still returns 5 mg.
- **Daytona** builds and tests every version in a sandbox that can't reach the internet; Core pulls the results out. **Anchor** opens each build at phone size with a recording. **Arize** traces every step (gate decisions as guardrail spans), scores each release, and ran the scam eval set as an experiment.
- **ElevenLabs** is Carmen's Spanish phone line, with safety sentences spoken word for word, and the call that checks with Marco. **Twilio** carries the calls.
- **Kit:** React + TypeScript + Vite for the phone apps and the Control Room, 57 tests.
- **Contracts first:** JSON Schemas, fixtures and an OpenAPI file (`contracts/`, version 1.2.1) were written before code so parallel lanes could build against the same shapes.
- **How the day was run:** one builder, Richel Gomez. A Claude session orchestrated: specs, briefs, merges, tests, tags. Codex sessions implemented core, gate, voice and contracts until a shared rate limit made them drop turns; then Claude sessions implemented core V1, the builder, the apps and Control Room, the release pipeline, evals, memory and the pitch kit, each in its own git worktree (`DECISIONS.md` D25, D26, D28).

### Challenges we ran into
- **Rate limits while running five implementation lanes at once.** Five Codex sessions shared one OpenAI limit of 1M tokens per minute and kept dropping turns; one lane had zero commits after 20 minutes. We moved lanes to Claude in two steps (D26 at 10:30, D28 at 11:30) and kept Codex as the implementer of record for the early work.
- **Model access.** On the AWS Bedrock lab account only Claude Haiku 4.5 answered; every Sonnet and Opus id returned 404. Haiku 4.5 carried every role until the Anthropic key worked.
- **API key scoped to a workspace.** Our Anthropic API key returned 400 until requests carried the workspace id, so the direct Anthropic path only turns on when that id is set.
- **Daytona snapshot creation was denied** on our account tier, so we keep one warm sandbox from the default image (install once, reuse by label) instead of a prepared snapshot. Cold release: 29.7 s; warm: 15.0 s.
- **Sandbox egress is blocked**, by design: a Daytona sandbox can't reach any outside host. That is what we want for code an AI wrote for a real family, so sandboxes only build and test, and Core pulls the results out.
- **Twilio geographic permissions** blocked live outbound calls to Marco's number, so the call path is tested with a fake dialer while the in-app prompt carries the check.

### Accomplishments we're proud of
- **30/30 scam calls caught, 0/20 false alarms on our 50-case eval set** (Bedrock Haiku 4.5 extraction + the pure gate; Arize experiment `scam-model-20261016T153959Z`). With the model switched off, the rules alone catch 28/30 with 0 false alarms.
- **A build that failed was fixed by the agent itself.** Rev 3 was blocked with "contrast 4.1:1 on elder Text (needs 7:1)"; the Builder changed #4C80B4 to #2D5A8C, the build re-ran in Daytona and rev 4 went live. Trace: AGENT → TOOL daytona_build ✗ → LLM → TOOL daytona_build ✓.
- **Two villages, one pipeline:** Reyes released in 14957 ms warm; the West 147th block in 13409 ms with 33 floor tests passing.
- **Village did things on its own last night, and stopped itself once.** One nightly round on seeded data: 3 things done alone, 1 question to a person ("Ana has taken 9 of the last 12 nights. Ask Lucía to take the Sunday call?"), 1 refused: "Blocked by code: Carmen's rule, no calls after 9:30 PM."
- **379 Python tests and 114 kit tests**, all passing offline with the model off.
- **The rebuild ran live:** at 13:00 on the demo Core, Ana tapped Approve and every phone was patched 12 s later, through six stages (spec, Daytona build, floor tests, Anchor phone-size run, Arize evals, live).

### What we learned
- Putting the rules in code made the AI parts easier to build, not harder: every lane could test against the gate without a model.
- Rules as spec parameters are what make it a platform: Carmen's quiet hours and the block's escalation order are data, read by the same gate.
- A blocked sandbox is a feature when the code inside was written by an AI for someone's mother.
- Measure before you plan the demo: the model you expect may not be on the account.

### What's next (designed, not built today)
The demo protects the center of the village. The rest of a village is the people around her carrying weight together. Designed today (screens on the design canvas, plan in `docs/VILLAGE-FEATURES.md`), not built:
- **Handoffs:** at every turn change, a note to the incoming caregiver written from the day's events.
- **The week in the village:** a weekly page per member, in their language.
- **Consent per affected person:** a change that touches your phone needs your yes, not only the leader's.
- **The charter:** a plain-language page of what Village watches, what it may do alone, what it must ask, and Carmen's own rules.
- **Modes:** hospital stay, a parent away, a blackout, as planned rebuilds with an exit condition.
- **Needs and offers:** who needs what, who can help, one nudge, loop closed.
- **Village makes the boring calls:** pharmacy, clinic, the fraud line.
- **Guest notes:** the visiting nurse leaves a note from the fridge QR code without an account.
- **"What does Village know about me?":** what it holds, who sees it, revoke by voice.
- **Village types:** starting points for a new baby, a recovery circle, a block in a crisis.
- **Governance escalation:** leader unreachable, then co-lead, then a 24-hour hold, then nothing changes.

### Safeguards (claim only rules with a passing test)
Deterministic gate, 114 tests with the model off · verification through a channel the caller doesn't control · calls only to people who agreed · no money movement, no account numbers, no dosing advice · emergency words get "call 911" first and can't be downgraded · Carmen's quiet hours, from her own words · every fact keeps its source · nothing reaches a person untested (Daytona floor tests + Anchor run before every release) · [PENDING V4: a human approves every change to the software, shown live].

---

## V0 · READY · "Village: rules are code, not prompts"

**Headline:** Village: rules are code, not prompts.

**Hero:** Screenshot: three phones (Carmen, Ana, Marco) updating from one check-in, next to the terminal showing the gate tests green with the model switched off. Caption: *"The rules that protect Carmen don't depend on what the model says."*

**What it does (V0):** the safety gate and its money rules; the verification state machine; live family state (check-in → gate → SurrealDB Cloud → every phone in about 130 ms); Marco's refill view showing lisinopril 5 mg → 10 mg on Oct 3 with the old dose kept as history.

---

## V1 · READY (first live call 12:23, verified end to end; clip URL pending) · "When a scammer calls Mom as her son, Village checks with the real son before she sends a dollar"

**Headline:** When a scammer calls Mom as her son, Village checks with the real son before she sends a dollar.

**Hero:** the 30-second clip: Carmen's line on speaker, "Voy a confirmar con Marco ahora mismo. No mande dinero todavía," Marco's phone shows the prompt, he taps "That wasn't me," Carmen hears "Ese no era Marco. No mande dinero. Ana ya lo sabe." English captions. [PENDING V1: clip URL]

**What it does (adds to V0):**
- Carmen calls her Village number (ElevenLabs, Spanish). When she reports a money request "from Marco," the gate holds it and starts a check.
- Marco gets an in-app prompt (and a call, where he agreed to calls): "Did you just call Mamá asking for $2,000?" Either answer counts.
- Village speaks the gate's sentence word for word. If Marco doesn't answer in time: "No pude confirmar con Marco. No mande dinero. Le aviso a Ana."
- Ana gets an incident card. Every step is an Arize trace.
- Scam eval set: 30/30 caught, 0/20 false alarms on our 50-case set.

**Numbers:** first live call (12:23): hold line at 18 s, Marco's tap and the refusal at 31 s.

---

## V2 · [PENDING V2: confirm the intake on the Control Room] · "Describe your people. Village builds what each of them needs."

**Headline:** Describe your people. Village builds what each of them needs.

**What it does (adds to V1):**
- The Control Room opens on the platform: a "Village" header, a switcher between villages, and "New village". An empty village starts with the intake conversation.
- Ana talks to Village about her family; it asks one question at a time until it understands everyone, then builds three different apps from one catalog.
- Same address, different software, because it's a different person. Judges scan a QR code to join; their phones update live.
- "Ask Village why": type "Why did you call Marco and not Lucía?" and it answers from its decision log, citing sources.
- Carmen's own rules: "after 9:30, no calls," in her words, enforced by code.

**Numbers:** full 11-question intake to a valid spec, Sonnet 5.5: 65.8 s (who's-who draft 11.5 s, three apps rendered in 16.9 s). Phones joined during the demo: [MEASURE: count].

---

## V3 · [PENDING V3: confirm on the Control Room] · "Every release built in Daytona, tapped by Anchor, scored by Arize"

**Headline adds:** Every version is built in Daytona, tapped by Anchor, scored by Arize. Nothing reaches Carmen untested.

**What it does (adds to V2):** the release pipeline and both villages' numbers from "How Village builds any group"; the caught-and-fixed build; the West 147th block as the second village.

**Numbers:** Reyes warm 14957 ms, cold with the caught failure 29731 ms; West 147th 13409 ms, 33 floor tests. Anchor phone-size run 5.2–5.4 s warm.

---

## V4 · [PENDING V4: rebuild beat run live on the Control Room] · "Learns from every attempt"

**Headline adds:** It learns from every attempt: 30/30 scams caught, 0/20 false alarms on our 50-case eval set.

**Hero (replaces the V1 clip):** GIF, 8 s: a second phone calls Carmen's line. Village answers first ("Carmen's phone, this is Village. Who's calling?"), checks with the real Marco on his own phone, and refuses the caller. English captions. Caption: *"The scammer never reached her."* [PENDING V4: receptionist mode built and recorded]

**What it does (adds to V3):**
- **Village's rounds:** a nightly run on its own with an action budget. Last night (seeded data): 3 things done alone, 1 question to a person, 1 refused ("Blocked by code: Carmen's rule, no calls after 9:30 PM").
- **The rebuild:** session evals flagged the Oct 9 call as possible fraud; after the second attempt, Village raises it with Ana: "Mom's had two of these calls. Let me answer unknown callers for her?" It shows the options it considered (a check button: relies on her remembering under pressure; a daily check-in call: doesn't stop the call; answering unknown callers first: chosen). Ana says yes. Daytona builds and tests, Anchor taps it, Arize scores it, every phone changes.
- **Receptionist mode:** unknown callers reach Village first; family passes through; anyone claiming to be family or asking for money is held while Village checks with the real person on their own device, never by calling back the incoming number.
- **Every incident becomes a test:** last night's call joins the eval set the next change must pass (rules only: 29/31 caught, 0/20 false alarms with the Reyes incident added).
- **Carer load:** "Ana has taken 9 of the last 12 nights. Ask Lucía to take the Sunday call?" Asked, never done on its own.

**Numbers:** live on the demo Core at 13:00, Ana's yes → every phone patched in 12 s; receipt "Scored on 51 calls (last night's included)." Evolve lane runs: 7705 ms (first 13381 ms).

---

## Numbers table
| What | Value | Source |
|---|---|---|
| Scam eval set, model on (Bedrock Haiku 4.5 + pure gate), 50 cases | 30/30 caught, 0/20 false alarms, 49/50 exact | RESULTS.md, Arize experiment `scam-model-20261016T153959Z` |
| Scam eval set, model off (rules only) | 28/30 caught, 0/20 false alarms | RESULTS.md |
| Release, Reyes warm / warm with caught failure / cold with caught failure | 14957 / 19908 / 29731 ms | RESULTS.md |
| Release, West 147th block warm | 13409 ms, 33 floor tests | RESULTS.md |
| Anchor phone-size run (warm) | 5211–5398 ms | RESULTS.md / LANE-REPORT release |
| Nightly round (seeded, budget 3) | 3 alone · 1 asked · 1 refused | RESULTS.md |
| Check-in to last of 3 phones | about 130 ms | RESULTS.md, spine |
| SurrealDB Cloud LIVE insert to notification | p50 22 ms, p95 77 ms, max 103 ms (10/10) | RESULTS.md 06b |
| Agent Memory write / history / recall | p50 630 ms / p50 248 ms / 3.7 s | RESULTS.md |
| Claude Haiku 4.5 on Bedrock, time to first token | about 520–600 ms | RESULTS.md 01 |
| ElevenLabs text to speech, 50 KB mp3 | 656 ms | RESULTS.md 09 |
| Tests offline, model off | 379 Python (114 gate), 114 kit | RESULTS.md platform; gate + kit lane reports |
| Founding intake, 11 questions → spec + three apps (Sonnet 5.5) | 65.8 s (draft 11.5 s, render 16.9 s); resume path starts at 8 of 10 → "Draft ready · rev 5" | RESULTS.md founding |
| **Live rebuild on the demo Core (13:00): Ana's yes → every phone patched** | **12 s** (six stages passed) | RESULTS.md live rebuild |
| Rebuild, evolve lane: scam check resolved → proposal / yes → every phone | 2166 ms / 7705 ms (first run 13381 ms) | RESULTS.md evolve |
| First live call: report → hold line / Marco's tap → refusal spoken | 18 s / 31 s into the call | RESULTS.md first live call |
| Reyes floor test count | [MEASURE] | V3 receipt |
| Rebuild timed live on stage at the pitch | [MEASURE: seconds, at the pitch] | V4 |
| Cost per village per month | [MEASURE: dollars, from real usage] | not measured |

---

## Video (≤ 2:00) shot list
Climax: the receptionist refusing the scammer live (D19). Founding is the full intake replay (D29 `--replay`); the Control Room shows the platform face (D30: "Village" header, switcher, "New village"). Cut any shot whose version isn't confirmed; at V1 the video is the 30 s clip only.

| t | Shot | Version |
|---|---|---|
| 0:00–0:08 | Cold open: Village answers Carmen's line, the caller is refused. Caption: "The scammer never reached her." | V4 |
| 0:08–0:16 | "Apps are built for millions. Village builds one for your people." Carmen, 78, alone at home; $7.75B lost to scams in 2025. | any |
| 0:16–0:22 | Platform face: the "Village" header, the switcher showing Reyes and West 147th, the cursor on "New village". | V2 |
| 0:22–0:44 | Intake (replay, sped up): Village asks one question at a time, reflects back, people and needs appear on the Control Room; three different apps under one address. A judge scans to join. | V2 |
| 0:44–1:02 | Run: the first call reaches Carmen. "Voy a confirmar con Marco." Marco's phone; "That wasn't me." "Ese no era Marco. No mande dinero." | V1 |
| 1:02–1:10 | Rounds card: "Last night Village did 3 things on its own, asked you about 1, and stopped itself once: Carmen's rule, no calls after 9:30 PM." | V4 |
| 1:10–1:34 | Rebuild: "Mom's had two of these calls. Let me answer unknown callers for her?" Options considered; "Sí, hazlo"; Daytona tests, Anchor taps, Arize scores; every phone changes. Inset: the caught build, contrast 4.1:1 → fixed. | V3/V4 |
| 1:34–1:48 | Live: the presenter calls Carmen's line as "Marco". Village answers first, checks with the real Marco, refuses the caller. English captions. | V4 |
| 1:48–1:56 | Anyone: switch to West 147th St. "Same code, no Reyes anywhere in it. Describe your group and it builds yours." (13.4 s release, 33 floor tests on screen.) | V3 |
| 1:56–2:00 | "30 of 30 scam calls caught on our eval set. It takes a village. Now every group can have one." | V4 |

---

## Questions judges will ask
1. **What stops the AI from being talked into sending money?** The model doesn't decide. Every action goes through a gate in plain Python that reads the family's state and returns the decision and the sentence to speak. Village has no tool that moves money, and the gate denies any request that it do so, whoever asks. 114 gate tests run with the model switched off. If Marco doesn't answer, the answer is "don't send," and Ana is told.
2. **What if the scammer spoofs Marco's number or clones his voice?** Village never trusts the incoming call. It checks with Marco on his own device: the app on his phone and the number on file. It never calls back the number that called.
3. **What data do you keep, and who sees it?** Members, consent, events and decisions, each with its source (which call, which second, which tap). Health details go only to the members Carmen shares them with; Carmen's own screen doesn't even show medicine names. Account and card numbers are redacted before storage and never repeated.
4. **Is this HIPAA compliant?** No, and that's out of scope today. Village is a family's own tool, not a clinic or insurer, and it never gives medical advice: it reports what was recorded and tells the person on duty. A version sold to care providers would need a full HIPAA program.
5. **How does it scale past one family?** Everything is keyed by village id, and the rules are parameters of each village's spec, so a new group is new data, not new code. We built a second village, a city block in a blackout, through the same pipeline: released in 13.4 s with 33 floor tests. Core holds no state of its own, so it can run as many copies as needed in front of one database; nightly rounds run per village on a schedule. Today it's one Mac and one database.
6. **What does a village cost to run?** [MEASURE: cost per village per month from today's usage]. Until measured, say: "We haven't measured it yet; voice minutes are the biggest part."
7. **Why Daytona?** Village runs code an AI wrote for a specific family. Every version is built and tested in a sandbox that can't reach the internet, and only a passing build gets out. Today a build failed the contrast test, the agent fixed it, and the fixed build shipped: Daytona's generate, test, fix pattern with real stakes.
8. **Why Anchor?** Tests that read code don't see what Carmen sees. An Anchor browser opens each version at phone size (390×844) and checks it the way she'd see it, and we keep the recording as evidence.
9. **Why Arize?** The agent reads its own traces and evals. A session eval flagged the Oct 9 call as possible fraud, which is what starts the rebuild; release evals decide whether a version ships; the scam eval set runs as an Arize experiment (30/30, 0/20). Observability the agent uses, not only a dashboard for us.
10. **Why SurrealDB and ElevenLabs?** SurrealDB gives us records, LIVE queries to every phone (p50 22 ms) and Agent Memory where a new fact replaces an old one without erasing it: the 5 mg to 10 mg change stays visible with its source, and as-of queries return what was true then. ElevenLabs is the whole product for Carmen: a Spanish phone line where the safety sentences are spoken word for word, and the call that checks with Marco.
