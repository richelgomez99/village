# Devpost page, per version

Rules for this file:
- Paste the section for the **latest green tag** (LAYERS.md version map). A version section stays `[PENDING Vn]` until the orchestrator confirms the tag.
- Every number is copied from `RESULTS.md` or `LANE-REPORT.md`, or written `[MEASURE: what]`. Nothing with a `[MEASURE]` or `[PENDING]` left in it gets pasted into Devpost: cut the sentence instead.
- Plain words (DECISIONS D18, LAYERS.md "On stage, plain words only"). No "agentic", "seamless", "intelligent", "leverage", "empower".
- Never claim a P2 or P3 feature works. They go in "What's next" only.

Devpost draft link: [PENDING: paste the draft URL once saved]

---

## Fixed fields (all versions)

**Name:** Village

**Tagline:** Software that builds itself around your people, and rebuilds itself as their life changes, without ever acting alone.

**Built with** (services actually called today, per `RESULTS.md`):
daytona · arize · surrealdb · elevenlabs · anchor-browser · aws-bedrock · twilio · tailscale · python · fastapi · uv · pytest
Add `react · typescript · vite` when the kit lane merges into `main`.

---

## V0 · READY · "Village: rules are code, not prompts"

### Headline
**Village: rules are code, not prompts.**

### Hero
Screenshot: three browser tabs (Carmen, Ana, Marco) updating from one check-in, next to the terminal showing `uv run pytest -q` green with the model switched off. Caption: *"The rules that protect Carmen don't depend on what the model says."*

### Summary
Village turns a conversation about your people into working software for each of them, then keeps watch. Our demo family: Carmen, 78, alone in Queens, Spanish-speaking, won't use apps; Ana, her daughter, who coordinates; Marco, her son, who works shifts. Today's first version is the part everything else stands on: every action the agent wants to take goes through a gate written in plain code, tested with the AI switched off, and every change reaches every family member's phone in about 130 ms.

### Inspiration
Older people want to stay in their own homes. What ends that is rarely one big event: a refill where the dose changed and nobody noticed, a call from "your son" asking for $2,000, two siblings each thinking the other was visiting. Scammers took $7.75B from older Americans in 2025. The families doing this work coordinate it in a group chat. Apps are built for millions of people; a family is five. We wanted software made for one family, that changes when their life changes, and that can't be talked into doing the wrong thing.

### What it does (V0)
- **A safety gate in code.** Every action the agent proposes (log a dose, place a call, react to a money request) is checked by a pure Python function that reads the family's state and returns allow, deny or ask a human, plus the exact sentence to say. The voice model never picks a safety sentence.
- **Money rules.** Village never moves money or handles account numbers. A money request in a family member's name is checked with that person through a channel the caller doesn't control. No answer means "don't send," and Ana is told. A caller who isn't in the family is treated as unverified. Village only calls people who agreed to be called.
- **Verification state machine.** Pending, confirmed, denied, timed out, late answers, duplicate answers, restarts: each has a test.
- **Live family state.** A check-in goes tool call → gate → SurrealDB Cloud → change feed → every connected phone over WebSocket.
- **Prescription history.** Marco's refill view shows lisinopril went from 5 mg to 10 mg on Oct 3 (Dr. Lee), with the old dose kept as history, not overwritten.

### How we built it
- **Core:** Python 3.13, FastAPI, one process. The gate (`core/gate/`) is pure Python with no model calls and no network.
- **SurrealDB Cloud** holds villages, members, events, decisions and verifications. LIVE queries feed a WebSocket hub that pushes each change to every phone.
- **Claude on AWS Bedrock** for reasoning (`core/llm.py`). The lab account only had Claude Haiku 4.5, so every role runs on it today.
- **Arize** tracing is registered: one traced Bedrock call produced chain, agent, guardrail and tool spans.
- **Contracts first:** JSON Schemas, fixtures and an OpenAPI file (`contracts/`) were written before code, so parallel lanes could build against the same shapes.
- **How the day was run:** one builder (Richel Gomez). A Claude session wrote the specs, briefed lanes, merged and tested; Codex sessions implemented core, gate and voice; Claude sessions implemented the phone app, the release pipeline and this pitch kit, each in its own git worktree (`DECISIONS.md` D25, D26).

