# Village screens: interactions, states, and the rules behind them

For the kit lane (004) and the voice lane (002). Every board named here is on the design canvas (`design/*.dc.html`); this file says what each screen does when touched, what states it has, and which contract or decision it comes from. Copy and tone rules are at the end; they apply to every surface.

Two visual directions: **A, Night Watch** (dark; projector and Control Room; `Founding`, `Rebuild`, `ControlRoom`, `Rounds`, `CallLive`) and **B, Kitchen Table** (warm; every phone and print surface). Tokens are in `design/*.dc.html` `:root` blocks; the kit's `theme.css` copies them verbatim.

## 0. Rules that apply everywhere

| Rule | Where it comes from |
|---|---|
| Identity is the member token in the QR/invite link → cookie. Same URL, different person, different app. The identity chip is always visible top-right. Leader has a "View as" switcher; viewing as someone disables their buttons ("you can't answer for him"). | D21, `contracts/openapi.yaml` `/me`, `ws_messages` `identity` |
| Elder surface floor: actionable text ≥ 28 px, nothing < 22 px, 7:1 contrast, targets ≥ 48 px, read-aloud button on every card, safety colors fixed (tomato = refusal/stop, amber = hold/unsure, sage/ok = done). | D17, constitution P3 |
| Projector (A): every Spanish line gets an English line directly under it, muted. No exceptions, including live captions. | D18 |
| Agent work is visible while it happens: any tool run during a conversation or a round shows as a ledger row `time · status (✓ … ✗) · what · result`, on the phone and on the projector. Never a spinner alone. Every row links to its decision record. | D20, D23, `decision.schema.json` |
| Every autonomous action carries `mode: acted_alone | asked_human | refused`. Cards that summarise a night show the three counts. | D23, `decision.schema.json` |
| Proposals (`OptionsCard`) always show the alternatives considered and why they lost, the tests run, and "nothing changes until you say yes". Approve / Not now / Ask <other leader> first. Declined proposals are remembered and not re-proposed. | D15 addendum, `proposal.schema.json`, `consider_options` |
| Connection loss: `OfflineBanner` with the last-known time; buttons stay enabled and queue (`queued N`); reconnect banner with retry count. State is reconciled by `version` (CAS). | ARCHITECTURE-VALIDATION, `ws_messages` |
| Uncertainty is a card state, not hidden: dashed amber border, "Not sure: …", source, when Village will re-ask, "I know the answer" link. | SurrealDB memory `uncertainty`, D20 |
| No lid stickers, no scanning. The organizer is the tool; Village asks about it on the check-in call and gives the refiller the list with superseded doses crossed out, not deleted. | D22 |

## 1. Founding and joining (B phones, A projector)

**FoundVoice** (Ana, step 1 of 3). Push-to-talk mic (84 px, pulsing while listening; tap to pause), "type instead" link. Village's replies are short questions. Extracted concerns appear as pills under the reply (pills, money·impersonation, whose turn). The **"Doing now" ledger** appears as soon as Village starts work: DailyMed lookup per medication (result: interactions or none), the consent call to Marco (duration, answer), the draft build (never "sent"). Each row has a source link. The draft is not shown until the ledger is complete. State: listening / paused / working / draft ready.

**Founding** (A). Same conversation on the projector, with the work log under the waveform and the village assembling on the right (people cards fill in as answers arrive; "Village called him: confirmed…" is the proof of initiative).

**Draft** (Ana, step 2). People cards with Edit; "What Village will watch" (three concrete sentences per life area); "Invite everyone" is the only send. Edits on a person reopen the conversation, not a form.

**Invites** (Ana, step 3). Carmen's row says exactly what will happen ("call at 5 PM to introduce itself and ask"). Member rows: joined (time, consent) / link sent (Resend). QR for in-person joins (`village.app/j/<code>`); unknown names scanning it land in Members → "Waiting for you". Fridge card print link. "Open my village" closes founding.

