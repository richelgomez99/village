# Village: the three-minute pitch

Rubric: Impact, Technical, Creativity, Presentation (25 % each) plus sponsor prizes. Devpost is round one, so every beat below is also a section on the Devpost page. Numbers in `[brackets]` come from `RESULTS.md` only. Never say a number that isn't there.

Props: your phone (Carmen's caller and, later, the scammer), the judge's phone (Marco), the projector on `control.html` (live), the fake sequences open in a second tab as fallback. No printed props.

Screen before you start: Carmen's app on your phone; projector on the Control Room, Reyes founding scene ready to replay to 9 of 10 (DEMO-NOTES, D33).

## Pitch rules (from YC / Paul Graham and hackathon judges' notes)

- Say what it is in the first sentence, in plain words. A narrow description beats a grand one.
- Problem as one person's story, and introduce the person before using her name. No statistics unless they're specific and ours.
- Be in the demo by 0:30. The demo is where judges decide; narrate what they're seeing.
- Specific measured numbers, once. No market size, no business model, no roadmap on stage.
- One speaker, slow and to the room, not to the screen. Don't talk and drive: the sequences are pre-staged; the judge taps the phone.
- Never say "this isn't working"; use the fallback line and keep moving. Never show a terminal or code.
- End on the soundbite and stop. Don't ask for questions.

---

## 0:00 Open: opener A (30 s) · screen: Control Room, "Village"

*(hold up your phone, showing Carmen's app)*

Three buttons. Village wrote this at ten this morning for a seventy-eight-year-old who won't learn an app. It wrote her daughter a dashboard and her son one question. Same address, three pieces of software, one conversation.

*(platform line, 15 s; point at the header: "Village", the village pills, "New village")* Village is software that builds a village and runs it. You describe your people once; it builds each person the smallest app that does their job, runs their week, and changes itself when their life changes, asking a human before anything that matters. Any group. Here's one.

## 0:30 Build (40 s) · screen: Reyes founding scene, paced replay

This is the Reyes village. Carmen, seventy-eight, Spanish, alone in Queens. Ana, her daughter, set it up. Marco, her son, works nights. Lucía is in New Jersey.

*(the paced replay runs: transcript left, "heard → knows → doing → will build" middle, people and phone mirrors right)* This is Ana's real conversation from this morning, replayed at its own pace. One question at a time. Watch the middle: every answer makes Village know something, do something, and decide what to build. It looked up all four medications on DailyMed. It called Marco to confirm his nights and ask if it may call him. *(phone mirrors gain cards)* Each card arrives one second after the reason for it.

*(the replay stops at 9 of 10; type the last answer live as Ana)* Last question, typed now: "Lucía should see the refill list too." *(Lucía's phone grows the refill card)* Done. Three different apps, nothing hand-built. Carmen's quiet hours are her own words, and that rule lives in code, not in a prompt.

## 1:10 Run (45 s) · screen: Live panel, Marco's phone mirrored, captions

Now a Friday night. *(to the judge)* You're Marco. Keep that open. Carmen speaks Spanish; I don't, so I'll be her in English, and Luz answers in whatever language the caller uses. *(call the line on speaker)*

*(Luz greets in both languages; you, as Carmen)* "Marco called me crying. He says he's in trouble and needs two thousand dollars."

*(captions show the Spanish under the English)* Village doesn't argue with her and doesn't lecture her. It holds. *(Marco's phone buzzes)* The real Marco gets one question on his own phone. *(judge taps "That wasn't me")*

*(Luz, in the caller's language)* "That wasn't Marco. Don't send money. Ana already knows." *(the projector shows "Ese no era Marco. No mande dinero. Ana ya lo sabe." with the English under it)*

About thirty seconds (the first live call today refused at 0:31), no money moved, and the decision is on the record: the agent asked a human, the human answered, the gate enforced the default. If nobody answers in time, the answer is still don't send.

## 1:55 Rebuild (30 s) · screen: Ana's proposal card, then the six-stage receipt, then the phones row

Here's the part that makes Village different. That was the second call in thirty days claiming to be Marco. *(proposal appears on Ana's phone)* Village noticed on its own, weighed three fixes, and proposes one: let it answer unknown callers on Carmen's line and check with the real person before she ever hears them. The other two are struck through with the reason.

Ana taps approve. Watch the room. *(receipt runs)* Village writes the change, builds it in a Daytona sandbox, runs the floor tests, an Anchor browser clicks through it at phone size, Arize scores it. *(NEW on every phone)* Every phone just changed. At one o'clock today that took twelve seconds from Ana's yes to every phone.

## 2:25 Receptionist (15 s) · screen: Live panel, captions

Now I'm the scammer. *(call the line; in English)* "Hi, this is Marco's friend, he's in trouble and needs two thousand dollars."

*(Luz screens, checks with Marco, refuses; captions in both languages)* Refused. Carmen never heard it.

## 2:40 Anyone (10 s) · screen: click the West 147th pill

*(click the other pill; the whole room refills)* This is a block in Harlem during a blackout: an oxygen machine on five, insulin warming up, a bodega with a generator. Different people, different apps. Same code, no Reyes anywhere in it. Describe your group and it builds yours.

## 2:50 Numbers, once (10 s) · screen: "What Village knows" + decisions log

A pure Python gate it can't argue with, tested with the AI off. On our fifty-case scam set: thirty of thirty caught, no false alarms. Twelve seconds from a yes to every phone. A dose change is a dated fact with its source, and every agent reads the same memory.

(Sources: RESULTS.md: scam set 30/30, 0/20, Arize experiment `scam-model-20261016T153959Z`; live rebuild 12 s at 13:00; Agent Memory 5 → 10 mg with source. Tests: 379 Python, 114 kit, 114 gate, all model-off.)

## 3:00 Close

It takes a village. Village builds it. *(stop; don't ask for questions)*

---

## Table demo: Thanksgiving (D36)

Same village, a new kind of need, so judges see the rebuild isn't only for safety.
1. On Ana's phone, Chat tab, type: "@Village we're doing Thanksgiving at Mom's on the 27th. Twelve of us. Marco brings the turkey, Lucía brings the pie and comes in on the 11:40 train…"
2. Village answers in the chat: it drafted "Add Thanksgiving to the village"; nothing changes until it's approved. The proposal card appears with Approve.
3. Tap Approve. The receipt runs (built in a sandbox, tested, clicked through on a phone, scored).
4. Show the phones: Ana gets a plan board (who brings what, pickups, the day's schedule); Marco and Lucía each get one line ("you bring the turkey · pick up Lucía at Penn Station"; "bring the pie · 11:40 train"); Carmen gets one Spanish line: "El jueves vienen todos. Marco trae el pavo."
Say: "Same village, a new need, nobody wrote code. It changed the right place in each person's app."
Honest note: this ran end to end on a test Core (builder lane, D36), not yet on the demo Core.

## If a live beat fails (say it, keep moving)

- **Language:** Luz greets in both languages and answers in the caller's. If a judge wants to hear Spanish, invite a Spanish speaker in the room to be Carmen at the table.
- **Call doesn't connect:** "The line is live on this number; here's the same call from this morning." Switch to the `scam` fake sequence tab, narrate the same words.
- **Marco's prompt doesn't arrive:** "His phone's offline, which is exactly the case the gate is for: no answer means don't send." Let the timeout run; Luz says don't send. That is a feature, not a failure.
- **Pipeline stalls:** switch to the `release` sequence: "This is the run from one o'clock, twelve seconds, same receipt." Keep the stopwatch line honest.
- **Receptionist call fails:** play the `evolve` sequence's refusal, say "recorded this afternoon".
- **Village switch misbehaves:** skip it; say "and the same code is running a Harlem block during a blackout; it's on the Devpost".

## Q&A you should expect

- **What if the model is wrong?** The model never has the last word on money, dosing or quiet hours. The gate is pure Python, 114 tests with the model off. The model can ask; it can't send.
- **Why not a group chat?** A group chat is where Thursday got lost. Village assigns, confirms, and shows each person only their part.
- **What's generated vs. templated?** Every screen is a spec from a fixed catalog of components, generated per role from the conversation. Unknown components render nothing, so the model can't invent UI.
- **Consent and privacy?** Every member says yes to calls on their own device. Carmen sets her own rules on the welcome call. Money incidents share what was asked and what she decided, never her balances.
- **Could this scale?** One Core serves many villages; the village id keys every record, span and live query. The block was born through the same intake as the Reyes family.
- **Is the founding live?** The paced part is this morning's real conversation (Sonnet 5.5, 65.8 s for all eleven answers), replayed; the last answer is typed live.
- **What did you not build?** Handoffs, the weekly digest, consent per affected person: designed, on the roadmap, shown in the Devpost.

## Devpost (round one) checklist

- Hero GIF: the receptionist refusing the scammer, captions visible, under 10 s.
- First three lines say the sentence: "Software that builds itself around your people. Describe your group; Village builds an app for each person, runs their week, and rebuilds itself when life changes."
- Sections mirror the beats above: Problem (Thursday, the scam), Build, Run, Rebuild, Anyone, Under the hood, Numbers (one table, all from RESULTS.md), Safeguards, What's next.
- A sponsor table with code paths, one row per sponsor: sponsor judges scan for their name.
- One honest line: what ran live today, what was recorded today, what is designed only.
- Both villages' numbers side by side.
