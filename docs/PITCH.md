# Village: the three-minute pitch

Rubric: Impact, Technical, Creativity, Presentation (25 % each) plus sponsor prizes. Devpost is round one, so every beat below is also a section on the Devpost page. Numbers in `[brackets]` come from `RESULTS.md` only. Never say a number that isn't there.

Props: your phone (Carmen's caller and, later, the scammer), the judge's phone (Marco), the projector on `control.html` (live), the fake sequences open in a second tab as fallback. No printed props.

Screen before you start: Control Room, Reyes family, idle, intake resumed at 8 of 10.

## Pitch rules (from YC / Paul Graham and hackathon judges' notes)

- Say what it is in the first sentence, in plain words. A narrow description beats a grand one.
- Problem as one person's story, and introduce the person before using her name. No statistics unless they're specific and ours.
- Be in the demo by 0:30. The demo is where judges decide; narrate what they're seeing.
- Specific measured numbers, once. No market size, no business model, no roadmap on stage.
- One speaker, slow and to the room, not to the screen. Don't talk and drive: the sequences are pre-staged; the judge taps the phone.
- Never say "this isn't working"; use the fallback line and keep moving. Never show a terminal or code.
- End on the soundbite and stop. Don't ask for questions.

---

## 0:00 Open (30 s) · screen: Control Room, "Village", empty state

Village is software that builds a village and runs it.

Everyone knows it takes a village. Nobody says that running one is a job: who's on tonight, who answers "did I take my pills", who checks the call that says "it's your son, send money". Today that job lands on one person, in a group chat, and when it slips, somebody gets hurt.

You describe your people to Village once: who they are, what each one can do, what the rules are. It builds a different app for each person, down to three big buttons for the one who won't learn an app, and a phone line for her too. It runs the week: the check-in calls, the refills, whose turn it is. And when the group's life changes, it changes itself: it notices, proposes, builds and tests the change, waits for a human yes, and every phone updates.

Any group. Here's one, built this morning.

## 0:30 Build (40 s) · screen: Reyes village, intake resumed at 8 of 10

This is the Reyes village. Carmen, seventy-eight, Spanish, lives alone in Queens. Ana, her daughter, is the one who set it up. Marco, her son, works nights. Lucía is in New Jersey.

Ana has been talking to Village for a few minutes. *(point at the transcript)* It asked who's in the family, when Marco can actually be there, Carmen's pills, the scam call last week, the building, who to call first. It did work while she talked. *(point at the work log)* It looked up all four medications on DailyMed. It called Marco to confirm his nights and ask if it may call him. It found that every night now has a name, which matters, because last Thursday nobody went.

Two questions left. *(read A10)* "Spanish only. A regular phone, she won't use apps. Big letters if anything. She'll answer a call; she won't read a text."

*(cards appear)* So Carmen gets the simplest app there is: three big buttons in Spanish, read aloud, nothing to learn. *(point at Carmen's phone mirror)* And a phone line she can call or that calls her. Ana gets a dashboard. Marco gets one card that answers the only question he has: is it my night.

*(read A11)* "After lunch, around one-thirty. And she hates calls at night."

Village calls Carmen itself, in Spanish, to introduce itself, and she can say no to all of it. Her rules are hers, not Ana's: after nine-thirty, no calls. That rule lives in code, not in a prompt.

*(A12, invites)* "Lucía should see the refill list too." Done. Invites out. Three apps from one conversation, nothing hand-built.

## 1:10 Run (45 s) · screen: Live panel, Marco's phone mirrored, captions

Now a Tuesday night. *(to the judge)* You're Marco. Keep that open. Carmen speaks Spanish; I don't, so I'll be her in English, and Luz answers in whatever language the caller uses. *(call the line on speaker)*

*(Luz greets in both languages; you, as Carmen)* "Marco called me crying. He says he's in trouble and needs two thousand dollars."

*(captions show the Spanish under the English)* Village doesn't argue with her and doesn't lecture her. It holds. *(Marco's phone buzzes)* The real Marco gets one question on his own phone. *(judge taps "That wasn't me")*

*(Luz, in the caller's language)* "That wasn't Marco. Don't send money. Ana already knows." *(the projector shows "Ese no era Marco. No mande dinero. Ana ya lo sabe." with the English under it)*

Forty seconds, no money moved, and the decision is on the record: the agent asked a human, the human answered, the gate enforced the default. If nobody answers in time, the answer is still don't send.

## 1:55 Rebuild (45 s) · screen: Ana's proposal card, then release receipt, then Live panel

Here's the part that makes Village different. A week later it reads its own traces and memory: three money requests from unknown callers in nine days. *(screen: proposal on Ana's phone)* It considered three options and proposes one: let Village answer unknown callers on Carmen's line and verify any money ask with the real person before she ever hears it.

Ana taps approve. Watch the room. *(release receipt runs)* Village writes the change, builds it in a Daytona sandbox, runs the floor tests. *(first attempt fails)* It caught its own failure, contrast on the elder view, patched it and rebuilt. Anchor clicks through it at phone size. Arize scores it. *(toast on every phone)* Every phone just changed. Live, without anyone touching the code.

Now I'm the scammer. *(call the line; as the scammer, in English)* "Hi, this is Marco's friend, he's in trouble and needs two thousand dollars."

*(Luz, in English to the English-speaking caller; the projector captions it in both languages)* "Carmen isn't available. Marco says that isn't true. There will be no money." Refused. Carmen never heard it.

## 2:40 Anyone (10 s) · screen: switch to West 147th St

Same code, no Reyes anywhere in it. *(click the other pill)* This is a block in Harlem during a blackout: an oxygen machine on five, insulin warming up, a bodega with a generator. Different people, different apps, same Village. Built in [13.4 s].

## 2:50 Under the hood (10 s) · screen: architecture section or numbers

One agent with its own tool loop, and a pure Python gate it can't argue with: money, dosing, quiet hours, tested with the model off. SurrealDB holds live state and a memory where a dose change is a dated fact with a source. ElevenLabs answers Carmen's number. Daytona builds and tests every rebuild, Anchor clicks it at phone size, Arize scores it and keeps the traces the agent reads. Claude on Bedrock.

[N] tests. Rebuild in [15 s] warm. Phone-size QA in [5 s]. Tool call to every phone in [~100 ms]. Scam evaluation: [X of Y] refused.

## 3:00 Close

It takes a village. Village builds it. *(stop; don't ask for questions)*

---

## If a live beat fails (say it, keep moving)

- **Language:** Luz greets in both languages and answers in the caller's. If a judge wants to hear Spanish, invite a Spanish speaker in the room to be Carmen at the table.
- **Call doesn't connect:** "The line is live on this number; here's the same call from this morning." Switch to the `scam` fake sequence tab, narrate the same words.
- **Marco's prompt doesn't arrive:** "His phone's offline, which is exactly the case the gate is for: no answer means don't send." Let the timeout run; Luz says don't send. That is a feature, not a failure.
- **Pipeline stalls:** switch to the `release` sequence: "This is this morning's run, same receipt." Keep the stopwatch line honest.
- **Receptionist call fails:** play the `evolve` sequence's refusal, say "recorded this afternoon".
- **Village switch misbehaves:** skip it; say "and the same code is running a Harlem block during a blackout; it's on the Devpost".

## Q&A you should expect

- **What if the model is wrong?** The model never has the last word on money, dosing or quiet hours. The gate is pure Python with the model off and [N] tests. The model can ask; it can't send.
- **Why not a group chat?** A group chat is where Thursday got lost. Village assigns, confirms, and shows each person only their part.
- **What's generated vs. templated?** Every screen is a spec from a fixed catalog of components, generated per role from the conversation. Unknown components render nothing, so the model can't invent UI.
- **Consent and privacy?** Every member says yes to calls on their own device. Carmen sets her own rules on the welcome call. Money incidents share what was asked and what she decided, never her balances.
- **Could this scale?** One Core serves many villages; the village id keys every record, span and live query. The block was born through the same intake as the Reyes family.
- **What did you not build?** Handoffs, the weekly digest, consent per affected person: designed, on the roadmap, shown in the Devpost.

## Devpost (round one) checklist

- Hero GIF: the receptionist refusing the scammer, captions visible, under 10 s.
- First three lines say the sentence: "Software that builds itself around your people. Describe your group; Village builds an app for each person, runs their week, and rebuilds itself when life changes."
- Sections mirror the beats above: Problem (Thursday, the scam), Build, Run, Rebuild, Anyone, Under the hood, Numbers (one table, all from RESULTS.md), Safeguards, What's next.
- A sponsor table with code paths, one row per sponsor: sponsor judges scan for their name.
- One honest line: what ran live today, what was recorded today, what is designed only.
- Both villages' numbers side by side.