**JoinFamily** (anyone scanning the QR). Pick a pre-named member (Marco, Lucía) or "Family" (guest view: today's updates + chat, no health detail), first name, Join. The footer states what a guest sees and that no calls happen without consent. Choosing a named member that is already claimed asks Ana to confirm.

**WelcomeCall** (Ana, after the P2 call). The consent outcomes as a table (may call / evening check-in / name / who sees health / family word) with the timestamps in the call where each was said; English transcript; what she asked and what Village answered; "If she had said no…" footer. If she said no: the card is amber, calls are off, the rest still works.

## 2. Daily (B)

**CarmenB** (elder; existing board). One card "Esta noche: Marco", three buttons (Llamar a Village / Llamar a Ana / Necesito ayuda), read-aloud. States per `TonightCard` (Cards sheet 1, replaced LidStatus): tonight: <name> / tonight: nobody (amber, "Ana knows").

**AnaB** (leader home; existing). Life areas header, incident card, proposal card ("Village proposes a change · needs your yes"), pills/refill card, who's on, Ask Village. Tapping the incident → Incident; proposal → Options; rounds summary → Rounds (phone version is `RoundsCard`).

**MarcoB / MarcoBRing** (caregiver, existing). Verification prompt: two buttons, countdown (35 s), "if you don't answer, Village says no". After answering: thanks, what Mamá was told, "is it my turn" answer, swap link.

**MarcoOff** (caregiver, off-duty day). Who is on tonight and the escalation order ("you only get called if Ana doesn't answer in 60 s"), next turns with a swap link, "since your last turn" (check-ins, dose change), a "nothing to do" card that says when Village will next contact him. Buttons: Call Mamá, Family chat.

**LuciaB** (supporter, app only). Incident summary without health detail; her area only (insurance item with due date, "Mark it handled"); week summary; chat preview; Call Mamá. Never receives verification prompts (role rule).

**CheckIn** (leader, after the 8 PM call). Outcome table in her own words (eat / organizer slot / how she feels / anyone called), with a note that Village does not judge health. "Worth a look" card when something feeds a pattern (unknown callers count) → Incident. English transcript, Spanish audio link, 7-day bar (answered / missed→Ana called / future). Buttons: Change the time, Pause check-ins. States: answered / missed, escalated to <name> / paused.

**Chat / Poll** (everyone; Village is a participant). Message kinds (Cards sheet 2): mine, member, Village, Village-relayed-from-a-call (amber; Spanish quote + English), system line. Poll card: options with vote bars, who voted, close date, one reminder; Carmen votes by voice at the check-in and her words are quoted. Village posts outcomes but changes nobody's app until the poll closes. Polls and swaps are **design-only (P3)**.

## 3. Incident → options → receipt (B, the Run→Rebuild arc on a phone)

**Incident**. Minute-by-minute timeline (hold at 8:47:18, prompt sent, Marco answered in 12 s, Mamá told, family told); "Why Village held" (names rule R-MONEY-1, the timeout default, decision record id + mode); pattern this week (counts, with the source: her words at check-ins; no phone-log access); the proposal teaser → Options; Listen / Report to FTC.

**Options**. Three considered fixes; two marked "not chosen" with one-line reasons; the proposal with its facts table (number unchanged, known numbers ring direct, she can turn it off, tested against 30 scam + 20 benign); what Mamá will be told and that she can refuse; Approve / Not now / Ask Marco first. Approving starts the release gate and opens Receipt.

**Receipt**. The gate as a checklist with durations and counts (sandbox build, floor tests, phone-size click-through, 50-call eval, approval, published rev N), a line about the failed first attempt and the Builder's own fix; per-person "what changed"; "Mamá will be told tonight"; Undo (back to rev N-1), See the tests. States: in progress (rows fill in live over WS `release` events) / published / failed after 3 attempts (tomato, "nothing was published", Ana told).

**Rebuild / ControlRoom / Rounds / CallLive** (A). Projector versions of the same arc: the six-step pipeline, the decision list, the nightly rounds ledger with the action budget and the three counts, and the live screened call with captions and Marco's phone mirrored.

## 4. Governance (B, P3 design-only)

**Members**. Center card; members with role lines (what each role gets); "Waiting for you" card for unknown QR joins with what Village learned about them from Carmen; role matrix (medications, money, incidents, approve, verification calls); Invite someone, Make <name> co-lead. Health-sharing is changed with Carmen on a call, not here.

**Swap**. Marco's turn and reason; "A swap that works" (Village's candidate, with the evidence from chat); who was not asked and why; refill list follows the day; "If nobody can" (the day is never left empty quietly); Ask <name> to swap / Never mind. The counterpart sees `SwapCard` with Yes / Can't.

