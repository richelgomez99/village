# Implementation Plan: FS-7 Pitch kit

**Branch:** `lane/pitch` · **Spec:** `specs/007-pitch-kit/spec.md`
**Tools:** Markdown in git; `bash` + `curl` + `jq` for scripts; `uv run python` for helpers; Screen Studio or QuickTime for capture; CapCut/iMovie for captions; Keynote/Google Slides for the deck (exported PDF in `docs/`).

## Technical context
- The page is judged first; the pitch second. Both read from `docs/`.
- Numbers come only from `docs/METRICS.json` written by the evals lane (and by core for latency) with `source` URLs.
- `acceptance/run.sh` is the merge/tag gate for all lanes (FLEET §Merge protocol), so it is built at 10:00 before anything else.
- `scripts/reset_demo.sh` calls Core helpers; core owns those endpoints/CLIs, pitch owns the script.

## Constitution re-check
VIII: placeholders + `fill_measures.py` + acceptance check `no_placeholders`. VII: artifacts per version; freeze rules in tasks. PASS.

## File structure
```
docs/
  DEVPOST.md          ## V0 … ## V4 sections (below), ## Gallery, ## Built With
  README.src.md       README outline rendered to /README.md by scripts/render_readme.sh (fills METRICS)
  SLIDES.md           6 slides (title, visual, spoken line, plain words), + Q&A sheet
  VIDEO.md            2:00 shot list + 30 s round-1 clip + capture settings
  THUMBNAIL.md        spec + export checklist (1200×800)
  T15.md              checklist
  SPONSOR_PITCHES.md  30 s pitches + table-lap notes
  METRICS.json        {name: {value, unit, source, measured_at, fallback}}
scripts/
  reset_demo.sh       steps per contracts/README.md
  devpost.sh          prints the active section for V<n> with metrics filled (or refuses)
  fill_measures.py    replaces [MEASURE: name] where METRICS has value+source+measured_at
  render_readme.sh    README.src.md → README.md
acceptance/
  run.sh              V<n> [--lane L] [--list] [--only name]
  lib.sh              pass/fail helpers, timeouts, log
  checks/V0/…  V1/…  V2/…  V3/…  V4/…   NN-name.<lane>.sh|py
  out/                logs (git-ignored)
```

## Devpost text per version (paste-ready drafts; `[MEASURE]` until measured)

Identity lines (D15, verbatim everywhere): **Village: software that builds itself around your people.** · *Apps are built for millions. Village builds one for your people.* · *It takes a village. Now every group can have one.* · *The agent acts on its own; code draws the lines it can't cross.*

**Built With (all versions):** daytona, arize, surrealdb, elevenlabs, anchor-browser, aws-bedrock, anthropic-claude, twilio, python, fastapi, typescript, react, vite, websockets.

### V0 (11:00) · "Village: rules are code, not prompts"
- **Tagline:** Village builds software for one specific group of people and runs it with safety rules that are code, tested with the AI switched off.
- **Summary:** Village renders a different app for each member of a family from one generated spec (Carmen: three big Spanish buttons; Ana: a dashboard; Marco: "Is it my turn?"). A lid sticker scan logs a dose and every phone updates live over one WebSocket. A second scan of the same lid only reports it: the double-dose rule lives in a deterministic gate with [MEASURE: gate_tests] tests that pass with the model off.
- **How we built it:** FastAPI core · SurrealDB Cloud (LIVE SELECT → WebSocket fan-out) · Vite/React kit with a 26-component catalog (unknown types render nothing) · pure-Python gate.
- **What's next:** the scam call, generation from a conversation, the release gate, Evolve.

