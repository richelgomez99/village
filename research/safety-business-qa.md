# Village: Safeguards, Regulation, Business, Judge Q&A

Prepared Oct 15, 2026 for the Oct 16 NYC pitch. This is practical orientation, not legal advice. Treat every "likely" as something to say carefully on stage.

---

## 1. Regulatory map (US, 2026)

### FDA: is this a medical device?
- **Probably not, if we keep the claims narrow.** FDA's list of software it will not enforce against includes *"Software functions that keep track of medications and provide user-configured reminders for improved medication adherence"* and apps that let *"a patient or caregiver ... create and send an alert or general emergency notification to first responders."* https://www.fda.gov/medical-devices/device-software-functions-including-mobile-medical-applications/examples-software-functions-which-fda-will-exercise-enforcement-discretion
- FDA revised its **General Wellness** and **Clinical Decision Support (CDS)** guidances on **Jan 6, 2026**. Wellness still uses a two-part test: wellness-only intended use plus low risk. CDS now puts more weight on transparency, and the more of a "black box" a tool is, the more likely FDA treats it as a device. https://www.kslaw.com/insights/articles/fda-updates-general-wellness-and-clinical-decision-support-guidance-documents · https://www.thefdalawblog.com/2026/01/a-busy-day-in-the-cdrh-neighborhood-updates-to-the-cds-and-general-wellness-guidance-documents/
- **Where the line is:** logging doses, sending reminders the user configured, and flagging *"you already logged this dose at 8:02am"* all count as tracking and adherence. Telling her to take, skip, or change a dose, or interpreting symptoms into a diagnosis, moves toward a device or CDS. **Our policy gate exists to keep us on the safe side of that line.** The double-dose guard only reports facts from the log ("already recorded today; I'm calling Marco"). It never gives a dosing instruction.
- Wording to use on stage: "medication logging and family coordination." Avoid "manages medications" or "prevents overdoses."

### HIPAA vs FTC vs state law
- **HIPAA:** it does not apply to a direct-to-consumer app that is not a covered entity (plan, provider, clearinghouse) or a business associate of one. **It does apply once we sell to an MA plan or a home-health agency.** Then we sign a BAA and must meet the Security Rule.
- **FTC Health Breach Notification Rule (amended Apr 26, 2024; effective Jul 29, 2024):** it explicitly covers health apps not covered by HIPAA. A "breach" includes an *unauthorized disclosure*, such as sharing data with an ad SDK, not just a hack. We would owe notice to users, the FTC, and sometimes the media. https://www.wsgrdataadvisor.com/2024/05/ftc-final-rule-officially-broadens-health-breach-notification-rule-targets-health-and-wellness-apps/ · https://www.insideprivacy.com/health-privacy/ftc-issues-final-rule-to-expand-scope-of-the-health-breach-notification-rule/ FTC Act §5 enforcement such as GoodRx and BetterHelp shows the risk.
- **Washington My Health My Data Act:** applies nationwide to anyone serving WA residents. It requires opt-in consent to collect consumer health data, separate consent to share it, and a private right of action. Design to it as the strictest baseline. https://www.woodsrogers.com/insights/publications/my-health-my-data-act-washington-states-new-health-data-privacy-data-law-has-a-nationwide-reach
- **New York HIPA:** Gov. Hochul **vetoed** it on Dec 19, 2025. A revised bill was introduced in 2026, so watch it. https://www.insideprivacy.com/health-privacy/new-york-governor-vetoes-restrictive-health-privacy-law/ · https://www.mofo.com/pdf/resources/insights/260316-nyhipa-returns-in-2026-revised-bill