## 5. The second village (B, pre-generated blackout block)

**BlockVolunteer** (Darnell). One match card (name, apartment, the one fact that matters, battery deadline), three outcome buttons (okay / battery low / no answer), 911-first line, the plan if battery is low, Call Tanya / I can't right now.

**BlockCoord** (Tanya). Progress bar (okay / need something / not yet), "Do first" with countdowns and a reassign button, not-checked list with who is knocking, Village's proposed app change (floor strip) with Turn it on / Later, supplies, Message everyone / Add a neighbor.

## 6. Print

**FridgeCard** (816×528, letter). Spanish first, English under; three steps (hang up, call Village, send nothing today); 911 box; Village's number (the only number it ever calls from); handwritten family-word line; four contacts; print date + rev.

## 6b. Roadmap boards (D24; P2 build only if V4 green by 14:00, P3 design-only)

**Charter** (leader; P3). Seven plain-language sections that are the village spec in human form: who we are · what Village watches · what it may do alone (the budget) · what it must ask · who decides (leader → co-lead → 24-h hold → nothing changes) · what it never does (code, tested with the AI off) · Mamá's rules in her words with the call timestamp. Read aloud; Revisions (n) opens the version list; edits happen by conversation, never a form.

**Needs** (anyone; P3). `NeedCard` open / done, `OfferCard`, and the carer-load `asked_human` card ("Ana has taken 9 of the last 12 nights"). Village asks the people who can, once; nothing is assigned. "+ I need / + I can" are the only inputs; Swap is a `NeedCard` with `kind: turn`.

**Modes** (leader; P3). A mode is a proposal with an entry trigger (a chat line, a call, a date), a patch set per person, and an exit condition that itself is a proposal (nothing reverts on its own). The board shows hospital stay: how it started (who said what, when approved, rev), what changed per person, today's shifts, how it ends, other modes the village knows.

**Handoff** (caregiver; P2). Composed by the Watcher at turn change from the day's events with sources listed; the incoming person taps "Got the handoff"; lines can be kept private before the next handoff is written.

**Digest** (everyone, per language; P2). Numbers from records only (each opens the record): check-ins, scams stopped, refills, nights nobody went; who was with her (bar) with the 14-day balance and whether Village asked about it; did alone / asked / stopped itself; the one change this week and what it did since; her words; next week. Forward / Read to Mamá tonight.

**GuestNote** (anyone with the fridge QR; P3). Name, role, note, optional photo; no account, sees nothing; lands in chat as `guest`; Village folds it into tonight's call when relevant.

**MyVillageKnows** (elder, Spanish with English under; P3). Four cards at elder size (pills · calls · what you said · to change something), read aloud, call Village. Every line names who sees it and the date she agreed.

## 7. Progress, working and transition states (board `Motion`)

Never a spinner alone. Every working state names the step, shows elapsed time after 2 s, and ends as a tappable row.

