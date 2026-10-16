# Slides: the 3-minute pitch (6 slides)

Arc per LAYERS.md (D15): Build → Run → Rebuild → Anyone. Most of the 3 minutes is the live Control Room and phones; the slides are the frame around them. Plain words only (D18): say "it figured out who's who", not blueprint; "nothing reaches her untested", not release gate; "it checks with the real person", not R-MONEY-VERIFY. Every number is from `RESULTS.md` or stays `[MEASURE]`; a slide with `[MEASURE]` left in it loses that line before going on screen.

Name three sponsors on stage (Daytona, Arize, SurrealDB) as the rebuild loop; the rest are on Devpost.

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

**On screen:** Control Room, then three phones side by side with one address above them: "village.app/v/reyes · one site · three people". QR code to join.

**Stage lines:**
> "Ana talks to Village about her family. It asks one question back."
> "It figured out who's who, what each person can and can't do, and what could go wrong."
> "Three different apps. Carmen gets three big buttons in Spanish. Ana gets the whole picture. Marco gets one question: is it my turn?"
> "Same address. Different software, because it's a different person. Scan this. You're in the family now."
> (to one judge) "You're Marco."

**Fallback:** if generation is slow, show the three apps already built ("built from this conversation at [MEASURE: time]") and keep the QR join live.

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
- Daytona: "[MEASURE: n] of [MEASURE: n] tests passed"
- Anchor: live view of a phone-sized browser tapping Carmen's screen
- Arize: "[MEASURE: score]"
- "Ana approved" → every phone changes

**Stage lines:**
> "That was the second call. So Village speaks up."
> (Village, to Ana) "Mom's had two of these calls. Let me answer unknown callers for her?" (Ana) "Sí, hazlo."
> "Now it changes its own software. It builds and tests the change in a Daytona sandbox. An Anchor browser uses it the way Carmen would. Arize scores it. Nothing reaches her untested."
> "Ana said yes, so every phone in the room changes."
> (presenter calls Carmen's line from a second phone, as the scammer) "This time I'm the scammer."
> (Village answers) "Carmen's phone, this is Village. Who's calling?" ... "Marco says this isn't him. I won't put you through."
> "The scammer never reached her."

**Fallback:** if the build is slow, narrate the receipts already on screen from the earlier run ("built and tested at [MEASURE: time]"). If the network fails, play the recorded rebuild clip within 5 seconds: "Here's the same thing an hour ago."

---

## 5 · Anyone (2:25–2:45)

**On screen:** a completely different village: a city block during a blackout. Its people, its apps, its build time.

**Stage lines:**
> "Same engine, a completely different group. A block in a blackout: who has oxygen at home, who has a generator, who checks on whom."
> "Built earlier today in [MEASURE: seconds]."
> "Caregiving and scam protection today. Any group tomorrow."

**Fallback:** a static screenshot of the blackout village.

---

## 6 · Close (2:45–3:00)

**On screen:** "[MEASURE: N]/30 scams caught · [MEASURE: M]/20 false alarms". Under it: "It acts on its own. Code draws the lines it can't cross." Then: "It takes a village. Now every group can have one."

**Stage lines:**
> "[MEASURE: N] of 30 scam calls caught."
> "It acts on its own; code draws the lines it can't cross, tested with the AI off."
> "It takes a village. Now every group can have one."

**Fallback if the eval number isn't measured:** drop the number line and close on the gate: "Forty-nine safety tests, all passing with the AI switched off." (49 gate tests, `RESULTS.md`.)