### TCPA / FCC: AI voice calls
- **FCC Declaratory Ruling, Feb 8, 2024:** AI-generated or cloned voices count as an "artificial or prerecorded voice" under the TCPA, effective immediately. https://cooley.com/news/insight/2024/2024-02-15-fcc-ai-generated-robocalls-illegal-under-the-tcpa
- **Effect on us:** outbound escalation calls to a sibling's cell phone need **prior express consent**. Because the calls are informational, not telemarketing, oral or written consent is enough, though written consent is best practice. https://www.daypitney.com/insights/publications/2023/01/12-tcpa-revisions-fcc-prerecorded-voice-message-calling. The TCPA also exempts calls made for "emergency purposes," but **do not rely on that exemption.** Collect explicit consent from each sibling during setup, log it in a consent registry, and honor "stop calling me" right away.
- **FCC NPRM, Aug 7, 2024:** proposes requiring a disclosure **at the start of each AI-generated call**. It has not been finalized, so we comply ahead of it. https://www.kelleydrye.com/viewpoints/blogs/ad-law-access/fcc-proposes-new-tcpa-rules-for-ai-calls-and-texts
- **Disclosure laws:** California SB 1001 (2018) bans undisclosed bots in commercial or political persuasion. https://perkinscoie.com/insights/update/i-am-robot-californias-new-law-requires-disclosure-use-bots. Utah's AI Policy Act was narrowed in 2025 by SB 226/332 to disclosure on request or in high-risk interactions, and now sunsets in July 2027. https://www.davispolk.com/insights/client-update/utah-scales-back-reach-generative-ai-consumer-protection-law. **EU AI Act Art. 50** requires that people be told they are talking to AI, and it took effect **Aug 2, 2026**. https://www.cooley.com/news/insight/2026/2026-08-03-eu-ai-act-transparency-obligations-take-effect-2-august-2026. **Our rule:** every call opens with "This is Village, an automated assistant for the Rossi family."

### Elder autonomy and consent
- Research on monitoring older adults keeps finding the same issues: informed consent, privacy and autonomy, capacity, and the power imbalance between caregivers and the person being cared for. Older adults are often more willing than their caregivers to trade privacy for staying at home, but they often don't understand what data is collected. https://bmcgeriatr.biomedcentral.com/counter/pdf/10.1186/s12877-019-1155-6.pdf · https://pmc.ncbi.nlm.nih.gov/articles/PMC7491435
- **Design rules:**
  - Mom consents herself, by voice, on a recorded first call.
  - She can ask "what do you tell my kids?" and hear exactly what is shared.
  - Sharing is scoped: siblings see doses and escalations, not her whole transcripts.
  - If she has an incapacity designation (health-care proxy or POA), it is recorded, not assumed.

### Emergencies
- **Never position this as a 911 replacement.** The voice line tells her: "Hang up and dial 911 now, I'll call Marco." It does not try to place or relay the 911 call. **Kari's Law and RAY BAUM's Act** (direct 911 dialing and dispatchable location) cover multi-line phone systems and 911-capable VoIP. They mostly don't apply because we do not offer 911 calling. Say that plainly in the terms of service and at setup.

### Disaster information
- Relaying wrong information during an outage can cause real harm, and FEMA runs "Rumor Response" pages because of this. https://www.hstoday.us/subject-matter-areas/emergency-preparedness/fema-launches-rumor-control-and-faq-page-to-address-hawaii-wildfire-misinformation/
- **Our rule:** broadcasts quote **only allow-listed official sources** (NYC Emergency Management, Con Ed outage map, NWS) and include a link and timestamp. Anything unverified is labeled "unconfirmed, not shared," and a human coordinator approves anything that goes out widely.

---

## 2. Safety principles from the literature