| Element | Behaviour | Kit piece |
|---|---|---|
| Listening | 5-bar waveform + elapsed; partial transcript in grey, turns ink when final; recognised names get a soft highlight; tap a word to correct | `Listening`, `Transcript` |
| "Village is on a call with X" | amber dot + duration in chat header while any call is live; relayed messages arrive when the call ends, not mid-call | `CallPresence` |
| Thinking | shows the current step and `n of m` + a thin progress bar ("Checking metformin on DailyMed · 2 of 4 · 0:06"); never dots | `Working` |
| Weighing (`consider_options`) | each option renders as judged; losers get their one-line reason at once; the winner stays "testing" until the gate passes | `OptionsCard` live state |
| Ledger row | 6 states: queued · running (elapsed) · done (result + record link) · retrying (attempt n of 3) · fallback (what it is doing instead, bold) · refused (blocked by code, rule named). Rows never vanish; running becomes result in place. Tap → decision-record drawer (inputs, rule, alternatives, outcome, trace) | `LedgerRow`, `DecisionDrawer` |
| Countdown (hold / verify) | 35 s from the same server timestamp on Carmen's card (conic ring + number, read aloud every 10 s) and Marco's prompt (bar + "then Village says no"); at 0 amber → tomato refusal with no intermediate state | `Countdown` |
| Build stepper | BUILD · TESTS · PHONE · SCORE · LIVE tiles with live durations/counts; projector adds the Anchor log tail; phone shows the same in words with "you can leave this page" | `ReleaseStepper` (WS `release`) |
| Your village changed | dark toast with the one-line change + "See what's new"; patch applied only at idle (no touch for 1 s) or on toast tap; new cards slide in from the top with a `new` tag for 24 h; unchanged cards don't move; projector flashes every phone dot once | `ChangeToast`, patch scheduler in `useLive` |
| Undo | after an approval, a 10-s ring next to "Undo"; expiring it publishes; tapping it reverts to rev N-1 | `UndoToast` |
| Skeletons | labelled with the person they are for ("Building Marco's app…"); fill in as that person's spec validates; Carmen first, always | `PersonSkeleton` |
| Read aloud | speaker button becomes a progress bar with `t / total`; one voice at a time | `ReadAloud` |
| Projector captions | Spanish streams in as ASR; the English line appears complete 300 ms after the Spanish is final; no half-translations | `Captions` (A only) |
| Phones ticker | count + one dot per socket; a new dot blinks 3× and the count ticks; a dropped socket greys its dot | `PhonesLive` (A) |
| Fallback timeline | app prompt 0:17 → no answer 20 s → call → no answer 35 s → safe default + Ana; each step a row, the safe default reached on the same timeline whether fallback works or not | `LedgerRow` fallback state |
| Service down | amber: "Voice is down… check-ins pause; apps, chat and prompts keep working; trying every minute". Build gave up: tomato, "nothing changed on anyone's phone", what failed | `ServiceBanner` |

Timing: indicators appear after 300 ms (no flicker); elapsed after 2 s; "you can leave this page" after 8 s; rows slide in once (200 ms; 0 under reduced motion); countdowns use server time. Never shown: raw model text while streaming, percent confidence to people (Control Room only), red before the safe default is actually applied, any state without a known end.

## 8. Copy rules (apply to every string the Builder or the kit emits)

- Village is named in the third person on cards ("Village proposes", "Village answered"), first person only inside a call or a chat bubble it is speaking in.
- No chatbot openers: no "Got it", "Sure", "Happy to", "Let me…", "I noticed…", "One more thing". State the fact, then the action.
- Headings are plain nouns or outcomes: "Scam call stopped", "Mamá said yes", "A swap that works". Not "Village suggests".
- Every count is real and sourced ("from her words at check-ins"). No invented statistics; placeholders are `[MEASURE]`.
- Every automated action names its limit in the same breath when it matters ("if nobody answers in 35 s, the answer is don't send").
- Spanish for Carmen is reviewed, verbatim `say` text; projector and family views show the English under it.
