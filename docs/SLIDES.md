# Slides: the 3-minute pitch (6 slides)

Arc per LAYERS.md (D15): Build → Run → Rebuild → Anyone. Most of the 3 minutes is the live Control Room and phones; the slides are the frame around them. Plain words only (D18): say "it figured out who's who", not blueprint; "nothing reaches her untested", not release gate; "it checks with the real person", not R-MONEY-VERIFY. Every number is from `RESULTS.md` or stays `[MEASURE]`; a slide with `[MEASURE]` left in it loses that line before going on screen.

Name three sponsors on stage (Daytona, Arize, SurrealDB) as the rebuild loop; the rest are on Devpost.

Platform face per D30 ("Village" header, switcher, "New village"); founding per D29 (real intake, resumed at question 8 of 10 on stage).

Each slide lists: what's on screen, the stage lines (word for word), and the fallback if the live part fails. Spanish on screen always has the English caption under it.

---

## 1 · Thesis and stakes (0:00–0:20)

**On screen:** "Apps are built for millions. Village builds one for your people." Photo-style card: Carmen, 78, Queens, lives alone. One number: $7.75B taken from older Americans by scammers in 2025.

**Stage lines:**
> "Apps are built for millions. Village builds one for your people, and rebuilds itself when their life changes."
> "This is Carmen. She's seventy-eight, alone in Queens, and last week someone called pretending to be her son and asked for two thousand dollars."
> "Watch."

**Fallback:** none needed.

---

## 2 · Build (0:20–0:50)

**On screen:** the platform face first (D30): Control Room header "Village", the village switcher (Reyes · West 147th St), and "New village". Then the Reyes intake, picked up at question 8 of 10 (D29: the full conversation is in the video; on stage we resume near the end), people and needs filling in on the Control Room. Then three phones side by side under one address: "village.app/v/reyes · one site · three people". QR code to join.

**Stage lines:**
> "This is Village. Every group it runs is here, and anyone can start a new one."
> "Ana's been talking to Village about her family. It asks one question at a time, says back what it heard, and skips what it already knows. We're at question eight."
> (Village asks; Ana answers; the last cards appear) "It figured out who's who, how to reach each of them, what could go wrong, and Carmen's own rules."
> "Three different apps. Carmen gets three big buttons in Spanish. Ana gets the whole picture. Marco gets one question: is it my turn?"
> "Same address. Different software, because it's a different person. Scan this. You're in the family now."
> (to one judge) "You're Marco."

**Fallback:** if the intake stalls, play the recorded replay from question 8 and keep the QR join live: "Here's how that conversation ended an hour ago."

---

## 3 · Run: life happens (0:50–1:25)

**On screen:** Carmen's call on speaker, live captions in Spanish with English beneath. Countdown. Marco's prompt on the judge's phone.

**Stage lines:**
> "Carmen calls Village. Someone just called her as Marco."
> (Village, on speaker) "Voy a confirmar con Marco ahora mismo. No mande dinero todavía." Caption: *I'm checking with Marco right now. Don't send money yet.*
> "It checks with the real person, on his own phone, not the number that called."
> (judge taps "That wasn't me") "Ese no era Marco. No mande dinero. Ana ya lo sabe." Caption: *That wasn't Marco. Don't send money. Ana already knows.*
> "If Marco doesn't answer, the answer is still don't send. That rule is code, tested with the AI switched off."

**Fallback:** if the phone doesn't ring, the in-app prompt lands on the judge's phone (same check). If the judge doesn't answer: "Watch what happens when nobody answers," and the safe default speaks.

---

## 4 · Rebuild (1:25–2:25), the climax

**On screen:** Rebuild screen, one row per step with a concrete result:
- "Found the pattern: 2 calls in 7 days claiming to be Marco"
- Options considered: a check button (she has to remember under pressure) · a daily check-in call (doesn't stop the call) · **answer unknown callers first (chosen)**
- Daytona: "[MEASURE: n] of [MEASURE: n] floor tests passed" (Reyes count not in RESULTS yet)
- Timer on screen: Ana's yes → every phone patched (live on the demo Core at 13:00: 12 s; RESULTS.md)
- Anchor: live view of a phone-sized browser tapping Carmen's screen
- Arize: "evals passed" (score per release from the receipt: [MEASURE: score])
- "Ana approved" → every phone changes

**Stage lines:**
> "That was the second call. So Village speaks up."
> (Village, to Ana) "Mom's had two of these calls. Let me answer unknown callers for her?" (Ana) "Sí, hazlo."
> "Now it changes its own software. It builds and tests the change in a Daytona sandbox. An Anchor browser uses it the way Carmen would. Arize scores it. Nothing reaches her untested."
> "Ana said yes, so every phone in the room changes."
> (presenter calls Carmen's line from a second phone, as the scammer) "This time I'm the scammer."
> (Village answers) "Carmen's phone, this is Village. Who's calling?" ... "Marco says this isn't him. I won't put you through."
> "The scammer never reached her."

**Fallback:** if the build is slow, narrate the receipt from the earlier run: "Built, tested and checked at phone size in 15 seconds this morning; one build failed the contrast test and the agent fixed it." (14957 ms warm; caught-and-fixed build in `RESULTS.md`.) If the network fails, play the recorded rebuild clip within 5 seconds: "Here's the same thing an hour ago."

---

## 5 · Anyone (2:25–2:45)

**On screen:** the switcher flips from Reyes to West 147th St (D30: every region re-keys and clears). A completely different village: a city block during a blackout, its people, its apps. Receipt: "Released in 13.4 s · 33 floor tests passed."

**Stage lines:**
> "Same engine, a completely different group. A block in a blackout: who has oxygen at home, who has a generator, who checks on whom."
> "Built through the same pipeline. Released in thirteen seconds, thirty-three tests passed."
> "Same code, no Reyes anywhere in it. Describe your group and it builds yours."

"No Reyes anywhere in it" is verified (RESULTS.md, platform sweep 12:30: 0 hits in `core/` outside test fixtures).

**Fallback:** a static screenshot of the West 147th village.

---

## 6 · Close (2:45–3:00)

**On screen:** "30/30 scam calls caught · 0/20 false alarms · on our 50-case eval set". Under it: "It acts on its own. Code draws the lines it can't cross." Then: "It takes a village. Now every group can have one."

**Stage lines:**
> "On our fifty-case eval set, it caught thirty of thirty scam calls, with no false alarms."
> "Last night it did three things on its own, asked once, and stopped itself once, because of Carmen's rule."
> "It acts on its own; code draws the lines it can't cross, tested with the AI off."
> "It takes a village. Now every group can have one."

Numbers: scam set 30/30, 0/20 (Bedrock Haiku 4.5 + gate, Arize experiment `scam-model-20261016T153959Z`); round 3 alone / 1 asked / 1 refused (seeded data); gate 110 tests model off. All from `RESULTS.md` / `LANE-REPORT.md`.