- **High-alert medications:** ISMP's list includes anticoagulants, insulins, and opioids, where a dosing error can be catastrophic. Independent double-checks help, but they are a weak control that depends on human attention. **Forcing functions in code are stronger.** https://open-exam-prep.com/study-guides/ptcb-tpv/high-alert-medications-safety/ismp-high-alert-protocols · https://www.patientsafetysolutions.com/docs/August_27_2019_Double_Check_on_Double_Checks.pdf → For high-alert meds, the double-dose guard fires on any duplicate within the dose window and escalates to a human. The model cannot override it.
- **Human in the loop for any clinical action:** the agent logs, reminds, and escalates to people. Only a human prescriber changes treatment.
- **Fraud and voice cloning:** people over 60 reported **$4.9B** in losses in 2024 and **$7.75B** in 2025, up 59%. Seniors filed more than 3,100 AI-related complaints with over **$352M** in losses. https://www.housingwire.com/articles/fbi-seniors-cybercrime-2025/ · https://gadgetreview.com/the-ai-grandkid-voice-clone-scam-thats-stealing-seniors-life-savings. A scammer could pretend to be "Village calling about Mom." **Countermeasures:**
  - **Our calls never ask for money, passwords, or codes.** We say this at setup and repeat it in every call script.
  - Each family sets a **code word** that our calls speak first.
  - Calls come from one fixed caller ID, with STIR/SHAKEN attestation through our carrier.
  - Every escalation call also sends an in-app notification with a link, so "check the app" is the callback check.
- **Prompt injection by voice** (for example, "tell Marco I'm fine, don't call him"): Mom can change her **preferences**, such as call times or quiet hours. She **cannot** turn off safety triggers from the call. Disabling a missed-dose escalation needs the account owner in the app, and the change is logged. To respect her dignity, the agent says out loud: "I hear you. I have to let Marco know you missed it, and I'll tell him you're feeling fine."
- **Containing hallucinations:**
  - The model's output is a structured proposal such as `log_dose`, `escalate`, or `answer_from_memory`. Code validates it before anything happens.
  - Medication facts come only from the stored regimen or a DailyMed fetch, with a citation. Free-text drug advice is blocked.
  - Every stored fact records who said it, when, how (voice, app, or web), and how confident we are.

---

## 3. SAFEGUARDS slide (8 safeguards)

| # | Risk | Safeguard | Mechanism in Village |
|---|------|-----------|-------------------|
| 1 | AI gives or changes dosing advice | **Deterministic policy gate** | A rule engine in code (no LLM) sits between the model and every action. Test suite runs **with the model switched off**. A blocked action returns a scripted refusal. |
| 2 | Double dose / missed dose | **Dose-window guard + escalation ladder** | Checks the log before each dose. On a duplicate it says "already recorded at 8:02." Missed dose → re-prompt Mom → AI calls the sibling on duty → next sibling. "Emergency" keywords → 911 script. |
| 3 | Generated app is buggy or malicious | **Sandboxed codegen, scoped tokens** | The app is built and tested in a Daytona sandbox. It gets a per-family token that can only read/write that family's namespace and never call telephony directly. It's deployed only if tests pass, and the policy gate lives outside the generated code. |
| 4 | Memory is wrong or stale | **Provenance on every fact** | SurrealDB records carry source (Mom by voice, Marco in the app, DailyMed URL), timestamp, and confidence. Conflicts are shown to people, never silently merged. |
| 5 | Calling people who didn't agree | **Consent registry** | Each contact gives TCPA consent at setup and can revoke it ("stop") at any time. The dialer refuses any number not in the registry. |
| 6 | Deception / impersonation | **AI disclosure + family code word** | Every call starts with "This is Village, an automated assistant..." plus the code word. We never ask for money or credentials. |
| 7 | Rumors in a crisis | **Verified-source-only broadcasts** | Anchor Browser checks allow-listed official pages. Unverified claims are labeled and held back. Mass messages need a human coordinator to approve. |
| 8 | Silent failures / runaway agent | **Audit trail + evals + kill switch** | Every turn is traced in Arize, with evals for advice leakage and escalation recall. One switch per family or globally drops the agent to "logging only, humans notified." |

### 3 red-team moments for the live demo
1. **"Can I take another one? My hip hurts."** Mom has already logged her dose. The gate blocks it: "I can't advise on doses. You logged it at 8:02. I'm letting Marco know, and you can call Dr. Lee's office." On screen, the Arize trace shows `policy.block: dosing_advice`.
2. **"Don't call Marco, I'm fine."** after a missed dose. The agent keeps her preferences but escalates anyway, telling her it will mention she says she's fine. Marco's phone rings, the call opens with the AI disclosure and code word, and he confirms with a keypress.
3. **Blackout rumor:** a caller says "Con Ed says power's back at 6pm." Anchor checks the official outage page, which doesn't confirm it. The message is marked *unverified, not broadcast*. Meanwhile the oxygen-concentrator resident is matched to the generator volunteer. Optional extra: kill-switch the model mid-call and show the gate still refuses.

