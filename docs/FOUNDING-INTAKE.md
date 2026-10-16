# Founding intake: the full conversation (V2, builder lane) — spec of record (D29, operator-written, 12:00)

The founding is an **intake conversation**, not one paragraph plus two follow-ups. The Founder drives it: after every answer it extracts structured fields, shows what it now knows and what is still missing, does any work it can do itself (lookups, coverage checks, the consent call), and asks for the single highest-risk missing thing. It never asks for what it can look up or compute. The whole conversation is ten topics; on stage Ana answers the last three live, the rest were answered earlier (resume mode).

All facts below match `data/villages/reyes_family.json`. Where the data file disagrees with itself, this file says which wins.

## 1. Intake plan (`data/intake/plan.json`)

Ten topics, in the order the Founder asks when nothing is known. Each has required fields; a topic is "covered" when its required fields are filled. The projector shows a coverage meter (`7 of 10 covered · 3 gaps`) and the gap list, updated after every answer.

| # | Topic | Required fields | Village does on its own |
|---|---|---|---|
| 1 | The person at the center | name, age, language, lives where, what goes wrong | extracts life areas; opens the blueprint |
| 2 | Who is in the village | each member: name, relation, where they live, distance to the center, what they take on | member cards appear as named |
| 3 | Availability | per member: days, window, hard constraints, reminders they want | **rota coverage check**: every night has a name, or Village names the gap |
| 4 | Health: medications | each med: name, dose, slots, prescriber, pharmacy, recent changes | **DailyMed lookup per med** (warnings, high-alert, interactions) → facts with url provenance; refill list with supersession; old-bottle risk |
| 5 | Health: routine | how pills are taken, what fails, who is called for "did I take them?" | dose policy rows (never says how many; already logged → report, tell on-duty; double-dose window) |
| 6 | Money | the incident, who handles money, accounts in play, the **family word** | R-MONEY-VERIFY / R-MONEY-DEFAULT / R-MONEY-NEVER switched on, verifier = named member |
| 7 | Home and day | daily routine, neighbors, building, super, who nearby | routines; neighbor as contact (role label only) |
| 8 | Emergencies | who first, which hospital, 911 rule | escalation ladder; 911 first everywhere |
| 9 | Channels and language | per member: phone / app / both, language, what they will actually use | per-person surfaces: phone line + fridge card, apps, calls |
| 10 | Consent and the center's own rules | consent per member (calls / app prompts / verifier); welcome call time; what Village must ask her, not Ana | **consent call to Marco** (availability + yes to calls) during the conversation; plans Carmen's welcome call; her rules stay **pending until she says them** |

Follow-up rule: one question per turn, the highest-risk uncovered field first (money and meds before home and day). If an answer covers several topics, the meter jumps and the Founder says what it now knows in one line before the next question. If Ana says "I don't know", the field is marked `unknown` and shown as a gap, never guessed.

Review turn: the draft blueprint (members, surfaces, rules on, gaps) is shown; Ana edits in words; Village patches and sends invites.

## 2. The Reyes transcript (demo; Ana is played by the presenter)

Village speaks as itself in conversation (questions are allowed to be first person: it is talking, not labelling a card). No chatbot openers. Short questions.

**A0 · Ana:** "Mom's seventy-eight and alone in Queens. She mixes up her pills, she almost wired money to someone pretending to be Marco last week, and last Thursday nobody went to see her because Marco and I each thought the other was going."
→ meter 1/10 · life areas Health, Money, People · gaps: everything else.
**V1:** "Who else is in this besides you and Marco, and where does everyone live relative to your mom?"

**A1:** "Marco and me, and our sister Lucía in New Jersey. Marco's in Astoria, ten minutes from Mom. I'm in Brooklyn, forty minutes. Lucía can't come on short notice, but she does the refills and the insurance calls."
→ 2/10 · cards: Carmen · Ana · Marco · Lucía (backup, refills, insurance).
**V2:** "What is Marco's week like? When can he actually be there?"

**A2:** "He works nights. Sunday to Thursday he has to leave by nine-thirty. He sleeps until two in the afternoon. He can do Tuesday, Thursday, Friday and Saturday evenings. He wants a text at three on his days so he doesn't forget."
→ ledger: `Calling Marco to confirm Tue/Thu/Fri/Sat and ask if Village may call him` (runs in the background; result lands two turns later).
**V3:** "And you?"

**A3:** "Monday, Wednesday, Sunday, after four. I do all the doctor visits. Sunday lunch is at Mom's and I fill her pill organizer then."
→ 3/10 · **rota coverage: every night has a name. Thursday is Marco.** (shown as a green row; this is the Thursday gap closed)
**V4:** "Her pills: what does she take, and who prescribed them?"

**A4:** "Eliquis morning and night. Lisinopril in the morning, which Dr. Park just doubled to ten milligrams on the third. Metformin twice a day. Atorvastatin at night. The old lisinopril bottle is still in her cabinet, that scares me. Farmacia La Esquina on 37th fills everything."
→ ledger: `DailyMed: apixaban ✓ (high-alert, bleeding)` `lisinopril ✓` `metformin ✓` `atorvastatin ✓`; refill list with `lisinopril 10 mg (was 5 mg, Oct 3, Dr. Park)`; need `old bottle in the cabinet` added. 4/10.
**V5:** "How does she take them, and what happens on the nights she isn't sure?"

