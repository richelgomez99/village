## Village builds a village and runs it

A village is any group that has to keep someone safe: a family around an aging parent, a block without power in a heat wave, a classroom, a night shift. Every one of them runs on one person's phone and a group chat. Who's on tonight. Who answers "did I take my pills." Who checks the call that says "it's your son, send money." Who knows which cooling center still has power. The job has no software, because every group would need different software.

**Village is software that builds itself around your people.** Describe the group once, in a conversation. Village builds a different app for each person, and a phone line for the one who won't learn an app. Then it runs the week as a participant: it asks the right person, and it logs what it did on its own, what it asked, and what it refused. When the group's life changes, it changes itself: it notices from its own traces, proposes a change, builds and tests it in a sandbox, clicks through it at phone size, scores it, waits for a human yes, and updates every phone.

We built two villages today from the same code: the Reyes family around Carmen, 78, in Queens, and a Harlem block in a blackout.

## What it does

**Build.** The founding is an intake conversation, not a form. Village asks for what's missing, one question at a time, and shows a coverage meter as it goes. The topics come from the group: for a family, people, availability, medications, routine, money, home, emergencies, channels, consent and the person's own rules; for a block, who is on which floor, who has oxygen or insulin or an infant, who has a generator or a car, which official pages to trust. It does work while you talk: it looks up every medication on DailyMed, checks the city's cooling-center and outage pages, calls the people who said yes to confirm what they offered, and checks that every night or every shift has a name. Then it builds one app per role from a fixed component catalog, so the model composes screens but can't invent UI.

**Run.** Members join by QR on their own phones and see only their part. In the family, an elder who won't use apps gets a phone line in her language and three big buttons that read themselves aloud, the coordinator gets a dashboard, and the son on duty gets one card: "Is it my turn?" On the block, the coordinator gets the shift board and the rumor queue, a volunteer gets this shift and the next pickup, and a resident on oxygen gets one big line: "Someone is coming at 3." Village sits in each group's chat: "someone needs to take Mom to the doctor Friday" becomes a Friday plan item and a question to the people who can drive; "which cooling centers still have power" becomes calls Village places itself, logged as facts with the call as source. Every action lands on every other phone live.

**Rebuild.** A week in, the family's Village reads its own traces: two calls asking for money in the son's name. It weighs options and proposes one: answer unknown callers itself and verify any money ask with the real family member before the elder hears it. The coordinator approves. Village writes the change, builds it in a Daytona sandbox, runs the floor tests generated for that village (it caught its own failing contrast and rebuilt), clicks through it in an Anchor browser at 390×844, scores it in Arize, and patches every phone. On the block, "the library cooling center closed early, we're moving everyone to Hamilton Grange at 3" becomes a proposal that re-points the shift board and adds one line to the volunteer and resident apps. Same pipeline, different change.

**The gate.** The agent acts on its own, and code draws the lines it can't cross. The lines are the group's own: for the family, money, dosing and quiet hours; for the block, 911 first, medical-priority matching, rumors never repeated as fact, no apartment numbers shared beyond the matched volunteer. The gate is pure Python with no model and no network, tested with the model off. Every autonomous action writes a decision record with its mode: acted alone, asked a human, or refused. A person's own rules ("after nine-thirty, no") come from their own words, stored with the call and the second as the source.

## Measured today (from RESULTS.md)

| What | Number |
|---|---|
| Scam call on a real phone line: hold line → refusal | 18 s → 31 s |
| Live rebuild: coordinator's yes to every phone (13:00) | 12 s |
| Scripted arc from reset: approve → applied | 18.4 s |
| Sandbox build + floor tests + dist served | 15.0 s warm · 29.7 s cold |
| Second village (a Harlem block in a blackout), same pipeline | 13.4 s, 33 floor tests |
| Phone-size QA click-through in Anchor | 8.3 s (with recording) |
| Tool call to every connected phone (SurrealDB LIVE → WebSocket) | 100–130 ms |
| Tests, run with the model off | 399 Python (114 gate) + 126 kit |
| Scam evaluation set (50 calls) | 30 of 30 caught, 0 of 20 false alarms |

## How we built it

One FastAPI core (Python 3.13) runs the agent loop, the gate, the WebSocket hub and the release pipeline. The generative UI kit is Vite + React with a zod-validated catalog; apps are JSON specs, patched live with JSON Patch.

### Daytona: build and test every version before anyone sees it
Every version of a village's app is a real `vite build` inside a Daytona sandbox, with floor tests generated for that village. A build that fails never reaches a phone.
- **For what → feature → number.** Build each release in isolation → sandbox from snapshot `village-kit` (node 22), one warm sandbox reused by label → cold sandbox 1.0 s, warm reuse 149 ms, Reyes release 15.0 s warm.
- Test what the group needs, not a generic suite → floor tests generated per village (elder text ≥ 28 px, contrast ≥ 7:1, buttons ≥ 88 px, a 911 contact) → 58 tests for Reyes at rev 6, 33 for the West 147th block.
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

### Why Village is an agent, not a workflow
Village runs a perceive → decide → act → remember loop that nobody triggers by hand. It **perceives** events from the apps, calls on the voice line, facts in memory and its own evals in Arize. It **decides** with Claude tool calls under three explicit autonomy modes that every decision is labelled with: did it on its own, asked a person, refused itself. It **acts** through tools: posting in the group's chat, placing and screening calls, writing memory, and building, testing and releasing new versions of the software. It **remembers** every outcome as a typed fact with a source. The Watcher runs rounds on the clock (check-ins, verification timeouts, nudges); the Evolve loop reads 14 days of its own traces to propose changes; the Builder is an agent of its own with a repair loop that fixed its failing build today. Code, not prompts, draws the lines it can't cross: the gate is pure Python, tested with the model off. There is no agent framework in between: one FastAPI process, one `llm()` factory, OpenInference spans with `graph.node.id` so Arize sees the whole graph.

## Challenges

- The platform, not the family, is the project. Halfway through we found the family's names in 30 core files and swept them out; now one core serves both villages and the same gate rules run against both specs with different parameters.
- A phone line is unforgiving. Two hang-ups came from a webhook that wasn't mounted; the fix was mounting it and giving the agent defaults so a webhook failure can never drop a call again.
- **Daytona snapshots came back "Access denied"** until 14:20: the API key lacked snapshot scope, not the plan. A new key fixed it (snapshot `village-kit` created in 4.2 s). Until then one warm sandbox from an image carried every release (cold 29.7 s, warm 15.0 s).
- An intake conversation has to drive, not transcribe. The founder asks for the highest-risk missing fact first and never asks what it can look up or compute.

## What ran live, what was recorded, what is designed

Live today on real phones: founding intake, three role apps, join by QR, live updates, the scam call with verification, the rebuild pipeline, the second village, the receptionist screening an unknown caller (13:28), and Village as a participant in the chat: it asked Marco and Lucía and wrote the swap (13:46). Built, not shown: the fridge card. Also live: the receptionist refusing a live money ask (14:00: an unknown caller asked for money, Village refused under Carmen's rule and did not put the call through). Designed, not built: handoff notes between shifts, the weekly digest, consent per affected person, guest notes.

## What we learned

The hard part of "it takes a village" is not the people. It's that nobody is paid to run it, and every village needs different software. Software that builds the village and keeps it running has to act on its own, in public, with lines it cannot cross, and it has to change itself when the group does.
