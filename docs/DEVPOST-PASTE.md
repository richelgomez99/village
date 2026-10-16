# Devpost paste sheet (form order). Every block is final text: copy what's inside each block as is.

Sources: RESULTS.md and LANE-REPORT.md at the 13:50 merge. No placeholders. What was dropped is listed at the end.

---

## 1. Project name

```
Village
```

## 2. Tagline (≤ 60 characters)

```
Software that builds itself around your people.
```

## 3. Elevator pitch (≤ 200 characters)

```
Describe your people once. Village builds each person their own app, runs their week, and rebuilds itself when life changes, checking with a human before anything that matters.
```

## 4. About the project (Devpost Markdown)

```markdown
## Inspiration
Older people want to stay in their own homes. What ends that is rarely one big event: a refill where the dose changed and nobody noticed, a call from "your son" asking for $2,000, two siblings each thinking the other was visiting. Scammers took $7.75B from older Americans in 2025. The families doing this work coordinate it in a group chat. Apps are built for millions of people; a family is five. We wanted software made for one group, that changes when their life changes, and that can't be talked into doing the wrong thing.

## What it does
Village is a platform: you describe your people, and it builds and runs software for each of them. Today it runs two villages it built: the Reyes family and a city block on West 147th Street during a blackout.

- **Build.** Ana talks to Village about her family. It asks one question at a time until it knows every person, how to reach them, what could go wrong, and her mother's own rules. Then it builds a different app for each person from one component catalog: three big Spanish buttons, read aloud, for Carmen (78, won't learn an app); a brief for Ana; one question for Marco: "Is it my turn?" Same address, different software, because it's a different person.
- **Run.** When a caller claiming to be Marco asks Carmen for money, Village tells her, word for word, "Voy a confirmar con Marco ahora mismo. No mande dinero todavía," and checks with the real Marco on his own phone. He taps "That wasn't me"; she hears "Ese no era Marco. No mande dinero. Ana ya lo sabe." No answer means don't send.
- **Rebuild.** After the second call in 30 days claiming to be Marco, Village weighs three fixes and proposes one: answer unknown callers on Carmen's line first. Ana approves; the change is built and tested in a Daytona sandbox, clicked through at phone size by an Anchor browser, scored by Arize, and every phone updates.
- **Runs the week.** Nightly rounds: "Tonight Village did 3 things on its own, asked a person 1, refused itself 1: Blocked by code: Carmen's rule, no calls after 9:30 PM."
- **Anyone.** Switch to the West 147th block: same code, no Reyes anywhere in it.

## How we built it
**The agent** is a hand-written tool-use loop over Claude with five roles: Founder (the intake), Watcher (rounds, patterns), Verifier (money checks), Builder (changes and releases), Explainer ("Ask Village why"). Every action that changes something is a proposal, and a **pure Python gate** decides allow, deny or ask a human. The gate reads its values from each village's spec (quiet hours, who may verify, escalation order), so the same code serves every village. 114 gate tests run with the AI switched off.

**The pipeline, the same for any group:** intake conversation → village spec → one renderer draws each person's app (tabs come from the parts of the group's life their job touches) → pure gate → release pipeline (Daytona build + generated floor tests → Anchor phone-size run → Arize evals → blue/green) → live patch on every phone over a WebSocket.

**Core:** Python 3.13 + FastAPI. **Apps and Control Room:** React + TypeScript + Vite. Contracts (JSON Schema + OpenAPI) were written first so parallel lanes could build against the same shapes.

### Daytona: build and test every version before anyone sees it
Every version of a village's app is a real `vite build` inside a Daytona sandbox, with floor tests generated for that village. A build that fails never reaches a phone.
- **For what → feature → number.** Build each release in isolation → sandbox from snapshot `village-kit` (node 22), one warm sandbox reused by label → cold sandbox 1.0 s, warm reuse 149 ms, Reyes release 15.0 s warm.
- Test what the family needs, not a generic suite → floor tests generated per village (elder text ≥ 28 px, contrast ≥ 7:1, buttons ≥ 88 px, a 911 contact) → 62 tests for Reyes, 33 for the West 147th block.
- Catch the Builder's mistake once, and keep the proof → the only failed build today, rev 3, stopped at "contrast 4.1:1 on elder Text (needs 7:1)"; the model changed #4C80B4 to #2D5A8C and rebuilt in the same sandbox → rev 4 went live; the receipt keeps both attempts.
- Keep AI-written code off the internet → sandbox egress blocked, Core pulls `dist` out → blocked to every host we tested (Anchor, SurrealDB, Bedrock, DailyMed, example.com).

**Code:** `core/release/pipeline.py`, `core/release/floor_tests.py`, `core/release/daytona_svc.py`

### SurrealDB: shared, time-aware memory, pushed live to every phone
One database for what the village knows, with history that nobody overwrites.
- Push every change to every phone → SurrealDB Cloud LIVE SELECT fanned out over Core's WebSocket → check-in to three family phones in about 130 ms.
- Remember the dose as of a date → Agent Memory facts that supersede instead of overwrite → lisinopril 10 mg since Oct 3 (from a call, 88 s in); "as of Oct 2" still answers 5 mg.
- Let every agent share one memory → the voice line, the ledger and the Watcher write and read the same facts, scoped per village and per member, each with its source → writes p50 630 ms; the Control Room shows who wrote each fact and the quote behind it.

**Code:** `core/db.py`, `core/live.py`, `core/memory/`

### Arize: the agent's senses, and what decides a release ships
Village reads its own traces to decide what to change, and no release ships without passing evals.
- See every agent step → spans with `session.id=village-<id>`, GUARDRAIL spans for gate decisions, EVALUATOR spans for release evals → one trace per founding, per call, per release.
- Prove the receptionist is safe before shipping it → experiment on dataset `village-scam-eval` → 30/30 scam calls caught, 0/20 false alarms.
- Turn an eval into a proposal → the Watcher reads a session eval that flagged the Oct 9 call as possible fraud (0.95) → that score is the evidence on the receptionist proposal Ana approved.
- Version the Builder's prompt where the team can see it → Prompt Hub prompt `village-builder`, v2 labelled `production`, fetched at runtime with a local fallback → all three founding render spans carry the Hub version id; elder, coordinator and helper apps validated first try.

**Code:** `core/obs/tracing.py`, `evals/`, `core/release/evals.py`, `core/builder/prompts.py`

### Anchor Browser: a real phone-sized browser checks every build
A human never sees a version that an Anchor browser hasn't clicked through first.
- Check the build the way Carmen will see it → Anchor session at 390×844, click-through of the home tab, screenshot and recording → 4.1 s warm in the smoke run, 9 s on the 14:22 release through the tunnel.
- Put the evidence on the receipt → the screenshot, the MP4 and the live-view link attached to each release → the Control Room's PHONE tile links straight to it.
- Refuse what wasn't checked → the release gate requires the Anchor pass before the blue/green switch → the blocked rev 3 never reached a phone.

**Code:** `core/release/anchor_qa.py`

### ElevenLabs: the whole product, for the person who won't use apps
Carmen's whole Village is a phone number that speaks formal Spanish.
- Give the elder a line, not an app → a Conversational AI agent on a real number, formal usted, English for English callers → first real call at 12:23.
- Let the voice act inside the rules → mid-call tools `report_money_request`, `await_verification`, `screen_caller` call Core; the gate's sentences are spoken word for word → hold line 18 s into the call, refusal 31 s after Marco's tap on his phone.
- Screen the unknown caller → the receptionist (built by a live rebuild at 13:00) asked who was calling and why, offered to take a message, did not put the call through → verified live at 13:28; refused a live money ask at 14:00.

**Code:** `agents/`, `core/voice/`

### AWS: the reasoning that kept the day running
- Keep the product up when a key fails → Claude Haiku 4.5 on Bedrock (Mantle) behind one `llm()` factory, with Claude Sonnet 5.5 / Haiku 5.5 through the Anthropic API as the primary path → it ran every role for the first hours, before our Anthropic key worked.
- Run the cheap, frequent reasoning → scam extraction, release evals, the Builder's repair → the scam set's model-on run (30/30, 0/20) used Bedrock Haiku 4.5; time to first token 520–600 ms.

**Code:** `core/llm.py`

### How the day was run
One builder, Richel Gomez. A Claude session orchestrated: specs, briefs, merges, tests, tags. Codex sessions implemented the early core, gate, voice and contracts; after a shared rate limit, Claude sessions implemented the rest (builder, apps and Control Room, release pipeline, evals, memory, pitch), each in its own git worktree.

## Challenges we ran into
- **Rate limits.** Five Codex sessions shared one OpenAI limit of 1M tokens per minute and kept dropping turns; one lane had zero commits after 20 minutes. We moved lanes to Claude in two steps.
- **Model access.** On the Bedrock lab account only Claude Haiku 4.5 answered; every Sonnet and Opus id returned 404.
- **An API key scoped to a workspace.** Our Anthropic key returned 400 until requests carried the workspace id.
- **Daytona snapshots came back "Access denied"** until 14:20: the API key lacked snapshot scope, not the plan. A new key fixed it (snapshot `village-kit` created in 4.2 s). Until then one warm sandbox from an image carried every release (cold 29.7 s, warm 15.0 s).
- **Sandbox egress blocked**, by design; sandboxes only build and test.
- **Twilio geographic permissions** blocked live outbound calls, so the check reaches Marco through his app.
- **The first live call taught us four rules**: formal usted throughout, the AI says it's a program first, the voice platform's guardrail must never block Village's own "No mande dinero", and every tool the agent can call must have a handler (one returned 404 mid-call; fixed).

## Accomplishments that we're proud of
- **30/30 scam calls caught, 0/20 false alarms on our 50-case eval set**; with the AI off, the rules alone catch 28/30.
- **A live rebuild in 12 seconds**: at 13:00, Ana tapped Approve and every phone was patched through six stages (spec, Daytona build, floor tests, Anchor phone-size run, Arize evals, live).
- **The agent fixed its own failing build** (contrast 4.1:1 → fixed → released).
- **Two villages, one pipeline**: Reyes 14957 ms warm, West 147th 13409 ms with 33 floor tests; no Reyes-specific code in Core (a search for the family's names returns nothing outside test fixtures).
- **379 Python tests and 114 app tests**, all passing offline with the AI off.

## What we learned
- Putting the rules in code made the AI parts easier to build: every lane could test against the gate without a model.
- Rules as spec parameters are what make it a platform.
- With her consent, a screen on her line is a receptionist; without it, it would be surveillance. So the rule is Carmen's, not Ana's: known numbers ring through, a stranger is asked who they are, and only money or family-claim calls are held and checked.
- In the family chat, Village should act like a participant: it asks the people concerned by name and arranges it when they agree; the leader approves only changes to the software.
- A blocked sandbox is a feature when the code inside was written by an AI for someone's mother.

## What's next
The demo protects the center of the village; the rest is the people around her carrying weight together. Designed, not built: handoff notes at every turn change; a weekly page per member; consent from each person a change affects; a plain-language charter; modes (hospital stay, a parent away, a blackout); needs and offers; Village making the boring calls (pharmacy, clinic, the fraud line); guest notes from the fridge QR code; "What does Village know about me?"; starting points for other groups; and governance when the leader can't be reached.

## What ran live today, what was recorded, what is designed only
**Live, on the demo system:** the first real call to Carmen's line (12:23: money report, Marco's tap, refusal spoken); the live rebuild (13:00: Ana's yes to every phone in 12 s); the receptionist answering a real unknown caller (13:28: Village asked who was calling and why, offered to take a message, and did not put the call through). **Recorded:** the founding conversation, this morning's real run, replayed at its own pace on stage with the last answer typed live. **Designed only:** everything under "What's next".
```