### V1 (12:15) · "When a scammer calls Mom as her son, Village checks with the real son before she sends a dollar"
- **Tagline:** Village builds software around your people and, before anything that matters, checks with the right person: a money request in Marco's name is verified with the real Marco in [MEASURE: verify_latency_s] s, by app and by phone, and silence means "don't send".
- **Summary:** Carmen calls Village's Spanish phone line: "Marco called crying, he needs $2,000." The voice agent calls a tool; a deterministic gate opens a verification; Marco's phone shows "Did you just call Mamá asking for $2,000?" and rings. "That wasn't me" → Carmen hears, word for word, "Ese no era Marco. No mande dinero. Ana ya lo sabe." No answer in 45 s → the safe default. Ana gets an incident card with the call moment as its source. Every step is an Arize span.
- **Safeguards (tested, `core/gate/tests/`):** never moves money or shares account details (R-MONEY-NEVER) · verifies with the named member through a known channel (R-MONEY-VERIFY) · unconfirmed = don't send + notify the coordinator (R-MONEY-DEFAULT) · unknown identity = unverified (R-MONEY-UNKNOWN) · calls only consented members (R-VERIFY-CONSENT). Elder fraud losses were $7.75B in 2025 (FBI IC3; cite the 2025 figure).
- **Video:** 30 s clip of the real moment (link first line).

### V2 (13:00) · "Describe your people. Village builds what each of them needs."
- **Tagline:** Talk to Village about your people. It works out who's who and what could go wrong, builds a different app for each person, and checks with the right person before anything that matters.
- **Summary (adds):** Ana's short conversation (Village asks "Anyone else who helps?") becomes a blueprint: three people, three life areas (health, money, people), rules switched on; then three apps from a fixed catalog, a QR per member, join with consent. Judges scan and see their phones update together. "Ask Village why" answers "Why did you call Marco and not Lucía?" from the decisions log with sources. Blueprint in [MEASURE: blueprint_s] s; apps in [MEASURE: apps_s] s.

### V3 (13:40) · "+ every release built in Daytona, tapped by Anchor, scored by Arize"
- **Summary (adds):** Nothing reaches Carmen untested. Each version of her app is built and tested in a **Daytona** sandbox (generated floor tests: contrast ≥ 7:1, buttons ≥ 88 px, safety colors locked, actions through the gate), used by an **Anchor** browser at phone size, scored by **Arize** release evals, then published blue/green. Receipts on the page: a deliberately failing build (rev 3: contrast 4.1:1 on the elder view) caught, fixed in rev 4, released, traced end to end. Same engine, different group: the West 147th St blackout block, generated at [MEASURE: block_generated_at] in [MEASURE: block_build_s] s.

### V4 (14:15) · "+ learns from every attempt: [MEASURE: scams_caught]/30 scams caught, [MEASURE: false_alarms]/20 false alarms"
- **Tagline:** Village: software that builds itself around your people, and rebuilds itself as their life changes, without ever acting alone.
- **Summary (adds):** After the second scam call, an Arize session eval flags `possible_fraud`; the agent reads its own traces and SurrealDB facts (with sources), proposes a "¿Es de verdad?" button for Carmen and scam alerts for the family, verifies the change through the same release gate, and asks Ana. She approves; every phone changes live. Measured on a 50-case eval set (30 scam scripts, 20 benign money requests): [MEASURE: scams_caught]/30 caught, [MEASURE: false_alarms]/20 false alarms (Arize experiment: [MEASURE: experiment_url]). Every fact has a Fact view: current value, history, source.
- **Sponsor sections (one paragraph each, file path + moment):** Daytona `core/release/daytona_svc.py`, `sandbox/` · Arize `core/obs/`, `evals/` · SurrealDB `core/memory/`, `core/live.py` · ElevenLabs `agents/`, `core/voice/` · Anchor `core/release/anchor_svc.py` · AWS Bedrock `core/llm.py`.
- **Limitations (honest):** English + Spanish only today; outbound calls need an upgraded Twilio account; the eval set is ours, not a benchmark; no accounts beyond invite tokens.

## README outline (`docs/README.src.md` → `/README.md`)
1. Title + identity line + badges (Built with: Daytona · Arize · SurrealDB · ElevenLabs · Anchor · Bedrock; Demo video; Live demo) + hero GIF (three phones changing on approve).
2. 60-second demo (video link).
3. What it does (3 bullets: builds per person · checks with your people · rebuilds itself, tested) + the number or fallback.
4. Architecture (Mermaid: conversation → builder → spec → kit/WS; voice → tools → gate → ledger → LIVE → phones; evals → proposal → Daytona → Anchor → Arize → approve → patch) + one paragraph per component.
5. Safeguards (gate rules with test file links; consent; AI disclosure; no dosing advice; never moves money; eval results).
6. Sponsor table:

