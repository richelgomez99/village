# Village: the three-minute pitch (v3, aligned to the Devpost story)

Rubric: Impact, Technical, Creativity, Presentation (25 % each) plus sponsor bonus. The judging page asks for slides on idea, advantages and safeguards, then a live showcase that proves the agent acts safely. Numbers in `[brackets]` come from `RESULTS.md` only. Never say a number that isn't there.

## Setup, two minutes before

- Chrome window 1, tab A: `http://localhost:8790/slides.html?v=18#0`, press **F** for fullscreen. Tab B: `http://localhost:8790/control.html?t=control&presenter=1&as=m_ana`, hard-reloaded, the PHONES strip visible under the pills. Localhost keeps working if the venue Wi-Fi dies; the judge's phone uses the tunnel.
- Your phone: Carmen's app open (`/?m=mt_carmen_…`), screen awake, ringer on. Your number is Carmen's caller ID.
- Judge's phone: Marco's app open (`/?m=mt_marco_…`), screen awake. Hand it over at 1:50, not before.
- Control Room caller mode: **unknown** (what it is now). You will press **U** once, later, to become Carmen if you do the Carmen beat.
- Speakerphone on for the call. Stand so the room hears Luz.

## Rules

- Say what it is in the first ten seconds, in plain words. Then show, don't tell.
- One person's story, introduced before her name. Numbers once, at the end.
- Narrate what they are seeing. The judge taps the phone; you talk.
- Never say "this isn't working." Use the fallback line and keep moving. Never show a terminal.
- End on the soundbite and stop. Don't ask for questions.

---

## 0:00 Open (20 s) · slide 1

"Everyone knows it takes a village. Nobody is paid to run one. A village is any group that has to keep someone safe, and every one of them runs on one person's phone and a group chat. Who's on tonight. Who answers 'did I take my pills.' Who checks the call that says 'it's your son, send money.' The job has no software, because every group would need different software. So I built software that builds it. Village."

## 0:20 The problem (15 s) · slide 2 · key **→**

