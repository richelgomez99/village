# EXPERIENCE.md: Village end to end (journeys, governance, screens)

**Identity (D15):** *Village: software that builds itself around your people.* Earlier tagline kept as a supporting line: *Describe your people. Village builds what each of them needs.* Opening / contrast line: *Apps are built for millions. Village builds one for your people.* Closing: *It takes a village. Now every group can have one.*

**What it is (pitch paragraphs):** Village is an AI agent that builds and runs software for one specific group of people: a family with an aging parent, friends supporting someone through chemo, a city block in a blackout, a small team. One person describes their people in a conversation; Village works out who's involved, what each person can and can't do, and what could go wrong, then builds different software for each person (fitted to language, memory, tech comfort, schedule), the right way in for each (an app, a phone line, a printed QR sticker, a welcome call), the group's own rules, and a shared memory where every fact keeps its source. Nothing is sent until the group's leader approves; everyone joins with consent.

Then it keeps running: before anything consequential happens (money asked in someone's name, a missed check-in, a claim that needs confirming) it checks with the right person. The lines it can't cross are code, tested with the AI switched off. As the group meets new problems, Village proposes changes to its own software (after a second scam attempt: "let me answer unknown callers for Mamá"), tests them and ships them once a leader approves. **The demo group is the Reyes family** (a scammer calls Carmen as her son; Village checks with the real Marco), and a 15-second reveal shows the same engine building a completely different village for a city block in a blackout.

**Visual direction:** A (Night Watch, dark) for the *system*: projector, Control Room, founding blueprint, live moments. B (Kitchen Table, warm) for the *people and the physical world*: onboarding, family and elder apps, print kit, Devpost thumbnail, slides. Elder view always light, high contrast.

---

## Roles
| Role | Who | Can |
|---|---|---|
| **Leader** (can have co-leads) | Ana (+ Lucía) | approve members, roles, rules, app changes; resolve polls |
| **Center** | Carmen | sees who's in her village; decides who sees her health info; must OK anything that changes what's shared about her; can say no to Village |
| **Caregiver** | Marco | on the rota; receives escalations/verifications; proposes changes |
| **Supporter** | a spouse, a grandchild | updates + tasks; no health info unless Carmen allows |
| **Contact** (not a member) | neighbor, aide, doctor's office | may be called for a stated purpose; sees nothing |

## Governance in phases
- **Phase 1 (build tomorrow, V2):** single founder/leader (Ana). Founder speaks → **draft village** → review/edit → **Invite everyone**. Members join via invite link/QR with consent. Evolve proposals → leader approves (V4). Every decision is in the decisions log.
- **Phase 2 (stretch V3/V4):** **Carmen's welcome call** (outbound, Spanish): introduces Village and who's in her village, asks "¿Le parece bien?", captures her preferred name, best times and the family word, records verbal consent. Her "no" is respected. Changes involving her info show "Carmen was asked."
- **Phase 3 (design only: Devpost/slides/vision):** co-leads; members propose additions (e.g. "add my wife Sofía as a supporter") → leader approves → Carmen is told; quick **polls** when a change affects several people ("Nightly 8pm check-in call for Mamá?" members tap, Carmen asked by voice, agent summarizes, leader confirms); rota negotiation; role/routine editor; someone leaving; consent changes.

## Journeys (screens per step)
| # | Journey | Screens (style) | Phase |
|---|---|---|---|
| 1 | **Found:** Ana describes the family | Founding by voice (B), blueprint assembling (A, projector) | 1 |
| 2 | **Review the draft** | Draft village: people, roles, channels, rules; edit; "Invite everyone" (B) | 1 |
| 3 | **Invite & join** | Invite sheet + QR per person (B); Join/consent per role (B); print kit (B) | 1 |
| 4 | **Carmen's welcome call** | Call transcript card on Ana's phone + Control Room (A) | 2 |
| 5 | **Daily life** | Carmen home (B elder), Ana dashboard with life areas (B), Marco "is it my turn?" (B), lid-scan pages (B) | 1 |
| 6 | **Incident: the scam call** | Scam moment (A projector), Carmen hold card, Marco verification prompt, Ana incident card (B) | 1 |
| 7 | **Evolve** | Detect→investigate→fix→verify (A), proposal card (B), "Carmen was asked" chip (B, phase 2) | 1–2 |
| 8 | **Grow & govern** | Add-member proposal, leader approval, poll card, members & roles screen (B) | 3 (design) |
| 9 | **Proof** | Control Room: decisions log, release receipts, gate, counter (A) | 1 |

## Demo mapping (V4)
Generate becomes **Founding**: Ana speaks → blueprint (A) → draft review (B) → "Invite everyone" → judges join, one becomes Marco. Then Protect (scan + scam), Evolve (+ second-family reveal), Proof + close. Optional 10 s audio of Carmen's welcome call if phase 2 lands.

## Data/contract implications (phase 1)
- Village has `status: draft|active`; members have `role` (leader|center|caregiver|supporter|contact) and `join_channel` (welcome_call|invite_link|none).
- Endpoints: `POST /villages` returns a **draft**; `POST /villages/{id}/activate` (leader) sends invites; `POST /villages/{id}/members/proposals` (phase 3).
- Gate rule: invites/outbound calls only after the leader activates; Carmen's welcome call needs no prior consent for an introduction but records her answer; any "no" disables Village calls to her (app/stickers can remain if the family asks).
