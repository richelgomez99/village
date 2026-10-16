# Devpost draft (rebuilt around autonomy, D23). Fill every `[MEASURE]` with a real number before posting. Update at each version tag.

## Name
Village

## Tagline (one line)
Software that builds itself around your people, runs it, and rebuilds itself as life changes, without ever acting alone.

## Hero (first thing on the page)
GIF, 8 s: a second phone calls Carmen's line. Village answers first, checks with the real Marco (his phone rings, he taps "That wasn't me"), and refuses the caller. English captions. Caption under the GIF: *"The scammer never reached her."*

## Summary (2–3 sentences)
Village is an agent that turns a conversation about your people into working software for each of them, then keeps watch. Describe your family once; it builds a different app per person, a Spanish phone line for the one who won't use apps, the family's rules, and a shared memory where every fact keeps its source. When life changes (a second scam call pretending to be her son), Village proposes a change to its own software, builds and tests it in a sandbox, tries it in a real browser, scores it, and ships it once a family member approves.

## The problem and its impact
75% of adults over 50 want to stay in their own home. What ends that is rarely one big event: it's a wrong refill, a call from "your son" asking for $2,000, nobody knowing whose turn it is. Elder fraud cost $7.75B in 2025 (+59%). 63M Americans are family caregivers, most of them also working, coordinating all of this in a group chat. Apps are built for millions; families aren't millions. Village builds one for your people.

## What the agent does on its own (measured)
- Tonight's rounds for the Reyes family: `[MEASURE N]` actions taken alone, `[MEASURE M]` asked a human, `[MEASURE K]` refused.
- Scam eval set: `[MEASURE]`/30 scam scripts caught, `[MEASURE]`/20 benign family calls left alone.
- Rebuild: proposal → sandbox build + tests → browser run → evals → live on every phone in `[MEASURE]` s.
- A build that failed the accessibility floor (contrast 4.1:1) was **fixed by the agent itself** and re-released (trace below).

## How it works (architecture)
One agent runtime, five roles, one gate:
- **Founder** turns a conversation into a village: people, what each can and can't do (language, memory, tech comfort), what could go wrong, which capability fits each person (phone line vs app, refill checklist, receptionist), the rules. It checks medications on DailyMed and calls caregivers to confirm availability and consent before showing the draft.
- **Watcher** runs rounds on a schedule: reminders, check-ins, pattern detection from its own evals, proposals.
- **Verifier** holds any money request in a family member's name and checks with that person on *their own* device.
- **Builder** writes the change (spec patch, or a new component under the component contract) and runs the release gate: **Daytona** sandbox build + generated tests → **Anchor** real browser at phone size → **Arize** evals → blue/green release. If a stage fails, the Builder reads the failure and fixes it.
- **Explainer** answers "why did you…?" from the decisions log with sources.
Every tool call that changes the world is a *proposal*; a **deterministic gate** (pure code, 51 tests run with the AI switched off) decides allow / deny / ask a human. Village never moves money, never says how many pills to take, only calls people who agreed, and treats silence as "don't send."
Memory in three layers: the operational ledger (**SurrealDB** Cloud, live queries pushed to every phone), experiential facts with provenance and history (**SurrealDB Agent Memory**: 5 mg → 10 mg supersedes, never overwrites; conflicting sources become an uncertainty for a human), and a per-run working context. Every run is one **Arize** trace; evals are both sensors (what triggers a proposal) and the release gate. **ElevenLabs** is the voice for the person who won't use apps and the way Village reaches real people. Claude on **AWS Bedrock** does the reasoning.
`[architecture diagram image: roles → loop → gate → release gate → memory layers, sponsor logos in place]`

## Scaling
One stateless Core behind SurrealDB; per-village memory scopes, sandboxes and voice lines (numbers shared by caller-id routing); rounds scheduled per village (EventBridge in production); published apps on S3 + CloudFront; about $18–47 per family per month at today's prices, voice being 70% of it. Any group, not only families: the same conversation builds a block-coordination village for a blackout (second village in the video).

## Sponsor tools (what each does here, with code paths)
- **Daytona**: every version of a family's software is built and tested in its own sandbox (`core/release/daytona_svc.py`, `sandbox/`); the agent fixes failing builds in the same loop.
- **Arize**: traces of every role run; GUARDRAIL spans for the gate; online evals on calls (the `possible_fraud` session eval triggers the rebuild); release evals; the scam experiment (`core/obs/`, `evals/`).
- **SurrealDB**: Cloud live queries → every phone; Agent Memory for facts with provenance, supersession, uncertainty, scopes per village and role (`core/live.py`, `core/memory/`).
- **ElevenLabs**: Carmen's Spanish line with verbatim safety sentences (structured procedures), the outbound verification call, the receptionist mode (`agents/`, `core/voice/`).
- **Anchor Browser**: a real phone-sized browser uses every generated version before release; live view on the projector (`core/release/anchor_svc.py`).
- **AWS Bedrock**: Claude Sonnet/Haiku 5.5 for all reasoning (`core/llm.py`).

## Safeguards
Deterministic gate with model-off tests · verification through a second channel the caller doesn't control · consent registry + AI disclosure on every call · no money movement, no dosing advice · every fact keeps its source · nothing reaches a person untested · a human approves every change to the software.

## Video (≤2:00) shot list
0:00 the receptionist refuses the scammer (8 s) · 0:08 "Apps are built for millions…" · 0:15 founding conversation → village assembling → three different apps · 0:40 the first scam call: hold, Marco's phone rings, "that wasn't me" · 1:05 rounds card: "did 6 things alone, asked 1" · 1:15 the rebuild: options considered → sandbox → browser → evals → every phone changes · 1:40 the agent fixes its own failing build (trace) · 1:48 second village (blackout) · 1:55 numbers + close.

## What's next (designed, not built today)
The demo protects the center of the village. The rest of a village is the people around her carrying weight together, and the same agent does that work: it notices when one sibling has taken 9 of 12 nights and asks the others; it writes the handoff note at every turn change from the day's events; it keeps the village's charter in plain words, including the rules Carmen set herself ("after 9:30, no calls"); it runs *modes* (hospital stay, a parent away, a blackout) as planned rebuilds with an exit condition; it matches needs to the people who can meet them; it makes the boring calls (pharmacy, clinic, the fraud line); it takes a note from the visiting nurse off the fridge QR without an account; and it turns every bad night into a test the next change has to pass. Screens for each are on the design canvas; the plan with cut lines is `docs/VILLAGE-FEATURES.md`.

## Built with
daytona · arize · surrealdb · elevenlabs · anchor-browser · aws-bedrock · twilio · python · fastapi · react · typescript