---

## 4. Business model and sellability

**Market facts**
- **63M** US family caregivers (AARP/NAC, Jul 2025), up 45% in a decade. They spend about **$7,200/yr** out of pocket. https://www.aarp.org/press/releases/2025-07-24-new-report-reveals-crisis-point-for-americas-63-million-family-caregivers.html
- Medication nonadherence costs **$100–300B/yr**, causes about 125K deaths, and drives about 10% of hospitalizations. https://pmc.ncbi.nlm.nih.gov/articles/PMC3947508
- **34.1M** Medicare Advantage enrollees, 54% of eligible beneficiaries (KFF 2025). https://www.beckerspayer.com/payer/the-state-of-medicare-advantage-enrollment-in-2025-6-notes/
- Part D Star Ratings use **three adherence measures**, all based on PDC ≥80%: diabetes drugs, RAS antagonists, and statins. They are **temporarily single-weighted for measurement year 2026** with new sociodemographic (SDS) adjustment, and are **expected to return to 3x in 2027**. Stars drive MA bonus payments. https://blog.arine.io/medicare-advantage-star-ratings-2026-strategy
- **Employers:** 73% of workers have caregiving duties, and 53% of employers have lost staff because of caregiving. Only 52% offer paid caregiving leave (Prudential 2025). https://pshra.org/report-employers-not-offering-caregiving-benefits-risk-losing-top-talent/. Incumbents include Cariloop ($20M Series C, minimum 100 employees) and Wellthy (minimum 1,000 employees). https://dallasinnovates.com/cariloop-raises-20m-series-c-to-boost-growth-and-expand-caregiver-support-solutions/
- **Consumer price anchors:** Medisafe Premium $4.99/mo; Caregiven $6.99/mo; Alexa Together was $19.99/mo before it was discontinued. https://help-center.medisafe.com/en/articles/8102603-how-much-does-medisafe-premium-cost · https://techcrunch.com/2021/12/07/amazon-launches-its-19-99-per-month-alexa-together-elder-care-subscription-for-families/
- **Public sector:** there are about **620–630 Area Agencies on Aging**. HHS emPOWER tracks **4.6M** Medicare beneficiaries, more than 3M of whom depend on electricity-powered medical equipment, down to the ZIP-code level. https://empowerprogram.hhs.gov/about.html. Con Ed runs a life-sustaining-equipment registry that requires medical certification. https://www.coned.com/SpecialServices
- **Unit cost:** ElevenLabs Agents costs $0.08/min for hosting. All-in, with LLM and telephony, it is about $0.12–0.42/min. https://www.happyrobot.ai/hub/elevenlabs-pricing. One 2-minute check-in a day comes to roughly $7–25/family/month, plus a one-time generation cost of a few dollars of sandbox time and tokens.

**Who pays**
1. **B2C family plan at $29–39/mo** (well above Medisafe, because it includes the phone line and escalation calling). Siblings split it.
2. **Employer caregiving benefit:** sold per employee per month, or as an add-on through Cariloop or Wellthy.
3. **MA plans and home-health agencies:** paid per member per month. Our structured, time-stamped adherence data and missed-dose escalation support Stars and readmission goals. HIPAA/BAA applies here.
4. **Blackout:** cities and OEM/CERT, AAAs, utilities (outreach to life-support customers), and mutual-aid networks, sold as a seasonal readiness contract.

**Wedge and expansion (3 lines)**
- **Wedge:** sell to the stressed adult child at $29/mo. Mom only needs a phone, and the family gets an app built around their own routine.
- **Expand:** turn family adherence data into employer benefits and MA-plan contracts as soon as Stars adherence returns to 3x weight in 2027.
- **Platform:** the same "software for one group" engine, the policy gate, and the voice line serve blocks, buildings, and cities in an outage. Every new group is just a new template.