**A5:** "Weekly organizer, yellow lid for morning, blue lid for evening. Two or three nights a week she calls me asking if she took them. Once she took them twice."
→ rules on: `Never says how many pills to take` · `Dose already logged → report it, tell the on-duty person` · `Missed dose → reminder, then the on-duty person`. 5/10.
→ ledger: `Marco confirmed Tue/Thu/Fri/Sat · yes to calls` (the consent call came back).
**V6:** "Money. Tell me about the call last week."

**A6:** "Someone called saying he was Marco, crying, in trouble, needed fifteen hundred dollars in gift cards. She was on her way to the store when Marco happened to call her. Marco handles her money stuff with her. She has one checking account and that's it."
→ rules on: `Money asked in a family member's name → check with that person first` · `Not confirmed → don't send` · `Village never moves money`; verifier: Marco (first), Ana. 6/10.
**V7:** "Pick a word only the family knows. Every real call from Village says it, so a caller without it is not us."

**A7:** "Pavo. Thanksgiving is at her place and Marco always brings the turkey."
→ family word set (never shown on the projector; the card says `family word · set`).
**V8:** "Her day and her home: what does a normal day look like, and is anyone nearby?"

**A8:** "Breakfast at eight with the morning pills. Blood pressure Monday, Wednesday, Friday, she writes it on a pad. Walk to the bakery at eleven with Doña Rosa, her neighbor on the third floor. Dinner at seven with her telenovela, evening pills at seven-thirty. It's a second-floor walk-up, no elevator; the super is Luis."
→ routines; contacts `neighbor (3rd floor)`, `building super`. 7/10.
**V9:** "If she falls or can't breathe, who is first?"

**A9:** "911, then me, then Marco. Elmhurst Hospital."
→ `Emergency → 911 first` · ladder Ana → Marco · hospital on the fridge card. 8/10.

*(Stage starts here: resume at 8/10. The presenter reads A10, A11 and the review live, about 60 seconds.)*

**V10:** "Her phone and her language: what will she actually use?"
**A10:** "Spanish only. A regular phone, she won't use apps. Big letters if anything. She'll answer a call; she won't read a text."
→ surfaces: Carmen `phone line · fridge card · Spanish, read aloud` · Ana `app + calls` · Marco `app + calls` · Lucía `app only`. 9/10.

**V11:** "Two things Village can't take from you: Lucía's own yes to being called, and your mom's rules. Village asks Lucía in her app and calls your mom in Spanish to introduce itself. She can say no to all of it. When is she sharpest?"
**A11:** "After lunch, around one-thirty. And she hates calls at night."
→ welcome call planned 13:30 · `quiet hours · pending her words` (becomes `P-QH-01 21:30–07:00 · "Después de las nueve y media, no."` after the welcome call). 10/10.

**V12 · review:** "Here is the draft: four people, three life areas, five needs, ten rules on, one thing pending your mom. What is wrong?"
**A12:** "Lucía should see the refill list too, she does the ordering."
→ patch: RefillCard added to Lucía's view · "Send the invites." → Invites screen.

## 3. What the projector shows during intake

Left: the transcript as it grows (Ana's words, Village's one-line "now I know" + its question). Middle: Village's work log (DailyMed rows, the consent call, the rota check, each a ledger row with state per `design/INTERACTIONS.md` §7). Right: the blueprint filling in (member cards, life areas, needs, rules on, coverage meter, gap list). The meter and the gap list are the proof that the agent is driving.

## 4. Implementation shape (fits spec 003 as written)

- `data/intake/plan.json`: the ten topics with required fields and the default question per topic.
- `founding.py` (T009 state machine): session state = filled fields; per turn: `record_answer` tool call (structured extraction, Sonnet 5.5 if the key is in, Haiku otherwise) → coverage → side-effects (T027 DailyMed, consent call, rota check) → next question. The existing clarify pause with the 30 s proceed stays for any turn.
- `POST /villages/{id}/answers` (K01) carries each answer; reasoning `note` frames carry the "now I know" line, the meter and the next question (1.2.1 `ledger` frames for the work rows).
- `data/builder/reyes_intake.jsonl`: this transcript as a fixture for `mode: fixture` replay (T016) and for `?resume=8` on stage.
- Fixture replay must still run the real side-effects (DailyMed, the consent call) so the ledger is real.

Data conflicts, decided here: Carmen's quiet hours are **21:30–07:00** (her words on the welcome call win over `escalation_policy.quiet_hours` 22:30). The prescriber is **Dr. Park** everywhere (not "Dr. Park" on the refill card). The dose change shown on cards and in Agent Memory is **lisinopril 5 → 10 mg, Oct 3**.

Cut line: if the live loop is not green by 13:20, ship fixture replay with real side-effects and the presenter reading A10–A12; the Founder's questions still come from the plan, so it still looks and is driven by the agent.