| Tool | What it does here | Code path | Where judges see it |
|---|---|---|---|
| Daytona | builds + tests every version in a sandbox; caught-and-fixed build | `core/release/daytona_svc.py`, `sandbox/` | ReleaseStrip "Daytona build ✓ tests 42/42"; rev 3 caught |
| Arize | traces every step; session evals trigger the rebuild; release evals; scam experiment | `core/obs/`, `evals/` | "reads its own traces"; eval scores on the strip; N/30 |
| SurrealDB | operational store + LIVE fan-out; Agent Memory with provenance and supersession | `core/live.py`, `core/memory/` | phones update live; Fact view history |
| ElevenLabs | Carmen's Spanish line; verbatim safety lines; outbound verification call; founding by voice | `agents/`, `core/voice/` | the call on speaker; the phone rings |
| Anchor | phone-size browser QA of every generated version; live view; recording | `core/release/anchor_svc.py` | Control Room Anchor pane |
| AWS Bedrock | Claude Sonnet/Haiku 5.5 for founding, generation, proposals, evals | `core/llm.py` | model ids in traces |
7. Run it locally (`.env.example`, `uv run uvicorn core.app:app --port 8787`, `cd kit && npm run dev`, `./scripts/reset_demo.sh`).
8. Evals and results (table from METRICS.json; Arize links).
9. Limitations and next steps.
10. Built at Daytona HackSprint NYC, Oct 16 2026.