## 5. Built with

```
daytona, arize, surrealdb, elevenlabs, anchor-browser, aws-bedrock, anthropic, claude, twilio, tailscale, python, fastapi, uv, pytest, react, typescript, vite, vitest, playwright, websockets, opentelemetry
```

## 6. Try it out

```
https://richel-macbook.tail8feae0.ts.net/control.html
https://richel-macbook.tail8feae0.ts.net/?m=mt_marco_7cd576dab01e77f3&village=v_reyes
```
Label for the second link: "Be Marco (the son): open on your phone".

## 7. Prize categories to tick
- Overall (1st / 2nd / 3rd)
- Best Use of Daytona
- Best Use of Arize
- Best Use of Anchor Browser
- Best Use of SurrealDB
- ElevenLabs
- AWS

## 8. Gallery (upload in this order; one caption each)
1. `docs/hero/room-rebuild.png`: The Control Room during the rebuild: what Village heard, the pattern it found, what it proposed, and its night's rounds.
2. `docs/hero/phone-ana-fact.png`: What Village knows, and how: lisinopril 10 mg since Oct 3 from a call, the old 5 mg kept as history (SurrealDB Agent Memory).
3. `docs/hero/phone-ana.png`: Ana's app is a brief: right now, what needs her yes, what Village did.
4. `docs/hero/phone-marco.png`: Marco's app answers one question: is it my turn?
5. `docs/hero/phone-carmen.png`: Carmen's app: Spanish, big buttons, read aloud, nothing to learn.

---

## Q&A lines for the judges' table (not a Devpost field)
- **Isn't screening her calls control?** With her consent it is a receptionist; without it, it would be surveillance, which is why Village asks her first. The rule is hers: known numbers ring straight through, strangers are asked who they are, only money or family-claim calls are held, and she can turn it off by saying so.
- **Who approves things in the family chat?** In the chat, Village asks the people concerned and arranges it when they agree; the leader approves only software changes.

## Dropped (needed a value we don't have)
- Cost per village per month (not measured).
- Reyes floor test count (only the block's 33 is measured).
- Phones joined during the demo; the rebuild timed at the pitch.
- Sponsor items not confirmed yet: Bedrock model chip, ElevenLabs success-evaluation criteria pushed to the live agent.
- Receptionist GIF and the money-claim refusal on a live call (the 13:28 call was a non-money caller); the V1 clip URL; the caught-build receipt screenshot.
- The Thanksgiving chat demo (ran only on a test Core).
- The sponsor section is headings + bullets rather than a Markdown table, because Devpost's editor doesn't reliably render bullets inside table cells.


**GitHub:** https://github.com/richelgomez99/village
