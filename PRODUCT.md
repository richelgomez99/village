# PRODUCT.md: what Village is when it's finished

> **Village: software that builds itself around your people.**
> Talk to Village about your people. It builds what each of them needs, runs it, and rebuilds itself as life changes, without ever acting alone.

This is the product definition that everything else derives from: user stories (by phase), demo features (by version), feature sets (by lane), and the spec-kit specs in `specs/`. Positioning: DECISIONS D15. Journeys and roles: EXPERIENCE.md. Mechanics: DECISIONS D13.

---

## 1. The finished product, surface by surface

| Surface | Who | What it is | Look |
|---|---|---|---|
| **Founder conversation** | the person who starts a village (Ana) | A voice (or text) conversation. Village asks 1–2 follow-ups, shows a **draft village** (people, roles, what each needs, rules), and waits for "Invite everyone". Later: "Marco switched to days" → the village updates. | B (warm) |
| **Per-person app** (PWA, any phone) | every member | Generated for that person from their profile: Carmen = 3 big buttons, Spanish, read-aloud; Ana = dashboard with life areas, incidents, proposals; Marco = "Is it my turn?" + verification prompts. Updates live. | B |
| **Phone line** | people who won't use apps (Carmen) | Calls Village or is called. Reports things, asks "¿ya me la tomé?", gets verification outcomes word for word. Welcome call on founding (P2). | voice |
| **Printables** | Carmen | A fridge card (Village number, family word, 911). Generated per family. | B print |
| **Village chat** | all members except Carmen (her chat is the phone line) | The family's group chat with Village as a participant: Village posts incidents, proposals (Approve inline), receipts, rota nudges; members talk to each other and to Village ("@Village, Marco switched to days" → rota rebuild; "@Village why…" → answer with sources). Every message keeps its source; system messages link to facts. | B |
| **Verification prompt** | the person a claim is about (Marco) | "Did you just call Mamá asking for $2,000?" by app and by phone; one tap answers. | B |
| **Proposals** | leaders | "Mom's had two of these calls. Want me to change her app?" Approve → the rebuild runs → every phone changes. | B |
| **Ask Village why** | leaders, judges | A question box: "Why did you call Marco and not Lucía?" Answers from the decisions log + memory, with sources. | B / A |
| **Control Room** (projector) | the demo, and in the product: a leader's "under the hood" | Live: the draft village assembling, the three apps, the verification countdown, the **rebuild pipeline** (traces → change → Daytona → Anchor → Arize → approve → live), the decisions log, release receipts, phones-connected counter, demo clock. | A (dark) |

**Interaction principles:** one action per screen for elders (≥88 px targets, ≥28 px text, 7:1 contrast, read-aloud); everything live (no refresh); every fact shows its source on tap; the agent explains itself; nothing consequential without the right person's say-so; safety wording is pre-written, never generated.

---

## 2. User stories by phase
Format: *As a <role>, I can <action>, so that <value>.* **(V#)** = demo version it ships in. P2/P3 = later phases (designed, not built tomorrow).

### P1: built tomorrow (V0–V4)
**Founding (V2)**
- US-01 As a founder, I can describe my people by voice or text and answer 1–2 follow-ups, so that Village understands who's who and what could go wrong.
- US-02 As a founder, I can review the draft village (people, roles, channels, rules) and edit before anything is sent, so that nothing happens without my approval.
- US-03 As a founder, I can tap "Invite everyone" and get a QR/link per person, so that each member joins their own way.

**Joining (V2)**
- US-04 As a member, I can open my invite, confirm who I am, choose how Village may reach me (consent to AI calls), and land in my own app, so that joining takes under a minute.
- US-05 As a member, my phone shows the family's state live (incidents, who's on, lids) the moment it changes, so that I never refresh.

**Daily (V0/V1)**
- US-06 As Carmen, I keep using my weekly pill organizer; Village may call me in the evening and I just look at it, so that my family knows without me remembering anything. As Marco, on refill day I get a checklist with the current doses and what changed, so that I never refill with an old dose.
- US-07 As Carmen, I can call Village in Spanish and say what happened or ask what's next, so that I don't need an app.
- US-08 As Marco, I can see "Is it my turn?" answered in one line, so that I know what's expected of me tonight.

**Protection (V1)**
- US-09 As Carmen, when someone asks me for money in a family member's name and I tell Village, Village checks with that person before I send anything, so that a scam can't get through me.
- US-10 As Marco, I get asked "Did you just call Mamá asking for $2,000?" on my phone (app and call) and can answer with one tap, so that my answer protects her within seconds.
- US-11 As Carmen, if nobody confirms, Village tells me not to send, so that silence is safe.
- US-12 As Ana, I see an incident card with what happened, who confirmed, and the source moment of the call, so that I can act.
- US-13 As any member, I can tap any fact and see where it came from and what it replaced, so that I can trust the record.

**Rebuild (V3/V4)**
- US-14 As a leader, when Village notices a pattern (from its own evals + memory), it asks me whether to change the app and shows why, so that the software adapts to our life with my consent.
- US-15 As a leader, I can approve a proposal and watch it built, tested in a sandbox, used by a real browser, scored, and then appear on every phone, so that nothing untested reaches my mother.
- US-16 As Carmen, after my family approves it, Village answers unknown callers on my line first and only puts through people it has checked, so that a scammer never reaches me; I keep a plain "Llamar a Village" button.
- US-17 As a leader, I can see every release receipt (build, tests, browser run, evals) and a build that was caught and fixed, so that I know the gate is real.