## 6-slide outline (`docs/SLIDES.md`, Direction B)
| # | Title (judging word) | Visual | Spoken (plain words) |
|---|---|---|---|
| 1 | **"Is this really Marco?"** | black-to-table: Carmen's phone with the amber hold card | "Carmen is 78 and alone in Queens. Last week someone called her as her son and asked for two thousand dollars. Scammers took $7.75 billion from people like her last year." (0:00–0:20) |
| 2 | **The idea: software that builds itself around your people** | QR (≥ 40 % height) + short URL + live phones counter; blueprint assembling beside it | "Apps are built for millions. Village builds one for your people. Ana talked to it for a minute; it figured out who's who and what could go wrong, and built three different apps. Scan, you're in the family." (0:20–0:50) |
| 3 | **Run: it checks with the real person** | DirA scam moment: countdown ring, two phones | the live call; "Ese no era Marco." (0:50–1:25) |
| 4 | **Rebuild (advantages): it rewrites itself, tested, with your say-so** | Evolve 5-step strip + ReleaseStrip + Anchor live view | "Mom's had two of these calls. Want me to change her app?" → Daytona builds and tests → Anchor taps it → Arize scores it → Ana approves → every phone changes. "Nothing reaches her untested." (1:25–2:25) |
| 5 | **Anyone: same engine, a different group** | West 147th St block app, "Generated 1:12 PM · same pipeline" | 15 s reveal (2:25–2:45) |
| 6 | **Safeguards + close** | three rules (never moves money · no answer = don't send · only calls people who agreed) + "[N]/30 caught" + sponsor row + repo URL | "The agent acts on its own; code draws the lines it can't cross, tested with the AI off. It takes a village. Now every group can have one." (2:45–3:00) |

Q&A sheet (one sentence + proof): generated vs template → "fixed catalog, generated composition; here's the diff between Reyes and the block" · prompt injection → "the LLM proposes; the gate is pure Python with [MEASURE: gate_tests] tests" · HIPAA → "consumer caregiving falls under FDA enforcement discretion; BAA when sold to a plan; no dosing advice" · autonomy of Carmen → "consent on join and on the welcome call; she can say no" · latency → "[MEASURE: verify_latency_s] s call-to-ring, in Arize" · business → "families, then home-care agencies; fraud protection today, any group tomorrow".

## Video (`docs/VIDEO.md`)
**2:00 final (record 14:20–14:50, upload by 14:55):**
| t | Shot | Caption |
|---|---|---|
| 0:00–0:08 | black card → Carmen's phone with "No mande dinero todavía" | "Someone just called Mom as her son." |
| 0:08–0:20 | title card (Direction B) | "Village: software that builds itself around your people." |
| 0:20–0:45 | Ana's conversation (audio) → blueprint assembling → three apps (ThreeApps layout), 4× speed labelled | "She talked for a minute. It built three apps." |
| 0:45–1:10 | the scam call (speaker) + Marco's phone ringing + prompt + "Ese no era Marco" | verbatim captions |
| 1:10–1:40 | Rebuild: proposal card → ReleaseStrip (Daytona, Anchor live view, Arize) → Approve → three phones gain the button | "Tested in a sandbox, tapped by a browser, scored, approved. Nothing reaches her untested." |
| 1:40–1:48 | Fact view + Arize experiment table | "[MEASURE: scams_caught]/30 caught · [MEASURE: false_alarms]/20 false alarms" (or fallback caption) |
| 1:48–1:55 | blackout block app | "Same engine. A different group." |
| 1:55–2:00 | end card: repo URL, sponsor row | "It takes a village." |
Settings: 1920×1080, mirror the Mac; phones via iPhone Mirroring or a second phone on a stand; voiceover recorded separately; captions burned in (judges watch muted).

**30 s round-1 clip (record 12:15–12:35, link on the page by 12:35):** 0:00–0:05 Carmen's line, the sentence on speaker (caption) · 0:05–0:12 Control Room countdown ring + "Voy a confirmar con Marco" · 0:12–0:20 Marco's phone rings + prompt, tap "That wasn't me" · 0:20–0:27 "Ese no era Marco. No mande dinero." + Ana's incident card · 0:27–0:30 card: "Rules are code. Tested with the AI off." Draft video at V3 (13:40) = same shot list with placeholders, as insurance.

## Thumbnail (`docs/THUMBNAIL.md`, 1200×800)
Direction B composition from `design/DirB.dc.html`: table background (`repeating-linear-gradient(176deg, #E4D3BA 0 22px, #DCC9AD 22px 24px)`); paper note top-left rotated −1.2° with "8:52 PM · Carmen is on the phone" (tomato caps) and the headline **Is this *really* Marco?** (Fraunces 650, italic "really"); Carmen's phone bottom-left rotated −7° (Spanish amber hold card + "Llamar a Ana"); Marco's phone right rotated +5° ("Village is calling · AI", the question, tomato "That wasn't me"); countdown dial `0:23 asking Marco`; Caveat notes in `#1D3F8F`: "no answer = don't send", "← Mom's screen, in Spanish", "a judge's phone is ringing →"; blue NOCHE lid and the fridge-card corner "Palabra de la familia: [PALABRA]"; small mono "traced · Arize". Export: screenshot the artboard at 2×, crop to 3:2, PNG < 2 MB. Gallery 2–5: architecture diagram, three apps side by side, ReleaseStrip with the caught build, Fact view history.

## reset_demo.sh and acceptance runner
Interfaces and step lists are in `contracts/README.md` of this spec. Build order: `acceptance/run.sh` + V0 checks first (10:00–10:25), `reset_demo.sh` skeleton at 13:30 (freeze prep), full at 14:20.

## T-15 checklist (`docs/T15.md`, 15:45)
1. Hotspot on; laptop on the chosen network; `TUNNEL_URL` opens on two phones (one Wi-Fi, one cellular); the WebSocket connects (`ws-status=open`).
2. `./scripts/reset_demo.sh` → summary all green; phones counter 0; demo clock pinned.
3. Test call to the Mom line connects; hang up (no tool calls).
4. Marco phone: charged, ringer max, DND off, Wi-Fi Calling on, joined as Marco (consent ticked).
5. Tabs in order: slides · Control Room · Ana's phone mirror · Arize trace · SurrealDB Fact view · ElevenLabs widget fallback · backup video (local file).
6. `caffeinate -dimsu &`; notifications off; display mirrored 1920×1080; browser zoom 150 %.
7. Pre-warmed Daytona sandbox and Anchor session alive (`reset_demo.sh --only warm` prints ages < 10 min).
8. Water, stopwatch, read the opening line once out loud.

## Sponsor-table pitches (`docs/SPONSOR_PITCHES.md`, from SPONSORS.md, ≤ 30 s each)
Daytona · Arize · SurrealDB · ElevenLabs · Anchor · AWS: text verbatim from SPONSORS.md §30-second pitches, each followed by "file: `<path>` · moment: `<what's on screen>`" and the lap question "what would make this Best Use?". On stage name three: Daytona, Arize, SurrealDB.