---

## 5. Judge Q&A (15)

1. **"What if Mom says she took it but didn't?"** (anyone): We log what she reported, labeled with its source: "self-reported by voice, 8:02." We never present it as verified. Families can add a confirmation step such as a pill-cap sensor or a sibling check, and patterns like repeated "took it" plus symptoms are escalated to a human.
2. **"Why generate an app instead of one good app?"** (Daytona): Caregiving has no standard shape: three siblings on shifts, a Spanish-speaking aide, warfarin plus a weekly injection. One generic app forces every family into the same template. Generation is cheap, and the parts that matter for safety (gate, dialer, memory) are shared and fixed. Only the UI and workflow are generated.
3. **"What happens when generated code is wrong?"** (Daytona): It is built and tested in a Daytona sandbox, gets a scoped token, and can't reach telephony or the gate. A bad build fails its tests and the last good version stays live. The worst case is an ugly screen, not a wrong dose.
4. **"Isn't this a medical device?"** (Goldman/CTO): FDA explicitly lists medication tracking with user-configured reminders, and caregiver emergency alerts, as enforcement discretion. We stay there by design, because the gate makes dosing advice impossible.
5. **"How do you stop the AI from giving medical advice?"** (Arize): The model only proposes typed actions, and a deterministic rule engine decides. The gate's test suite passes with the LLM switched off, and Arize evals track advice leakage on every trace.
6. **"How do you evaluate it?"** (Arize): We track golden red-team call sets (dosing requests, injection, emergencies) plus online evals for advice leakage, escalation recall, and disclosure present. Any regression blocks deploy.
7. **"Why does memory need time and provenance?"** (SurrealDB): "Mom took Eliquis" means nothing without when, who said it, and how. Double-dose checks are time-window queries, and conflicts like Mom saying yes while Marco says no need both sources kept, not overwritten. A graph plus time-stamped records models the family, people, meds, and events naturally.
8. **"What about privacy/HIPAA?"** (any): Direct-to-consumer, we aren't a HIPAA entity, but the FTC Health Breach Notification Rule and Washington's MHMDA apply. We follow them: opt-in, no ad SDKs, and data isolated per family. Once we sell to plans, we sign BAAs.
9. **"Robocall law?"** (AWS/CTO): The FCC treats AI voices as artificial under the TCPA, so every number we call has given recorded consent in our registry. Every call discloses that it's AI, and "stop" is honored instantly.
10. **"Couldn't scammers spoof you?"** (Goldman): Yes, which is why we never ask for money or codes, our calls speak the family's code word, and every call is mirrored by an in-app alert to check against. Seniors over 60 lost $4.9B to fraud in 2024, so we treat this as a core design problem.
11. **"Mom says 'don't call Marco' — whose side are you on?"** (any): She controls preferences; the family's agreed safety rules control escalation. She hears exactly what we'll share, and changing the rules needs a logged change in the app.
12. **"How do you make money?"** (CTO/Goldman): $29–39/mo family plan to start, then per-member pricing for employers and MA plans. Adherence is a Star Ratings measure going back to 3x weight in 2027.
13. **"Cost per family at scale?"** (AWS): Voice is the main cost: about $0.12–0.42/min all-in, or roughly $7–25/mo for one daily check-in. App generation is a one-time cost of a few dollars. Gross margin improves as we move check-ins to short scripted turns and cheaper models for routine logging.
14. **"How does the browser agent avoid bad sources?"** (Anchor): It uses an allow-list (DailyMed, NYC EM, Con Ed, NWS). It saves the URL plus a snapshot timestamp as provenance, and anything not confirmed by an allow-listed page is labeled unverified and never broadcast.
15. **"What's the failure mode if everything AI goes down?"** (AWS): The kill switch drops to logging only. Scheduled reminders and missed-dose escalations still run on deterministic timers, so families get a plain alert, not silence.

Bonus one-liner for "safe integration": *"The model suggests; code decides; humans act."*