### Challenges we ran into
- **Only one model on the lab account.** Bedrock returned 404 for every Claude Sonnet and Opus id we tried; only Claude Haiku 4.5 worked. We run every role on Haiku 4.5 and kept a fallback client for when a key with more models arrives.
- **Daytona snapshot creation was denied** on our account tier ("Access denied"), so sandboxes start from a public image and install at runtime instead of from a prepared snapshot.
- **Sandbox egress is blocked**, by design: a Daytona sandbox can't reach any outside host. That's what we want for code an AI wrote for a real family, so sandboxes only build and test, and Core pulls the results out.
- **Rate limits while running five implementation lanes at once.** Five Codex sessions shared one OpenAI rate limit and kept dropping turns; one lane had zero commits after 20 minutes. We moved two lanes to Claude and ran the paused ones one at a time (D26).
- **Twilio** needed an account upgrade and geographic permissions before Village could ring a real phone outside the verified list.

### Accomplishments we're proud of (V0)
- 49 gate tests and 16 core tests pass offline with the model off.
- A check-in reaches all three family phones in about 130 ms, through SurrealDB Cloud.
- SurrealDB Cloud LIVE notifications: p50 22 ms, p95 77 ms, 10 of 10 delivered.
- Duplicate voice webhooks for the same tool call return the same decision and create one verification, never two calls to Marco.

### What we learned
- Putting the rules in code made the AI parts easier to build, not harder: every lane could test against the gate without a model.
- A blocked sandbox is a feature when the code inside was written by an AI for someone's mother.
- Measure before you plan the demo: the model you expect may not be on the account.

### What's next
See the shared "What's next" section below.

---

## V1 · [PENDING V1] · "When a scammer calls Mom as her son, Village checks with the real son before she sends a dollar"

Paste only when the V1 tag is confirmed. Replaces the V0 Headline, Hero, What it does and Accomplishments; keeps the rest.

### Headline
**When a scammer calls Mom as her son, Village checks with the real son before she sends a dollar.**

### Hero
The 30-second clip recorded at the V1 tag: Carmen's line on speaker, "Voy a confirmar con Marco ahora mismo. No mande dinero todavía," Marco's phone shows the prompt, he taps "That wasn't me," Carmen hears "Ese no era Marco. No mande dinero. Ana ya lo sabe." English captions. [PENDING V1: clip URL]

### What it does (adds to V0)
- Carmen calls her Village number (ElevenLabs, Spanish). When she reports a money request "from Marco," the gate holds it and starts a check.
- Marco gets an in-app prompt and an outbound call: "Did you just call Mamá asking for $2,000?" Either answer counts.
- Village speaks the gate's sentence word for word. If Marco doesn't answer in time: "No pude confirmar con Marco. No mande dinero. Le aviso a Ana."
- Ana gets an incident card. Every step is an Arize trace.