**Explain (V2)**
- US-17b As a member, I have a village chat where Village posts what happened and what it proposes, and where I can talk to my family and to Village, so that coordination happens in one place we already use.
- US-18 As a leader (or a judge), I can ask "why did you…?" and get an answer citing the decisions log and memory, so that the agent's reasoning is inspectable.

**Anyone (V3)**
- US-19 As a different group (a block in a blackout), the same conversation produces a different village with different modules and rules, so that Village isn't a family app.

### P2: next (designed; build if ahead)
- US-20 As Carmen, Village calls me to introduce itself and ask if that's okay; I can say no (welcome call, verbal consent).
- US-21 As Carmen, I decide who may see my health details; changes about me are read to me first.
- US-22 As Marco, if I confirm late, Village calls Carmen back with the outcome.
- US-23 As a founder, I can say "Marco switched to day shifts" and the rota and apps update after I approve.

### P3: vision (designed only)
- US-24 Co-leads; any member proposes adding someone (spouse, aide); a leader approves; Carmen is told.
- US-25 Quick polls when a change affects several people; Carmen asked by voice; a leader confirms.
- US-26 Rota negotiation ("Marco can't do Friday; Ana swap?").
- US-27 Village learns a family web chore by demonstration (Medicare plan compare) and runs it with approval.
- US-28 Someone leaves; consent revoked; data forgotten with a preview.

---

### D24 additions
Carmen's rules (P1, V2, data+copy), incident→test and carer load (P1, V4), handoff / digest / consent-per-affected-person (P2), needs & offers, modes, charter, outward calls, guest notes, "what Village knows about me", village types, governance escalation (P3, boards only). Sizes, rationale and cut order: `docs/VILLAGE-FEATURES.md`.

## 3. Demo features that must be complete, per version
| Version | Cutoff | Must work on stage | Stories |
|---|---|---|---|
| **V0** | 11:00 | Fixture Reyes village renders 3 apps; a check-in tool call → gate → live on all tabs; refill card shows the superseded dose; gate + verification SM tests pass model-off | US-05, 06, 08, 13 (static) |
| **V1** | 12:15 | Real call → money request → verification (app prompt + outbound call) → verbatim outcome; safe default; incident card; traces | US-07, 09–12 |
| **V2** | 13:00 | Founding conversation → draft → invite → join/consent; 3 generated apps; Ask-Village-why; Control Room | US-01–04, 18 |
| **V3** | 13:40 | Release pipeline: Daytona build+tests → Anchor run → Arize evals → receipts; caught+fixed build; second village pre-generated | US-15 (pipeline), 17, 19 |
| **V4** | 14:15 | Pattern detect → proposal (receptionist mode) → approve → **live rebuild** → every phone changes → **a second scam call is screened live and refused**; scam eval number; Fact view | US-14, 15, 16, 13 |

---

## 4. Feature sets (the spec-kit units)
| FS | Name | Scope | Lane(s) | Spec |
|---|---|---|---|---|
| **FS-1** | **Core spine & safety gate** | Core app, settings, WS hub, SurrealDB schema + LIVE subscriber, record-id mapping, lid-scan route, pure gate (all rules), dose-window + verification state machines, idempotency, clock + warp, decisions log | core, gate | `specs/001-core-spine-gate` |
| **FS-2** | **Verification loop (voice)** | ElevenLabs agents as code (mom-line, setup, village-caller), webhooks (init, tools, post-call), `report_money_request` / `await_verification` / `submit_verification_answer`, outbound call, in-app VerificationPrompt, incident card, verbatim say procedures | voice, core, kit | `specs/002-verification-loop` |
| **FS-3** | **Founding & generation** | Founder conversation (voice + text), blueprint extraction (streamed), profiles, draft review + invite, per-role render_app, validation/repair/template fallback, join/consent, QR, Prompt Hub fetch, Ask-Village-why | builder, kit, core | `specs/003-founding-generation` |
| **FS-4** | **Kit (generated apps + Control Room)** | Renderer, catalog (incl. VillageChat, ScamCheck, VerificationPrompt, IncidentCard, LifeAreas, HelperAnswer, Proposal, ReleaseStrip, DecisionsLog), WS client + JSON Patch, floor theme + village layer, elder/coordinator/helper views, scan/join pages, PWA, Control Room (A), printables | kit | `specs/004-kit-control-room` |
| **FS-5** | **Release gate** | Daytona snapshot + bundle build/tests (generated floor tests), dist download → Core serves, Anchor phone-size run + live view + recording, in-process Arize release evals (coverage, safety copy, translation back-check, accessibility image judge), receipts, caught-and-fixed build, blue/green `published_rev`, pre-warm | release, evals | `specs/005-release-gate` |
| **FS-6** | **Memory & evolve** | Agent Memory writes with provenance labels, history/uncertainty/Fact view, session evals (`possible_fraud`) in-process + logged to Arize, pattern detector → proposal, approve → patch_app → FS-5 pipeline → live patch, scam eval set experiment → measured number, second-village generation | memory, evals, builder | `specs/006-memory-evolve` |
| **FS-7** | **Pitch kit** | Devpost per version, README, slides, video script, thumbnail, reset_demo.sh, acceptance checks per version | pitch, core | `specs/007-pitch-kit` |

Dependencies: FS-1 → FS-2, FS-3, FS-4 (parallel) → FS-5 → FS-6; FS-7 runs alongside from 10:00.

---

## 5. Non-goals (tomorrow)
Real accounts/auth beyond invite tokens; SMS; HIPAA/BAA flows; payments; native apps; multi-tenant scale; zh/ar; live Medicare chores; voice design per family; the live judge's-family act.