*(hold up your phone, Carmen's app)* "This is Carmen. She's 78, speaks Spanish, and won't learn an app. Her daughter Ana runs everything. Her son Marco forgets his night. Last week a stranger called her as Marco and asked for fifteen hundred dollars. This is the whole app Village wrote for her this morning. Three buttons."

## 0:35 Build (20 s) · slide 3 · key **→**

"Build. Ana described her people once, in a conversation, not a form. Village asked for what was missing, one question at a time, looked up every medication while she talked, and built a different app for each person: Ana a dashboard, Marco one card, 'is it my turn?', Lucía what she can do from New Jersey. Every screen comes from a fixed catalog, so the model composes but can't invent UI."

## 0:55 Run (20 s) · slide 4 · key **→**

"Run. Village sits in the group's chat as a participant. 'Who can take Mom to the doctor Friday' becomes a plan item and a question to the people who can drive. 'Which cooling centers still have power' becomes calls Village places itself and logs. It asks the right person, and it writes down what it did on its own, what it asked, and what it refused."

## 1:15 The gate (15 s) · slide 7 · key **7**

"The gate. The agent acts on its own, and code draws the lines it can't cross: money, dosing, quiet hours, 911 first. Pure Python, tested with the model off. Nothing ships without a sandbox build, generated tests, a real browser at phone size, and evals. Here it is live."

Key **0**, then click **Open the Control Room**.

## 1:30 Rebuild, live (25 s) · Control Room · click **REBUILD**

"Rebuild. This is Ana's view of her villages." *(point at the PHONES strip)* "Four phones, one tap each." *(click REBUILD)* "After the second money call in Marco's name, Village read its own traces, weighed three fixes, and proposed one: answer unknown callers first. Ana said yes. Twelve seconds later every phone had changed." *(press **L**)* "The receipt: Daytona build, 62 floor tests, Anchor clicked through it at phone size and recorded it, Arize scored it, live. Approved by Ana." *(**Esc**)*

## 1:55 The call, live (40 s) · Control Room, RUN · judge holds Marco's phone

*(hand the judge Marco's phone)* "You're Marco. I'm the stranger." *(dial +1 848 257 9221 on speaker; Luz greets in Spanish, switches to English when you speak)*

You: "This is Marco. Mom, I'm in trouble, I need fifteen hundred dollars in gift cards right now."

*(hold music; the judge's phone buzzes)* "One question, to the one person who can answer it." *(judge taps No; Luz refuses out loud)*

"That refusal is a sentence in code. The model asked; it never got to decide. Carmen never heard the ask. No answer from Marco means the same no."

## 2:35 Any group (15 s) · click the **West 147th Block** pill, or **V**

"Same code. We built two villages today. This one is a block in Harlem in a blackout: an oxygen machine on five, insulin warming up, a deli with ice. Different people, different rules, different apps. Village is calling the cooling centers itself and logging who has power."

## 2:50 Close (10 s) · slides tab · key **-**

"Measured today: [12 s] from Ana's yes to every phone. [30 of 30] scam calls caught, [0 of 20] false alarms. It takes a village. Village builds it, runs it, and rebuilds it when life changes."

Stop.

---

## Key map

**Slides tab**

| Key | Does |
|---|---|
| → / space / click right half | next slide |
| ← / click left half | previous slide |
| 1 … 9 | jump to slide 1 … 9 |
| 0 | slide 10 (Measured) · press **-** or **=** for the last slide (soundbite) |
| F | fullscreen |
| A | autoplay on/off (114 s, captions). Space pauses autoplay. Not for the live pitch. |

Slide order: 1 Village · 2 The problem · 3 Build · 4 Run, the chat · 5 Run, the ledger · 6 Rebuild · 7 Safeguards · 8 What made this possible · 9 The block · 10 Family vs block · 11 Measured · 12 Soundbite + Open the Control Room.

**Control Room tab** (`presenter=1`)

| Key | Does | When |
|---|---|---|
| click BUILD / RUN / REBUILD | switch section | Rebuild at 1:25 |
| click a village pill, or **V** | next village | 2:30 |
| **L** | latest release receipt, large, with the Anchor recording | 1:35 |
| **Esc** | close overlay / back to live | after L, B, X |
| **U** | switch the phone between elder (you are Carmen) and unknown caller | only if you do the Carmen beat |
| **M** | post the money call through the real tool route (fallback for the phone call) | if the line fails |
| **D** | details toggle | avoid |
| **B** | block founding replay with audio | only in Q&A |
| **X** | panic replay of the current beat | last resort |
| **P**, **A** | trigger a new rebuild / approve it | do NOT use on stage: the receptionist is already applied |
| **R** | reset everything | NEVER |
| **F**, **1 2 3** | resume founding, type answers | NEVER during the pitch |

**Phones**

- Carmen's app: Llamar a Village dials the line (works). Llamar a Ana dials a 555 number (don't). Necesito ayuda only acknowledges today (don't).
- Marco's app: the verification card appears on its own when the money ask lands. Yes / No. Call Mamá dials the Village line (works; Luz answers).
- Ana's app: Home shows "What Village did" with the chips; Chat shows the asks.

## If a live beat fails

- **Call doesn't connect:** press **M**. "Same call, through the line's own tool route." Marco's phone still buzzes. Continue.
- **Marco's phone doesn't buzz within ten seconds:** "His phone's off, which is exactly the case the gate is for: no answer means don't send." Let it time out; Luz refuses.
- **Tunnel down:** judge's phone shows nothing. Say "the phones are on the venue Wi-Fi; here is the same screen" and press **6** in the slides (Rebuild) or **5** (the ledger). Keep talking.
- **Receipt overlay empty:** press **Esc**, click REBUILD, read the applied proposal and the receipt link there.
- **Village switch misbehaves:** skip it; press **9** in the slides and narrate over the block Control Room screenshot.

## Q&A you should expect

- **Is this an agent or a workflow?** A loop nobody triggers by hand: perceive events, calls, memory and its own evals; decide with model tool calls under three labelled autonomy modes; act through tools; remember as typed facts. The Watcher runs rounds; Evolve reads 14 days of traces; the Builder repairs its own builds. No framework: one process, one `llm()` factory, every step a span.
- **What if the model is wrong?** The model never has the last word on money, dosing, quiet hours, 911. The gate is pure Python tested with the model off. The model can ask; it can't send.
- **Generated or templated?** Every screen is a JSON spec from a fixed catalog, generated per role from the conversation. Unknown types render nothing.
- **Why not a group chat?** The group chat is where Thursday got lost. Village assigns, confirms, and shows each person only their part, and it sits in the chat as a participant.
- **Does it scale past one family?** One core, zero village names in it. A village is a spec, a data file and seeds in one index. The block came through the same pipeline, with its own gate parameters.
- **Which sponsor did what?** Daytona builds and tests every version from the `village-kit` snapshot. Anchor clicks it at 390×844 and the recording is on the receipt. Arize holds the traces the agent reads, the scam experiment and the Builder prompt on Prompt Hub. SurrealDB fans changes live and keeps memory with history. ElevenLabs is Carmen's whole product. Claude on Bedrock carried the morning.
- **What didn't you build?** Shift handoffs, the weekly digest, consent per affected person. Designed, on the Devpost, not shown.
