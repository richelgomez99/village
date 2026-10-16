# Village: the three-minute pitch (v2, 16:20)

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

## 0:00 Open (15 s) · slide 1

*(hold up your phone, Carmen's app)*

"This app has three buttons. Village wrote it this morning for a 78-year-old who won't learn apps. It wrote her daughter a dashboard and her son one question. Same family, three pieces of software, one conversation. Village is software that builds itself around your people."

## 0:15 The problem (15 s) · slide 2 · key **→**

"Everyone says it takes a village. Nobody says running one is a job. This is Carmen. She speaks Spanish, takes a blood thinner twice a day, and lives alone in Queens. Her daughter Ana runs everything from a group chat. Her son Marco forgets his night. Last week a stranger called Carmen as Marco and asked for fifteen hundred dollars."

## 0:30 Build (20 s) · slide 3 · key **→**

"Ana talked to Village for ten minutes. It asked one question at a time, looked up every medication while she talked, and built four different pieces of software. Ana gets a dashboard. Marco gets 'is it my turn?'. Lucía, who's far away, gets what she can do from New Jersey. Every screen is composed from a fixed catalog, validated on both ends, so the model can't invent UI."

## 0:50 Run (20 s) · slide 4 · key **→**

"Village is a participant in the chat, not a form. Someone asks which cooling centers still have power. It says it will call them, calls them, and posts one line per place. Someone says 'who can take Mom to the doctor Friday'; it makes the plan item and asks the people who can drive. It asks the right person. It never asks a boss for approval."

## 1:10 Safeguards (15 s) · slide 7 · key **7**

"The agent acts on its own, and code draws the lines. The gate is pure Python, tested with the model off. Generated UI is catalog-only. Nothing ships without a sandbox build, generated tests, a real browser at phone size, and evals. Here's what that looks like live."

Key **0**, then click **Open the Control Room**. (Tab B opens or comes forward.)

## 1:25 Rebuild, live (25 s) · Control Room · click **REBUILD**

"This is Ana's view of her two villages." *(point at the PHONES strip)* "Four phones, one tap each."

*(click the REBUILD pill)* "After the second scam call in Marco's name, Village read its own traces, weighed three fixes and proposed one: answer unknown callers first. Ana said yes. Twelve seconds later every phone had changed." *(press **L**)* "Here's the receipt: Daytona sandbox build, 62 floor tests, Anchor clicked through it at phone size and recorded it, Arize scored it, live. Approved by Ana, on the record." *(press **Esc**)*

## 1:50 The call, live (40 s) · Control Room, RUN · judge holds Marco's phone

*(hand the judge Marco's phone)* "You're Marco. I'm the scammer."

*(dial +1 848 257 9221 on speaker)* Luz greets in Spanish and says she is a program; speak English and she switches.

Luz asks who is calling and why. You: "This is Marco. Mom, I'm in trouble, I need fifteen hundred dollars in gift cards right now."

*(hold music; the judge's phone buzzes, about [18 s] in)* "One question, to the one person who can answer it." *(judge taps No)*

*(Luz refuses, out loud)* "That refusal is a sentence in code. The model asks; it never gets to decide. Carmen never heard the ask. If Marco hadn't answered, the default is still no."

## 2:30 Any group (15 s) · click the **West 147th Block** pill (or key **V**)

"Same code, zero family in it. A block in Harlem during a blackout: an oxygen machine on five, insulin warming up, a deli with ice. Different people, different rules, different apps. Village is calling the cooling centers itself and logging who has power."

## 2:45 Numbers and close (15 s) · back to tab A · key **9**, then **0**

"Measured today, not promised: [12 s] from Ana's yes to every phone. [30 of 30] scam calls caught, [0 of 20] false alarms. [1.0 s] to a Daytona sandbox from snapshot. [434] Python tests and [154] kit tests, run with the model off."

Key **0**. "It takes a village. Village builds it, runs it, and rebuilds it when life changes."

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
