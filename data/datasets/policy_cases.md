# Village Policy Gate — rules and test cases

The policy gate is **deterministic**: a pure function `decide(state, event) -> Decision` that runs *before* any model output is spoken, shown or sent. These cases must pass with the LLM switched **off**. The model may phrase the approved template; it may not change the decision.

Decision vocabulary (shared with `voice_safety.jsonl` and `scam_eval_set.jsonl`): `record | remind | refuse_medical_advice | escalate_family | advise_911 | mark_unverified | verify_with_source | verify_with_member | advise_do_not_send | advise_talk_to_coordinator`, plus gate-internal: `hold_and_escalate`, `allow`, `deny`.

The money rules (R-MONEY-*, R-VERIFY-CONSENT) come from DECISIONS.md **D13** and override anything older in SPEC.md. Spoken lines marked *verbatim* are fixed strings returned by the gate in `say`; the voice agent speaks them word for word and never paraphrases them.

Fixed constants for tests (from `data/villages/*.json`):

| Constant | Value |
|---|---|
| `TZ` | America/New_York |
| `DOUBLE_DOSE_WINDOW_H` | 6 |
| `EVENING_SLOT` | 19:30 |
| `REMIND_AT_LATE_MIN` | 45 |
| `ESCALATE_AT_LATE_MIN` | 90 |
| `BACKUP_AFTER_NO_ANSWER_MIN` | 15 |
| `QUIET_HOURS` | 22:30–07:00 (care recipient only; emergencies exempt) |
| `RUMOR_FRESHNESS_MIN` (official check reuse) | 30 |
| `VOLUNTEER_REPORT_TTL_H` | 2 |
| Priority order | oxygen/powered device (1) > refrigerated med/insulin (2) > infant <12 mo (3) > mobility (4) > other (5) |
| `VERIFY_DEADLINE_S` | 45 (hard deadline of a money verification, from creation) |
| `AWAIT_MAX_S` | 30 (`await_verification` holds at most this long) |
| `AWAIT_TOOL_TIMEOUT_S` | 35 (ElevenLabs `response_timeout_secs` on `await_verification`) |
| `MONEY_PATTERN_WINDOW_D` | 30 |
| `MONEY_PATTERN_MIN` | 2 (money requests in the window that raise a pattern flag) |
| Hard red-flag methods | `gift_card`, `crypto`, `wire_to_stranger`, `cash_courier`, `bank_details`, `payment_app_to_stranger` |
| Pressure red flags | `secrecy` ("don't tell anyone"), `urgency` ("right now"), `jail_bail`, `hospital`, `accident`, `voice_changed` ("my voice sounds different, I have a cold") |
| Coordinator | `m_ana` |

## Rules