### Accomplishments (V1)
- Real phone call to real phone call: [MEASURE: seconds from Carmen's report to Marco's prompt]
- [MEASURE: seconds from Marco's tap to Carmen hearing the outcome]

---

## V2 · [PENDING V2] · "Describe your people. Village builds what each of them needs."

### Headline
**Describe your people. Village builds what each of them needs.**

### What it does (adds to V1)
- Ana talks to Village about her family. It asks one or two follow-ups ("Anyone else who helps?"), figures out who's who, what each person can and can't do, and what could go wrong, then builds three different apps: three big Spanish buttons for Carmen, a dashboard and approvals for Ana, one question ("Is it my turn?") for Marco.
- Same address, different software, because it's a different person.
- Judges scan a QR code to join; their phones update live.
- "Ask Village why": type "Why did you call Marco and not Lucía?" and it answers from its decision log, citing sources.
- Carmen's own rules: "after 9:30, no calls," in her words, enforced by code.

### Accomplishments (V2)
- Conversation to three apps in [MEASURE: seconds].
- [MEASURE: phones joined during the demo]

---

## V3 · [PENDING V3] · "Every release built in Daytona, tapped by Anchor, scored by Arize"

### Headline adds
**Every version is built in Daytona, tapped by Anchor, scored by Arize. Nothing reaches Carmen untested.**

### What it does (adds to V2)
- Every version of the family's software is built and tested in a Daytona sandbox (accessibility floor, safety wording, action routing).
- An Anchor browser at phone size uses each version the way Carmen would, with a recording as evidence.
- Arize scores each release.
- One build failed the accessibility floor; [PENDING V3: confirm the agent fixed it itself, with the failing value and the trace link]. Do not claim this until the trace exists.
- A second group, a city block during a blackout, built by the same engine earlier today.

### Accomplishments (V3)
- Daytona build + tests: [MEASURE: seconds, tests passed / total]
- Anchor phone-size run: [MEASURE: seconds]
- Blackout block generated in [MEASURE: seconds]

---

## V4 · [PENDING V4] · "Learns from every attempt"

### Headline adds
**It learns from every attempt: [MEASURE: N]/30 scams caught, [MEASURE: M]/20 false alarms.**

### Hero (replaces V1 clip)
GIF, 8 s: a second phone calls Carmen's line. Village answers first ("Carmen's phone, this is Village. Who's calling?"), checks with the real Marco on his own phone, and refuses the caller. English captions. Caption: *"The scammer never reached her."*

### What it does (adds to V3)
- **Village's rounds:** a nightly run on its own with an action budget (check-in call if enabled, "you're on tomorrow" nudge, refill reminder, pattern check). "Tonight Village did [MEASURE: N] things on its own, asked you about [MEASURE: M], refused [MEASURE: K]."
- **The rebuild:** after the second scam attempt, Village raises it with Ana: "Mom's had two of these calls. Let me answer unknown callers for her?" It shows the options it considered (a check button: relies on her remembering under pressure; a daily check-in call: doesn't stop the call; answering unknown callers first: chosen). Ana says yes. Daytona builds and tests, Anchor taps it, Arize scores it, every phone changes.
- **Receptionist mode:** unknown callers reach Village first; family passes through; anyone claiming to be family or asking for money is held while Village checks with the real person on their own device, never by calling back the incoming number.
- **Every incident becomes a test:** last night's call joins the eval set the next change must pass.
- **Carer load:** "Ana has taken [MEASURE] of the last [MEASURE] nights. Ask Lucía to take Sunday?" Asked, never done on its own.

### Accomplishments (V4)
- Scam eval set: [MEASURE: N]/30 caught, [MEASURE: M]/20 false alarms, run as an Arize experiment.
- Rebuild, Ana's yes to every phone changed: [MEASURE: seconds]

---

## Shared sections (all versions)

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
Deterministic gate, tested with the model off · verification through a channel the caller doesn't control · calls only to people who agreed · no money movement, no account numbers, no dosing advice · emergency words get "call 911" first and can't be downgraded · Carmen's quiet hours · every fact keeps its source · [PENDING V3: nothing reaches a person untested] · [PENDING V4: a human approves every change to the software].

### Numbers table
| What | Value | Source |
|---|---|---|
| Check-in to last of 3 phones (gate + SurrealDB Cloud + change feed + WebSocket) | about 130 ms | RESULTS.md, spine |
| SurrealDB Cloud LIVE insert to notification | p50 22 ms, p95 77 ms, max 103 ms (10/10) | RESULTS.md 06b |
| Claude Haiku 4.5 on Bedrock, time to first token | about 520–600 ms | RESULTS.md 01 |
| ElevenLabs text to speech, 50 KB mp3 | 656 ms | RESULTS.md 09 |
| Arize span export flush | 326 ms | RESULTS.md 07 |
| Tests passing offline, model off | 16 core + 49 gate | RESULTS.md, spine |
| Carmen's report to Marco's prompt | [MEASURE: seconds] | V1 |
| Marco's tap to Carmen hearing the outcome | [MEASURE: seconds] | V1 |
| Conversation to three apps | [MEASURE: seconds] | V2 |
| Daytona build + tests | [MEASURE: seconds, tests passed / total] | V3 |
| Anchor phone-size run | [MEASURE: seconds] | V3 |
| Rebuild, approval to every phone changed | [MEASURE: seconds] | V4 |
| Scam eval set | [MEASURE: N/30 caught, M/20 false alarms] | V4 |
| Rounds: acted alone / asked / refused | [MEASURE: counts] | V4 |
| Cost per village per month | [MEASURE: dollars, from real usage] | not measured |

### Video (≤ 2:00) shot list
Climax is the receptionist refusing the scammer live (D19). Cut any shot whose version isn't tagged; at V1 the video is the 30 s clip only.

| t | Shot | Version |
|---|---|---|
| 0:00–0:08 | Cold open: Village answers Carmen's line, the caller is refused. Caption: "The scammer never reached her." | V4 |
| 0:08–0:18 | "Apps are built for millions. Village builds one for your people." Carmen, 78, alone at home; $7.75B lost to scams in 2025. | any |
| 0:18–0:40 | Build: Ana talks; Village asks one follow-up; who's who and what could go wrong appear; three different apps; a judge scans to join. | V2 |
| 0:40–1:00 | Run: the first call reaches Carmen. "Voy a confirmar con Marco." Marco's phone; "That wasn't me." "Ese no era Marco. No mande dinero." | V1 |
| 1:00–1:08 | Rounds card: "Tonight Village did [MEASURE: N] things on its own and asked you about [MEASURE: M]." | V4 |
| 1:08–1:35 | Rebuild: "Mom's had two of these calls. Let me answer unknown callers for her?" Options considered; "Sí, hazlo"; Daytona tests, Anchor taps, Arize scores; every phone changes. | V3/V4 |
| 1:35–1:50 | Live: the presenter calls Carmen's line as "Marco". Village answers first, checks with the real Marco, refuses the caller. English captions. | V4 |
| 1:50–1:56 | Anyone: the blackout block, same engine, generated earlier. | V3 |
| 1:56–2:00 | "[MEASURE: N]/30 scams caught. It takes a village. Now every group can have one." | V4 |

### Questions judges will ask
1. **What stops the AI from being talked into sending money?** The model doesn't decide. Every action goes through a gate in plain Python that reads the family's state and returns the decision and the sentence to speak. Village has no tool that moves money, and the gate denies any request that it do so, whoever asks. Those rules are tested with the model switched off. If Marco doesn't answer, the answer is "don't send," and Ana is told.
2. **What if the scammer spoofs Marco's number or clones his voice?** Village never trusts the incoming call. It checks with Marco on his own device: the app on his phone and the number on file. It never calls back the number that called.
3. **What data do you keep, and who sees it?** Family members, consent, events and decisions, each with its source (which call, which second, which tap). Health details go only to the members Carmen shares them with. Account and card numbers are redacted before storage and never repeated.
4. **Is this HIPAA compliant?** No, and that's out of scope today. Village is a family's own tool, not a clinic or insurer, and it never gives medical advice: it reports what was recorded and tells the person on duty. A version sold to care providers would need a full HIPAA program.
5. **How does it scale past one family?** Core holds no state of its own, so it can run as many copies as needed in front of one database. Each village has its own data, its own memory and its own sandboxes; the nightly rounds run per village on a schedule. Today it's one Mac and one database.
6. **What does a village cost to run?** [MEASURE: cost per village per month from today's usage]. Until measured, say: "We haven't measured it yet; voice minutes are the biggest part."
7. **Why Daytona?** Village runs code an AI wrote for a specific family. Every version is built and tested in a sandbox that can't reach the internet, and only a passing build gets out. That is Daytona's generate, test, fix pattern with real stakes.
8. **Why Anchor?** Tests that read code don't see what Carmen sees. An Anchor browser opens each version at phone size and taps through it the way she would, and we keep the recording as evidence.
9. **Why Arize?** The agent reads its own traces and evals. Evals on calls are what notice the second scam attempt, and evals on each release decide whether it ships. Observability the agent uses, not just a dashboard for us.
10. **Why SurrealDB and ElevenLabs?** SurrealDB gives us records, LIVE queries to every phone (p50 22 ms measured) and memory where a new fact replaces an old one without erasing it: the 5 mg to 10 mg change stays visible. ElevenLabs is the whole product for Carmen: a Spanish phone line where the safety sentences are spoken word for word, and the call that checks with Marco.
