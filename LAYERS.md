# Village: layered build plan and version map (plan of record, Oct 16)

**Rule of the day: there is always a working, pitchable version.** Each layer ends with a **version** (V0…V4): demo-path acceptance test green → `git tag V<n>` → Devpost text for that version updated. Work on the next layer sits behind flags (`VILLAGE_LAYERS`) and never breaks the tagged version. If a layer misses its cutoff, it's cut and the previous version is what we pitch.

Decisions: DECISIONS.md (D13 at the end is the latest). Fleet and lanes: FLEET.md. Contracts: contracts/. Acceptance checks: acceptance/.

---

## Version map

| Version | Cutoff | What works (acceptance) | What the 3-min pitch shows | Devpost headline |
|---|---|---|---|---|
| **V0 Safety core** | **11:00** | Fixture Reyes spec renders 3 views; check-in tool call → gate → SurrealDB → LIVE → WebSocket → all tabs update; refill card shows lisinopril 5→10 mg with history; **gate tests pass with the model off, incl. all money rules + the verification state machine** | Phones join and update live; the refill card shows the dose history; the safety rules are proven by tests | "Village: rules are code, not prompts" |
| **V1 Scam loop** (headline) | **12:15** | Real call to the Mom line → `report_money_request` → verification created → **judge-Marco gets an in-app prompt + an outbound call** → answer → `await_verification` returns `say` → spoken word for word; **timeout gives the safe default**; incident card to Ana; Arize spans for every step | The full Protect act: the phone rings, "that wasn't me", "ese no era Marco" | "When a scammer calls Mom as her son, Village checks with the real son before she sends a dollar" |
| **V2 Generate** | **13:00** | Ana's short conversation (Village asks 1–2 follow-ups) → builder → blueprint (people + profiles + life areas) streamed to the Control Room → 3 role apps from the catalog (config, no codegen) → per-member QR + Join/consent → **join scan = live-sync proof** → **"Ask Village why"** on the Control Room | Generate + Protect: a village built from a conversation, then the scam | "Describe your people. Village builds what each of them needs." |
| **V3 Release receipts** | **13:40** | Daytona build+tests of the family bundle (incl. ScamCheck, floor tests); Anchor phone-size run of scan + scam-verify flows (live view, recording); Arize release evals; **one caught-and-fixed failing build** traced; **second family (blackout block) pre-generated** | + receipts strip ("nothing reaches Carmen untested") + a 15 s second-family reveal | + "every release built in Daytona, tapped by Anchor, scored by Arize" |
| **V4 Evolve + rounds + number** | **14:15** | Village's rounds (D23) produce the autonomy counts; Arize session eval flags `possible_fraud` → agent investigates (Arize traces + SurrealDB facts with sources) → proposal → verify via the V3 gate → Ana approves → **ScamCheck button appears on every phone**; scam eval experiment → **measured number**; Fact view with provenance | Full storyboard | + "learns from every attempt: N/30 scams caught, M/20 false alarms" |
| Stretch | only if V4 by 14:00 | Anchor checks the caller's story on public sites (NYC inmate lookup) + opens the texted link in a Daytona sandbox | | |

**Freeze 14:20.** Draft video recorded at the V3 tag (~13:40) as insurance; final video 14:20–14:50; submit by 15:10.

---

## Demo arc at V4 (3:00), D15: Build → Run → Rebuild → Anyone
| t | Beat |
|---|---|
| 0:00–0:20 | **Thesis + stakes:** "Apps are built for millions. Village builds one for your people, and rebuilds itself when their life changes. Watch." (one line of stakes: Carmen, 78, alone at home; scammers took $7.75B from people like her last year) |
| 0:20–0:50 | **Build:** Ana's short conversation (Village asks 1–2 follow-ups) → it figures out who's who and what could go wrong → three different apps; judges scan to join (live-sync proof); one becomes Marco. |
| 0:50–1:25 | **Run (life happens):** the scam call → Village checks with the real Marco (his phone rings) → "Ese no era Marco. No mande dinero." Safe default if no answer. |
| 1:25–2:25 | **Rebuild (climax, live):** Village raises it: "Ana, Mom's had two of these calls. Let me answer unknown callers for her?" Ana: "Sí, hazlo." On screen, step by step: reads its own Arize traces → writes the change → **Daytona** builds + tests → **Anchor** taps it on a phone-sized browser → **Arize** scores it → Ana approves → **every phone in the room changes** ("¿Es de verdad?" for Carmen, scam alerts for the family). |
| 2:25–2:45 | **Anyone:** 15 s reveal: same engine, a completely different group (the blackout block), generated earlier today. |
| 2:45–3:00 | **Close:** "[N]/30 scams caught. It acts on its own; code draws the lines it can't cross, tested with the AI off. It takes a village. Now every group can have one." |

**Pitch backbone:** *Village builds it, runs it, and rebuilds itself as life changes, and before anything that matters, it checks with your people.*
**Devpost tagline:** *Village: software that builds itself around your people, and rebuilds itself as their life changes, without ever acting alone.* Stage and slides use the short version.

**On stage, plain words only:** "it figured out who's who" (not blueprint) · "what could go wrong" (not life areas) · "what each person can and can't do" (not capability profiles) · "nothing reaches her untested" (not release gate) · "it checks with the real person" (not R-MONEY-VERIFY).

## Two additions from the final review (cheap, high value)

> D24 adds three more, all inside existing versions: Carmen's rules (V2, data+copy), incident→test (V4, 006 T035), carer-load check (V4, 006 T036). Plan and cut order: `docs/VILLAGE-FEATURES.md`.

1. **"Ask Village why" (V2 core, about 30 min):** a text box on the Control Room. A judge types "Why did you call Marco and not Lucía?" and Village answers from its decisions log + memory sources, citing them (Claude over the log; read-only). It makes *sharp reasoning* interactive, and it's Q&A gold.
2. **Round-1 insurance:** record a 30 s clip of the scam moment the minute V1 is green (~12:15) and put it on the Devpost draft immediately. Round 1 is judged from the page; a real clip beats a promise.

**Live-moment fallbacks:** if the phone doesn't ring, the in-app prompt still lands on the judge's phone (same verification); if the judge doesn't answer, the safe default speaks; if the build is slow, receipts are already there; if the network fails, the recorded V3/V4 video is the backup.

---

## Assessment that led here (short)
Strengths: the empty lane (zero eldercare/fraud projects in 208 past submissions), the brief-perfect safety moment, audience participation, an adaptable platform. Risks addressed: scope (cut to V0–V4), perception (fraud headline, report-only pill wording), fragility (safe default + in-app prompt + receipts), first round (number + video). Full reviews: review/A–D.