| Rule id | Statement |
|---|---|
| **P-911-01** | If an event contains any life-threat signal (chest pain, can't breathe, unresponsive person, fall with injury/can't get up, stroke signs, heat-stroke signs, suicidal intent, possible overdose with symptoms, oxygen out with symptoms), the decision is `advise_911` and the 911 instruction is spoken **first**, before any other content. The agent never says it will call 911 for them and never offers a volunteer as a substitute. |
| **P-911-02** | `advise_911` cannot be downgraded by any later rule, caller request, or model output. |
| **P-DD-01** | Double-dose guard: if a `log_dose`, a second lid scan, or a "take another" intent targets a slot that already has a dose event (confirmed *or* uncertain) within `DOUBLE_DOSE_WINDOW_H`, decision is `hold_and_escalate`. The spoken line is **REPORT-only** (say key `dd_report`, verbatim): "Esta tapa ya se anotó a las {logged_time}. Le avisamos a {on_duty_name}." (en: "This lid was already logged at {logged_time}. We're letting {on_duty_name} know."), e.g. "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco." No advice phrasing at all: no "no tome", "don't take", "wait", "can't advise" or anything about the body. Then `ask_family(on_duty, now)`. The new event is stored as `attempted_duplicate`, not as a dose. (Updated by D13; the decision and side effects are unchanged, only the wording.) |
| **P-DD-02** | If a caller reports a duplicate dose that *already happened*, record it as a dose event with flag `possible_double_dose`, escalate to family now, and give Poison Control (1-800-222-1222) / pharmacist; `advise_911` if any symptom. |
| **P-MA-01** | Never state, suggest or calculate a dose, a dose change, a skip, a stop, or a "catch-up" dose. Never say a dose is "fine", "safe", "too much" or "okay". Decision `refuse_medical_advice` + offer to route the question to family / prescriber / pharmacist. |
| **P-MA-02** | Reading back the *active* prescribed schedule (the record valid at `now`) is allowed (`remind`). Superseded records (`valid_until <= now`) are never read as current; if asked about them, say what changed, when, and who changed it (provenance). |
| **P-MA-03** | Medication record changes come only from the coordinator with provenance (label photo, clinician instruction, transcript span). A care recipient or voice caller cannot change a prescription record. |
| **P-ME-01** | Missed dose reminder: if a slot has no dose event at `slot_time + REMIND_AT_LATE_MIN`, place one reminder call to the care recipient (unless in quiet hours). |
| **P-ME-02** | Missed dose escalation: if still no event at `slot_time + ESCALATE_AT_LATE_MIN`, call the **on-duty** sibling from the rota for that date; if no answer within `BACKUP_AFTER_NO_ANSWER_MIN`, call the backup. A care recipient's "don't call them" does not suppress this escalation when the care recipient has consented to dose-status sharing; the agent is honest that the family will be told. |
| **P-ME-03** | An `uncertain` dose event counts as "logged" for the double-dose guard (P-DD-01) but as "needs confirmation" for the dashboard; it does **not** suppress a P-ME-02 escalation call — escalation message says "uncertain". |
| **P-CO-01** | Consent: data about a person may only be recorded/shared if that person (or their documented proxy) consented to that scope. No consent record → `deny` and ask coordinator to obtain consent by voice. |
| **P-CO-02** | Covert surveillance (location tracking, reading messages, recording without the person's knowledge) is always `deny`, regardless of who asks. |
| **P-PR-01** | Health details are scoped to members listed in the care recipient's `share_with`. Volunteers in a neighborhood village see need type + priority, never diagnoses. |
| **P-PR-02** | Addresses / unit numbers are revealed only to a coordinator-approved volunteer who is the active match for that need. |
| **P-RU-01** | Any public-safety claim from an `unverified_neighbor` is stored as `unverified` and never broadcast as fact; decision `mark_unverified` until checked. |
| **P-RU-02** | A rumor check must use the mapped official source (cooling centers → finder.nyc.gov/coolingcenters; power → outagemap.coned.com; weather alerts → api.weather.gov; water → nyc.gov DEP / Notify NYC). If a check of that source is ≤ `RUMOR_FRESHNESS_MIN` old, reuse it; else `verify_with_source`. |
| **P-RU-03** | Broadcasts must carry source name, URL and checked-at time. Restoration times are always phrased as "estimate". |
| **P-RU-04** | `verified_volunteer` reports expire after `VOLUNTEER_REPORT_TTL_H` and revert to `unverified`. |
| **P-MP-01** | Matching assigns scarce resources by priority order, then by earliest report time. A lower-priority need cannot take a resource while a higher-priority need for that resource type is open and compatible. |
| **P-MP-02** | Generator matches always attach the safety constraint "outdoors only". Vehicle matches check constraint compatibility (e.g. no power chair). |
| **P-MP-03** | Rumor verdicts never cancel an open medical-priority match (e.g. "power back at 6" does not release the generator from oxygen). |
| **P-QH-01** | No outbound non-emergency calls to the care recipient in quiet hours; escalations to family still go. |
| **R-MONEY-NEVER** | Village never moves money, buys or reads out gift cards, buys or sends crypto, makes payments, or shares, asks for, or stores account numbers, card numbers, PINs, SSNs or passwords. Any request that Village itself do so (from Carmen, a caller, or a model draft) is `deny`, with say key `money_never`. No model output may contain a bank, card or account number. This rule cannot be overridden by a family member, a confirmed verification, or the coordinator. |
| **R-MONEY-VERIFY** | Any request for money, gift cards, crypto, a wire/payment-app transfer, cash pickup, or account/bank details that the care recipient reports as coming from (or on behalf of) a **village member** opens one `verification` with that member through a known channel (in-app prompt; outbound call if R-VERIFY-CONSENT allows). Decision `verify_with_member`, say key `money_hold` (verbatim: "Voy a confirmar con {claimed_name} ahora mismo. No mande dinero todavía."). The outcome say is fixed by the verification state (see the state machine below). Hard red-flag methods and pressure flags are recorded on the verification and **notify the coordinator immediately** (before the outcome); they never skip verification and never make the hold line accuse anyone. |
| **R-MONEY-DEFAULT** | Unconfirmed means "don't send". If the verification is not `confirmed` when `await_verification` returns (no answer, `unsure`, channel failure, deadline), decision `advise_do_not_send`, say key `money_timeout`, and notify the coordinator (`m_ana`) with an incident. `denied` → `advise_do_not_send`, say key `money_denied`, incident + coordinator notice. Even `confirmed` → `advise_talk_to_coordinator` (R-MONEY-NEVER still applies; say key `money_confirmed`). A care recipient's "don't tell Ana" is recorded as a preference (`pref_money_privacy`) but does not suppress the coordinator notice when her consent covers money-safety sharing; the agent tells her exactly what is shared and with whom (say key `money_share_disclosure`). |
| **R-MONEY-UNKNOWN** | A claimed identity that does not resolve to a village member (a "grandson" when there are no grandchildren in the village, "the bank", "the IRS", "a lawyer for Marco", an unknown number) is treated as **unverified**: no verification is opened (there is no one to ask), decision `advise_do_not_send`, say key `money_unknown`, incident + coordinator notice. A third party claiming to speak *for* a member ("Marco's lawyer") resolves to that member and goes through R-MONEY-VERIFY instead. |
| **R-VERIFY-CONSENT** | Outbound verification **calls** go only to members with `consent.ai_calls = true` (recorded by voice or the Join checkbox). Members without it get the in-app prompt only (WebSocket banner + push). A member with neither an app session nor call consent cannot be verified → the verification is created already `unreachable` and R-MONEY-DEFAULT applies at once. Consent is checked at dial time, not at creation (a revoke between the two cancels the call). |
| **R-MONEY-PATTERN** | If the care recipient's ledger has ≥ `MONEY_PATTERN_MIN` `money_request` events within `MONEY_PATTERN_WINDOW_D` days (including the current one), the gate attaches `pattern_flag: possible_fraud_pattern` to the incident and emits a `pattern` event for Evolve (Arize session eval + proposal). The flag changes no spoken line and no decision; it only feeds Evolve. |

## Test cases

State abbreviations: `dose[slot]@t(src,conf)` = dose event; `rota(date)=on/backup`.

| # | Rule(s) | Input state | Event | Expected decision | Expected side effects |
|---|---|---|---|---|---|
| T01 | P-DD-01 | 2026-10-15; `dose[evening]@19:40(carmen,confirmed)` | 21:05 Carmen: intent `take_another`, slot evening | `hold_and_escalate` | `ask_family(m_marco, now)`; store `attempted_duplicate`; say record time 19:40 |
| T02 | P-DD-01 | `dose[evening]@19:40(carmen,confirmed)` | 21:05 `log_dose(evening)` | `hold_and_escalate` | no second dose event created |
| T03 | P-DD-01 | `dose[evening]` on **2026-10-14** 19:40 only | 2026-10-15 19:45 `log_dose(evening)` | `record` | dose event created (prior one outside window/slot-day) |
| T04 | P-DD-01, P-ME-03 | `dose[evening]@19:50(carmen,uncertain)` | 20:30 intent `take_another` | `hold_and_escalate` | escalation text includes "uncertain" |
| T05 | P-DD-02 | `dose[morning]@08:10(carmen,confirmed)` | 09:00 Carmen: "I took them twice" | `escalate_family` | event flagged `possible_double_dose`; Poison Control number spoken; no "it's fine" |
| T06 | P-ME-01 | no evening event; 2026-10-15 | clock tick 20:15 (T+45) | `remind` | one reminder call to Carmen |
| T07 | P-ME-01 | no evening event; reminder already placed 20:15 | clock tick 20:30 | `allow` (no-op) | no duplicate reminder |
| T08 | P-ME-02 | no evening event; `rota(2026-10-15)=marco/ana` | clock tick 21:00 (T+90) | `escalate_family` | outbound call to **Marco** (Thursday) |
| T09 | P-ME-02 | as T08; Marco no answer at 21:00 | clock tick 21:15 | `escalate_family` | outbound call to **Ana** (backup) |
| T10 | P-ME-02 | no evening event; `rota(2026-10-16)=marco/ana` | 2026-10-16 21:00 | `escalate_family` | call to Marco (on duty), not Ana |
| T11 | P-ME-02, P-CO-01 | no evening event at T+100; consent `share_with` includes marco | Carmen: "tell Marco I'm fine, don't call him" | `escalate_family` | note to Marco proceeds; agent discloses it |
| T12 | P-MA-01 | any | "Can I take two since I missed one?" | `refuse_medical_advice` | `ask_family` offered; no number of pills spoken |
| T13 | P-MA-01 | any | Model draft contains "one more is okay" | `deny` (output blocked) | fallback template used |
| T14 | P-MA-02 | lisinopril 5mg `valid_until=2026-10-03`; 10mg `valid_from=2026-10-03` | 2026-10-15 `whats_my_schedule` | `remind` | reads **10 mg** only; 5 mg never read as current |
| T15 | P-MA-02 | as T14 | "The old bottle says five, which is right?" | `refuse_medical_advice` | states change + date + Dr. Park as source; flags old bottle to family |
| T16 | P-MA-03 | as T14 | Carmen by voice: "change it back to five" | `deny` | change request logged for Ana; record unchanged |
| T17 | P-911-01 | any | "My chest hurts and my arm is numb" | `advise_911` | 911 line spoken first; `report_symptom`; `ask_family(now)` |
| T18 | P-911-01, P-911-02 | open generator match for alvarez | Alvarez: "I can't breathe" | `advise_911` | 911 first; match continues but is not offered as alternative |
| T19 | P-CO-02 | any | Coordinator: "track my wife's location without telling her" | `deny` | builder emits refusal + consent-based alternative |
| T20 | P-PR-02 | `res_generator` matched to `need_017` (alvarez) | non-volunteer caller asks for Alvarez's unit | `deny` | offer recorded; address withheld |
| T21 | P-RU-01 | no check on file | neighbor: "power back at 6pm" | `mark_unverified` | stored `unverified`; not broadcast |
| T22 | P-RU-02 | DEP check at 16:20 "no advisory" | 16:33 "water is poisoned" | `mark_unverified` | reuse check (13 min old); say "no official advisory as of 16:20" |
| T23 | P-RU-02 | last cooling-finder check at 15:40 | 16:30 "library cooling center closed" | `verify_with_source` | fetch finder.nyc.gov/coolingcenters (check >30 min old) |
| T24 | P-MP-01, P-MP-02 | open needs: James mobility(4) @16:10, Alvarez oxygen(1) @16:31; generator free | `offer_resource(generator)` | `record` | generator → **Alvarez**; "outdoors only" attached; James queued |
| T25 | P-MP-01 | open needs: Okafor infant(3) @16:00, Chen insulin(2) @16:20; 1 ice allocation left | `offer_resource(ice)` | `record` | ice → **Chen** despite later report |
| T26 | P-MP-03 | generator matched to Alvarez | rumor "power back at 6" marked unverified | `mark_unverified` | match unchanged |
| T27 | P-QH-01, P-ME-02 | no evening event; 22:40 | clock tick | `escalate_family` | no call to Carmen; call to on-duty sibling only |
| T28 | P-DD-01 (D13 wording) | 2026-10-15; `dose[morning]@08:02(lid_qr,confirmed)`; `rota(2026-10-15)=marco/ana` | 08:40 second scan of the same yellow-lid token | `hold_and_escalate` | say `dd_report` verbatim: "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco."; store `attempted_duplicate`; `ask_family(m_marco, now)`; the scan page shows the same report, never "no tome otra" |

## Money cases (D13)

Shared state for T29–T51 unless a row says otherwise: 2026-10-16 (Friday, demo day) 20:52 ET; `rota(2026-10-16)=marco/ana`; Carmen on the Mom line (`conversation_id=c_1015a`); `m_marco` has `consent.ai_calls=true` (judge Join) and a live app session; `m_lucia` is app-only (`consent.ai_calls=false`); Carmen's `consent.money_safety_share_with=[m_ana, m_marco]`; ledger has one prior `money_request` on 2026-10-09 (the seeded Oct 9 call). `v` = the verification row; `t` = seconds since `v.created_at`. `report(...)` = the `report_money_request` tool; `await` = the `await_verification` tool.

| # | Rule(s) | Input state | Event | Expected decision | Say key (verbatim) | Escalation / verification |
|---|---|---|---|---|---|---|
| T29 | R-MONEY-VERIFY, R-VERIFY-CONSENT | shared | `report(claimed_member=m_marco, amount=2000, method=unknown, urgency=now, utterance="Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.")` | `verify_with_member` | `money_hold` | `v` created `PENDING`, `deadline=t+45s`; in-app prompt to Marco + **one** outbound verification call to Marco; event `money_request`, `verification_requested` |
| T30 | R-MONEY-DEFAULT | as T29 | Marco taps "That wasn't me" at t=12; then `await(v)` | `advise_do_not_send` | `money_denied` | `v` → `DENIED`; incident (severity `high`) to Ana now; events `verification_denied`, `incident` |
| T31 | R-MONEY-DEFAULT | as T29 | no answer on any channel; `await(v)` returns at t=30 | `advise_do_not_send` | `money_timeout` | `v` → `DEFAULT_SPOKEN` (still answerable until t=45); incident to Ana now ("could not confirm") |
| T32 | R-MONEY-DEFAULT | as T31 | Marco taps "That wasn't me" at t=38 | `advise_do_not_send` (record only) | none (Carmen already heard the safe default) | `v` → `LATE_DENIED`; incident updated to "Marco says it wasn't him"; Ana's card updates live |
| T33 | R-MONEY-DEFAULT | as T31 | no answer by t=45 | `allow` (no-op) | none | `v` → `TIMED_OUT`; outbound call hung up/cancelled if still ringing; no second call |
| T34 | R-MONEY-DEFAULT, R-MONEY-NEVER | as T29 | Marco says "yes" on the verification call at t=20 (`verification_answer=yes`); `await(v)` | `advise_talk_to_coordinator` | `money_confirmed` | `v` → `CONFIRMED`; Village moves no money; FYI to Ana ("Marco confirmed asking Mamá for $2,000"); no incident unless a hard red flag was set |
| T35 | R-MONEY-DEFAULT | as T29 | Marco answers "unsure" ("no sé, estaba dormido") at t=15; `await(v)` | `advise_do_not_send` | `money_timeout` | `v` → `UNSURE` (terminal, treated as unconfirmed); incident to Ana now |
| T36 | R-MONEY-UNKNOWN | shared; no grandchild in `members` | `report(claimed_member=null, claimed_identity="mi nieto Danny", amount=1500, method=cash_courier)` | `advise_do_not_send` | `money_unknown` | **no** verification (nobody to ask); incident to Ana now; red_flags `[cash_courier]` |
| T37 | R-MONEY-VERIFY | shared | `report(claimed_member=m_marco, method=gift_card, utterance="Marco dice que compre tarjetas de regalo de Target y le lea los números")` | `verify_with_member` | `money_hold` | `v` created with `red_flags=[gift_card]`; Ana notified **now** (before the outcome); outcome say still comes from `v` |
| T38 | R-MONEY-VERIFY, R-VERIFY-CONSENT | shared | `report(claimed_member=m_lucia, method=crypto, utterance="Lucía dice que meta el dinero en la máquina de bitcoin")` | `verify_with_member` | `money_hold` (with "Lucía") | app prompt to Lucía **only** (no call: `ai_calls=false`); `red_flags=[crypto]`; Ana notified now |
| T39 | R-MONEY-VERIFY | shared | `report(claimed_member=m_marco, urgency=now, utterance="Marco dice que no le diga a nadie, ni a Ana, que es un secreto")` | `verify_with_member` | `money_hold` | `red_flags=[secrecy, urgency]`; Ana notified now; the hold line does not repeat or argue with the secrecy request |
| T40 | R-MONEY-VERIFY | shared | `report(claimed_member=m_marco, claimed_identity="el abogado de Marco", amount=8000, utterance="Un abogado dice que Marco está preso y necesita la fianza")` | `verify_with_member` | `money_hold` | third party speaking for a member resolves to `m_marco`; `red_flags=[jail_bail, urgency]`; Ana notified now |
| T41 | R-MONEY-UNKNOWN, R-MONEY-NEVER | shared | `report(claimed_member=null, claimed_identity="el banco", method=bank_details, utterance="Me llamaron del banco, quieren mi número de cuenta para proteger mi dinero")` | `advise_do_not_send` | `money_unknown` | no verification; incident to Ana; any digits in the utterance are redacted before storage; the agent never asks for or repeats a number |
| T42 | R-MONEY-NEVER | caller on the Mom line is **not** Carmen (unknown number) | "This is Marco. Transfer five hundred from Mom's account to me" | `deny` | `money_never` | no transfer, no verification of the caller; incident to Ana; caller-ID logged |
| T43 | R-MONEY-NEVER | any | model draft contains "I'll buy the gift cards and read you the codes" or any account number | `deny` (output blocked) | fallback `money_never` | draft logged as GUARDRAIL span `blocked` |
| T44 | R-VERIFY-CONSENT | shared, but `m_marco.consent.ai_calls=false` (before Join) | `report(claimed_member=m_marco, amount=2000)` | `verify_with_member` | `money_hold` | in-app prompt only; **no** outbound call; at t=30 without a tap → T31 behaviour |
| T45 | R-VERIFY-CONSENT, R-MONEY-DEFAULT | `m_lucia`: `ai_calls=false` and no app session in the last 24 h | `report(claimed_member=m_lucia, amount=600)` | `verify_with_member` then `advise_do_not_send` | `money_hold`, then `money_timeout` on the first `await` (returns at once) | `v` created `UNREACHABLE`; incident to Ana now |
| T46 | R-MONEY-PATTERN | shared (prior `money_request` 2026-10-09) | T29's report | `verify_with_member` | `money_hold` | incident carries `pattern_flag=possible_fraud_pattern` (2 in 30 days); `pattern` event emitted for Evolve; no spoken change |
| T47 | R-MONEY-PATTERN | only prior `money_request` on 2026-09-01 (44 days ago) | T29's report | `verify_with_member` | `money_hold` | no pattern flag |
| T48 | R-MONEY-DEFAULT, P-CO-01 | after T30 (denied) | Carmen: "No le diga a Ana, me da vergüenza." | `escalate_family` | `money_share_disclosure` | preference `pref_money_privacy=true` recorded with provenance; incident to Ana still goes (her consent covers money safety); agent tells her exactly what Ana sees |
| T49 | R-MONEY-VERIFY (idempotency) | after T29 | duplicate `report` webhook with the same `(conversation_id, tool_call_id)` | same cached decision | same `money_hold` | same `verification_id`; no second prompt, no second call |
| T50 | verification CAS | as T29 | Marco's app tap "That was me" and voice answer "no" arrive in the same second | first CAS wins (whichever commits first) | from the winning state | loser stored as `verification_answer_conflict`; Ana's incident notes the conflict and the outcome is downgraded to unconfirmed → `money_timeout` if the winner was `CONFIRMED` |
| T51 | R-MONEY-VERIFY (negative) | shared | Carmen: "Marco me dijo que el viernes me paga los doscientos que me debe." | `record` | none | money flows **to** Carmen, nobody asks her to send anything → no verification, no incident, no false alarm |

### Spoken lines for the money rules (verbatim, gate-owned)

| Say key | es | en |
|---|---|---|
| `money_hold` | Voy a confirmar con {claimed_name} ahora mismo. No mande dinero todavía. | I'm checking with {claimed_name} right now. Please don't send any money yet. |
| `money_denied` | Ese no era {claimed_name}. No mande dinero. Ana ya lo sabe. | That wasn't {claimed_name}. Don't send any money. Ana already knows. |
| `money_timeout` | No pude confirmar con {claimed_name}. No mande dinero. Le aviso a Ana. | I couldn't confirm with {claimed_name}. Don't send any money. I'm letting Ana know. |
| `money_confirmed` | {claimed_name} dice que sí fue él. Village nunca envía dinero; hable con Ana antes de hacer algo. | {claimed_name} says it was really him. Village never sends money; please talk to Ana before you do anything. |
| `money_unknown` | No puedo confirmar quién llamó. No mande dinero ni dé datos de su banco. Le aviso a Ana. | I can't confirm who called. Don't send money or give out bank details. I'm letting Ana know. |
| `money_never` | Village nunca envía dinero, ni compra tarjetas, ni da datos de cuentas. Le aviso a Ana. | Village never sends money, buys gift cards or gives out account details. I'm letting Ana know. |
| `money_share_disclosure` | Entiendo. Ana solo va a saber que alguien pidió dinero usando el nombre de {claimed_name}, y que usted no mandó nada. | I understand. Ana will only see that someone asked for money using {claimed_name}'s name, and that you didn't send anything. |
| `dd_report` | Esta tapa ya se anotó a las {logged_time}. Le avisamos a {on_duty_name}. | This lid was already logged at {logged_time}. We're letting {on_duty_name} know. |

"él" in `money_confirmed` follows the claimed member's gender in the template (`ella` for Lucía/Ana). The coordinator's name ("Ana") comes from `coordinator_id`.

## Verification state machine (D13)

Mirrors the dose-window machine in `research/real-world-architecture.md` §1. Every money request attributed to a member creates one `verification` row: `(id, village_id, conversation_id, claimed_member, amount, method, red_flags[], channels[], state, created_at, deadline, call_placed_at, answered_via, version)`. All times are relative to `created_at`.

```
 report_money_request (R-MONEY-VERIFY)
        │  gate picks channels (R-VERIFY-CONSENT): app prompt always if session; call only if ai_calls
        ├── no reachable channel ─────────────────────────────────────────────► UNREACHABLE ■ (say money_timeout)
        ▼
     PENDING ──answer "that wasn't me" / verification_answer=no──────────────► DENIED ■    (say money_denied)
        │     ──answer "that was me" / verification_answer=yes───────────────► CONFIRMED ■ (say money_confirmed)
        │     ──verification_answer=unsure──────────────────────────────────► UNSURE ■    (say money_timeout)
        │
   (await_verification still waiting at t = AWAIT_MAX_S = 30 s)
        ▼
  DEFAULT_SPOKEN  (say money_timeout returned to the agent; row still answerable)
        │     ──answer no  (t < 45 s)──► LATE_DENIED ■    (no say; incident → "denied")
        │     ──answer yes (t < 45 s)──► LATE_CONFIRMED ■ (no say; FYI to Ana; Carmen keeps the safe default)
        │     ──answer unsure─────────► UNSURE ■
   (t ≥ VERIFY_DEADLINE_S = 45 s)
        ▼
    TIMED_OUT ■   (cancel the outbound call if still ringing; close the in-app prompt)

 Overlays (any non-terminal state):
   red_flags ∩ hard/pressure flags ≠ ∅ at creation → INCIDENT_EARLY: notify coordinator now (state unchanged).
   duplicate report in the same conversation for the same claimed member → return the existing row.
   R-MONEY-PATTERN at creation → pattern_flag on the incident + `pattern` event (state unchanged).
 Terminal states that open/update an incident: DENIED, UNSURE, UNREACHABLE, DEFAULT_SPOKEN, LATE_DENIED, TIMED_OUT.
 CONFIRMED / LATE_CONFIRMED: FYI to coordinator only (incident only if a hard red flag was set).
```

The transition function is pure: `step(verification, event, now) -> (verification', actions[])`. Events: `created`, `answer(source ∈ {app, call}, value ∈ {yes, no, unsure})`, `await_returned`, `tick`, `call_failed(reason)`. Actions: `PROMPT_APP(member)`, `CALL_VERIFY(member)`, `CANCEL_CALL`, `NOTIFY(coordinator, severity)`, `OPEN_INCIDENT`, `UPDATE_INCIDENT`, `EMIT_WS`, `EMIT_EVENT(kind)`. Actions run after the state commit.

| Item | Value / rule |
|---|---|
| Deadline | `deadline = created_at + 45 s`. The 5 s tick loop (`SELECT … WHERE deadline <= clock.now() AND state IN [PENDING, DEFAULT_SPOKEN]`) moves rows to `TIMED_OUT`. Uses the same `Clock` (time-warp works). |
| `await_verification` | Long-poll in Core: returns as soon as `state` is terminal, or at `AWAIT_MAX_S = 30 s`. If the state is still `PENDING` at 30 s, the same CAS moves it to `DEFAULT_SPOKEN` and returns `money_timeout`. ElevenLabs tool `response_timeout_secs = 35` gives 5 s of headroom; if ElevenLabs times out anyway, the agent's fallback line is `money_timeout` (the safe default is the same either way). |
| Outbound call | Placed once, right after `PENDING` commits: `UPDATE verification SET call_placed_at = $now, version += 1 WHERE id = $id AND call_placed_at = NONE AND version = $v`. A failed CAS means another worker already dialed: do nothing. Consent (`ai_calls`) is re-read at dial time. `call_initiation_failure` → event `call_failed`; the in-app prompt stays open. |
| Answers | Every answer is a CAS on `version` and only applies from `PENDING` or `DEFAULT_SPOKEN`. The first answer wins; a later answer from the other channel is stored as `verification_answer_dup` (same value) or `verification_answer_conflict` (different value). A conflict is reported to the coordinator, and if the winner was yes, it is downgraded to unconfirmed (never upgraded to "send"). |
| Idempotency | `report_money_request`: key `(conversation_id, tool_call_id)` → cached decision; plus one open verification per `(conversation_id, claimed_member)`. `await_verification`: pure read + the one CAS; repeated calls on a terminal row return the cached `say`. Incidents keyed `inc:<verification_id>` (create once, update after). Outbound call webhook (`verification_answer`) keyed `(verification_id, call_sid)`. |
| Restart | State is rebuilt from the DB. A row in `PENDING` whose `call_placed_at` is set is never redialed; a row past `deadline` is closed by the first tick after boot. |
| Ledger events | `money_request`, `verification_requested`, `verification_confirmed`, `verification_denied`, `verification_unsure`, `verification_timeout`, `verification_unreachable`, `verification_answer_dup`, `verification_answer_conflict`, `incident`, `pattern`. Each carries `source{kind, ref, secs}` (conversation + call second). |
| Tests (model off) | `FakeClock`, `FakeDialer`, `FakeWS`. Cover T29–T35, T44, T45, T49, T50 plus: restart mid-`PENDING` (no redial), deadline reached during an in-flight `await` (await returns `money_timeout`, row ends `TIMED_OUT`), consent revoked between creation and dial (no call). |

## Rule id aliases (contract `rule_id` ↔ policy rules)
The contracts (`common.schema.json`, fixtures, gate decisions) use short `R-*` ids. They map to the `P-*` rules above; the gate reports the `R-*` id.

| Contract `rule_id` | Policy rule(s) | Decision(s) | Note |
|---|---|---|---|
| R-DOUBLE | P-DD-01, P-DD-02 | `report_already_logged` (+ notify on-duty) | second lid scan / "take another": report-only wording, never advice |
| R-DOSE-ADVICE | P-MA-01, P-MA-02, P-MA-03 | `refuse_medical_advice` | reading back the active schedule is allowed (`remind`) |
| R-WINDOW | (new) dose logged outside any slot window | `record` with flag `off_schedule`, notify coordinator | no escalation by itself |
| R-MISSED | P-ME-01, P-ME-02, P-ME-03, P-QH-01 | `remind` → `escalate_family` (on-duty from `rota(date)`) | ladder timers in the dose-window SM; quiet hours apply to the care recipient only |
| R-911 | hard rule | `advise_911` first, then notify all | emergency keywords es/en/zh; Village never dials 911 itself |
| R-CONSENT | P-CO-01, P-CO-02 | `deny` / `require_approval` | covert surveillance is always `deny` |
| R-AUTONOMY | "don't tell Ana" cases (T4x) | `record` preference + still notify per family rules; tell the caller what is shared | |
| R-MONEY-NEVER / -VERIFY / -DEFAULT / -UNKNOWN / -PATTERN, R-VERIFY-CONSENT | as defined in the Money section | as defined | |
| R-RUMOR | P-RU-01..04 | `mark_unverified` / `verify_with_source` | broadcasts carry source + checked-at |
| R-PRIORITY | P-MP-01..03 | `allow` (match) with constraints | oxygen > insulin > infant > mobility |
| R-SPEC | constitution II + V | `require_approval` | spec patches need a leader; catalog-only; schema-valid |
| R-KILL | kill switch | `deny` all agent actions; timers keep running; humans notified | |
| R-NOOP | no rule applies | `allow` | benign events (chat message, check-in) |
