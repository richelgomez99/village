# "Let's make your village": the features a village needs, and when each one lands

Plan of record for the fourteen features raised on Oct 16 (D24). The rule that keeps scope flat: **nothing on this list adds a system.** Each item is one of five sizes, and the size decides the phase.

| Size | Meaning | Where it can land |
|---|---|---|
| **copy/data** | words on a card, a field in `reyes_family.json`, a label with provenance | today, any version, no lane time |
| **one function** | ≤ 30 min in an existing lane, no new table, no contract change | today, V4 only, behind the V4 cut line |
| **one component** | a catalog card reusing an existing card pattern + one trigger | P2: designed now, built only if V4 is green by 14:00 |
| **design-only** | a board on the canvas + a paragraph on the Devpost | P3: today's canvas, never today's code |
| **roadmap text** | one sentence in the Devpost "What's next" | P3 |

Today's five versions (LAYERS.md) do not move. V4 gets two functions, V2 gets one data change. Everything else is a board or a sentence.

## Why these fourteen make the idea whole

The locked identity is "software that builds itself around your people." The demo proves it for the *center* of the village (Carmen): the agent protects her, then rebuilds itself when her life changes. A village, though, is the people around her **carrying weight together**. Without that, judges see a very good elder-safety product and a clever build pipeline. With it, they see a platform: the same agent that holds Carmen's hand on a scam call also notices Ana is burning out, writes the handoff note Marco needs at 6 PM, keeps the village's own rules in Carmen's words, and turns every bad night into a test the next change has to pass. That is "it takes a village," made of software, and it is what the Devpost page has to show even where today's code can't.

How each feature pays against the rubric (Impact / Technical / Creativity / Presentation, 25% each; sponsor bonus):

| # | Feature | Pays where | One-line rationale |
|---|---|---|---|
| 5 | Carmen's own rules | Impact, Presentation | Removes the surveillance smell: the limits the agent obeys are *hers*, in her words, enforced by code. Zero cost. |
| 11 | Every incident becomes a test | Technical, Arize | "Tested against 51 calls, last night's included" is a self-improving eval loop in one sentence; no other team will have it. |
| 2 | The village cares for the carers | Impact, Creativity | The agent's initiative turned toward the family, not just the elder. One Watcher query produces an `asked_human` row in Rounds; 0 s of stage time. |
| 3 | Handoffs | Impact | The single most-used artifact in real caregiving; composed from events we already store. |
| 9 | The week in the village | Presentation | Where the measured numbers live; the thing families forward. Rendered from decision records. |
| 14 | Consent per affected person | Technical, Presentation | Turns "Ask Marco first" from a button into a rule: a change that touches your phone needs your yes. |
| 6 | The charter | Technical, Presentation | A 78-year-old-readable page that *is* the agent's spec and budget. Answers "how do you control it?" with a URL. |
| 4 | Modes | Creativity, Technical | Generalises the receptionist rebuild: hospital, travel, holiday, blackout are planned rebuilds with an exit condition. The honest answer to "what else can it rebuild?" |
| 1 | Needs and offers | Impact | Reciprocity is what a village is; swaps and blackout matching are special cases of one `NeedCard`. |
| 7 | Village makes the boring calls | Impact, ElevenLabs | The outbound muscle (consent call, check-in) pointed outward: pharmacy, clinic, fraud line. |
| 8 | Guest notes | Creativity | The fridge QR takes a note from the nurse or the super without an account. |
| 10 | "What does Village know about me?" | Impact, Presentation | The consent ledger as a surface Carmen can hear read aloud and revoke by voice. |
| 12 | Village types | Scaling | The Founder adapts a starting blueprint; villages contribute components back. The scaling story in one sentence. |
| 13 | Governance escalation | Technical | Co-lead, then a 24-h hold, then nothing changes. The decision chain, like the call chain. |

## Phase by phase

### Today, V2 · copy and data (lane: builder/voice, 003) · 0 min of new lane time

**#5 Carmen's rules.** The gate already has `P-QH-01` (no non-emergency calls to the care recipient in quiet hours; `quiet_hours` is a param on the spec). Three changes, all data and words:
- `data/villages/reyes_family.json`: `quiet_hours: "21:30-07:00"` with `source: {kind: "call", ref: "welcome_call", secs: 108}` and her words: *"Después de las nueve y media, no."*
- The WelcomeCall card shows a row "Quiet hours · after 9:30 PM, no calls (her words)". The Rounds board and `RoundsCard` say *"Blocked by code: Carmen's rule, no calls after 9:30 PM"* instead of "no calls after 21:30".
- Pitch line (0:50 beat or close): "The rules it can't cross are hers."
Acceptance: the existing quiet-hours gate test reads the value from the spec fixture; the refused decision record carries `rule: P-QH-01, source: welcome_call`.

### Today, V4 · two functions (lane: evals/memory, 006) · ≤ 50 min total, behind the V4 cut line

**#11 Every incident becomes a test (T035, 30 min).** After a verification resolves (`refused` or `timeout`), append the call transcript + the expected decision to `evals/sets/<village_id>.jsonl` and tag the Arize dataset. The release gate (005) scores against the base set **plus the village's own set**. `Receipt` reads "Scored on 51 calls (last night's included)". Acceptance: a resolved verification adds exactly one row; the next release run reports `n_base + n_village`.

**#2 Carer load (T036, 20 min).** One Watcher check in the nightly round: nights per member over the last 14 days from the rota + check-in events. If one member carried > 60% and another eligible member < 20%, emit an `asked_human` decision: *"Ana has taken 9 of the last 12 nights. Ask Lucía to take the Sunday call?"* No action on its own (it is a change to people's duties, outside the budget). Acceptance: with the seeded rota, Rounds shows the row; counts become 4 alone / **2** asked / 1 refused.

If V4 is not green by 14:00, #2 is cut first, then #11. Neither touches the demo script; both only add rows to screens that already exist.

### P2 · one component each (designed now; build only if V4 is green by 14:00)

**#3 Handoff (T046, kit + 006, 25 min).** At every rota turn change the Watcher composes one `ChatMessage` of kind `relayed` to the incoming caregiver from the day's events (ate / organizer slot / who called / anything she said), and the same text lands as "Since the last turn" on their home card. No new table: it is a message with `source: events[]`.

**#9 The week in the village (T047, core, 25 min).** `GET /villages/{id}/digest?week=` renders decision records + events into one page per member in their language; sent Sunday as a chat message with a link. The measured numbers on the Devpost come from this view.

**#14 Consent per affected person (T048, gate, 20 min).** A proposal whose patch touches a member's view requires that member's `approved` event too, not only the leader's. The gate refuses `apply` until all `affects_member_ids` have answered; "Ask Marco first" becomes what the button already says.

### P3 · design-only boards today, code never today

Each gets one canvas board (B) and one Devpost sentence. Boards: `Charter`, `Needs`, `Modes`, `GuestNote`, `MyVillageKnows`, `Digest`, `Handoff`; `Types` and `Escalation` are text on the Charter board.

- **#6 Charter.** Plain-language page per village: who we are · what Village watches · what it may do alone (the budget) · what it must ask · who decides (leader, co-lead, then a 24-h hold) · what it never does · Carmen's rules. Versioned with the spec; read aloud; edits happen by conversation. It is the human form of `village_spec` + capabilities.
- **#4 Modes.** A mode is a proposal with an entry trigger, a patch set, and an exit condition. Hospital mode (visiting hours on every card, what to bring, who's there, check-ins paused); Ana away (co-lead approves, Marco gets the escalations); holiday; blackout (the second village already *is* this mode on its own). Built by the same release gate; exits by the same gate.
- **#1 Needs and offers.** `NeedCard`: who asked, for when, who can (rota + stated abilities + distance), one nudge, closed loop. `OfferCard` is the inverse. Swap is a `NeedCard` with `kind: turn`.
- **#7 Village makes the boring calls.** Outbound to known institutions with a scripted purpose and a consent flag: refill status, appointment confirmation, fraud-line report after an incident. Each call is a ledger row with the transcript.
- **#8 Guest notes.** The fridge QR's second path: "leave a note" (name, role, free text, photo) → a relayed chat message tagged `guest`; no account, no visibility into the village.
- **#10 What Village knows about me.** Per member: what it holds, who sees it, what they agreed to and when (from the welcome call / join consent), revoke by voice or tap.
- **#12 Village types.** Starting blueprints (aging parent · new baby · recovery circle · block in a crisis · small congregation · kids' team); the Founder adapts; components flow back to the shared catalog.
- **#13 Governance escalation.** Leader unreachable → co-lead → 24-h hold → nothing changes. Shown on the Charter.

## Scope guard (read before adding anything)

1. No new tables, no contract changes today. `events`, `decision`, `message`, `proposal` already carry everything above.
2. No new stage time. #5, #11, #2 appear as words on boards that are already in the arc (WelcomeCall, Receipt, Rounds).
3. A P2 item is built only after `V4-green` is tagged and only if the clock reads ≤ 14:00; otherwise it stays a board.
4. P3 items never get code today, however tempting at 13:30.
5. Devpost: the "What's next" section lists P2 + P3 by name with their boards; it never claims they work.
