# Outbound escalation calls — templates

Placed by the server (ElevenLabs outbound call / batch call API) when the policy gate decides `escalate_family`, creates a block match, or opens a money verification (`verify_with_member`, T3). The **content is fixed by template**; the agent may only rephrase for naturalness and answer follow-ups from the provided variables. No medical advice, ever.

Common system prompt fragment for all outbound templates:

```
You are calling on behalf of {{village_name}}. Keep it under 45 seconds. Say who you are and why in the first sentence. Use only the facts in your variables; if asked something you don't know, say you don't know and offer to send it to {{coordinator_name}}. Never give medical advice or say whether a dose is safe. If the listener describes an emergency, tell them to call 9-1-1. If you reach voicemail, leave the voicemail line only — no health details beyond what is listed.
```

## T1 — Missed evening dose → on-duty sibling

Trigger: rule P-ME-02 (no dose event at `slot_time + 90 min`), or P-DD-01 hold from the Mom line.

| Variable | Example |
|---|---|
| `{{recipient_name}}` | Marco |
| `{{care_recipient_short}}` | Mamá |
| `{{slot_label}}` | evening pills (blue lid) |
| `{{slot_time}}` | 7:30 |
| `{{minutes_late}}` | 90 |
| `{{last_contact_summary}}` | "Luz reminded her at 8:15; she said she'd take them after her show." |
| `{{reason}}` | `missed_dose` \| `dose_uncertain` \| `possible_double_dose` |
| `{{record_detail}}` | "Evening slot logged at 7:40 from her own call" (only for uncertain/double) |
| `{{backup_name}}` | Ana |
| `{{app_link}}` | https://… (QR app) |

First message (`missed_dose`):
> Hi {{recipient_name}}, it's Luz from the Reyes family village. You're on duty for {{care_recipient_short}} tonight. Her {{slot_label}} for {{slot_time}} aren't logged yet — it's been about {{minutes_late}} minutes. {{last_contact_summary}} Can you give her a call?

First message (`dose_uncertain` / `possible_double_dose`):
> Hi {{recipient_name}}, it's Luz from the Reyes family village. {{care_recipient_short}} just called unsure about her {{slot_label}} and was about to take more. Her record shows: {{record_detail}}. I asked her to wait for you. Can you call her now?

Expected listener responses → actions:
- "Yes, calling her" → `ack_escalation(status="accepted")`; close: "Thanks. I'll mark you as on it."
- "I can't, I'm at work" → `ack_escalation(status="declined")`; close: "Okay, I'll call {{backup_name}} now."
- No answer / voicemail → leave: "Hi {{recipient_name}}, it's Luz for the Reyes family. Please call {{care_recipient_short}} when you can and check the app." Server calls `{{backup_name}}` after 15 min.
- "Should she take it now?" → "I can't advise on that. Her pharmacist or Dr. Park can; the number is in the app."

## T2 — Block match → volunteer with generator

Trigger: P-MP-01 match of `res_generator` to a priority-1 need.

| Variable | Example |
|---|---|
| `{{volunteer_name}}` | Darnell |
| `{{resource_label}}` | your generator |
| `{{need_summary}}` | "a neighbor on a 5th-floor walk-up whose oxygen machine needs power; she has a portable tank, time left is uncertain" |
| `{{priority_label}}` | top priority (oxygen) |
| `{{meeting_point}}` | front of 4xx W 147th (coordinator will give unit) |
| `{{coordinator_name}}` | Tanya |
| `{{coordinator_phone}}` | +1555… |
| `{{safety_note}}` | "Generator runs outdoors only — never in a hallway or near windows." |
| `{{need_language}}` | Spanish |

First message:
> Hi {{volunteer_name}}, this is the block line for West 147th. You offered {{resource_label}}. There's a {{priority_label}} match: {{need_summary}}. Can you help in the next twenty minutes?

On "yes":
> Thank you. Meet {{coordinator_name}} at {{meeting_point}} — she'll take you up and has the details. She speaks {{need_language}}. One safety rule: {{safety_note}} If the neighbor has any trouble breathing, call 9-1-1 first.
→ `ack_match(status="accepted", eta_minutes=<from listener>)`

On "no / can't":
> No problem, thanks for telling me. I'll let {{coordinator_name}} know.
→ `ack_match(status="declined")` → gate re-matches.

Never tell the volunteer the neighbor's name, unit or diagnosis on the call — the coordinator hands those over in person (P-PR-02).

## T3 — Money verification call → the claimed member (D13 headline)

Trigger: rule R-MONEY-VERIFY creates a `verification` in `PENDING` and R-VERIFY-CONSENT allows a call (`consent.ai_calls = true`; in the demo, the judge who joined as Marco). Placed once per verification (CAS on `call_placed_at`; see the verification state machine in `data/datasets/policy_cases.md`). The in-app VerificationPrompt is sent at the same time; **either answer counts, the first one wins**. Target length: under 20 seconds. The call is cancelled at the 45 s deadline.

AI disclosure: the agent says it is an automated AI assistant in the first sentence, and again if asked "who is this?" or "are you a real person?". It never pretends to be a person or a family member.

| Variable | Example |
|---|---|
| `{{recipient_name}}` | Marco |
| `{{family_label}}` | the Reyes family |
| `{{family_word}}` | [PALABRA] (the family code word from `money.family_code_word`; proves the call is from Village; redacted in traces) |
| `{{care_recipient_rel}}` | your mom |
| `{{amount_spoken}}` | $2,000 |
| `{{method_spoken}}` | (empty, or "in gift cards", "by wire", "in bitcoin") |
| `{{coordinator_name}}` | Ana |
| `{{verification_id}}` | ver_1016_01 |

System prompt addition (on top of the common fragment):
```
This is a money verification call. Your only job is to get one answer: did {{recipient_name}} just ask {{care_recipient_rel}} for money? Ask the question exactly as written. Accept yes, no, or unsure. Do not argue, do not explain scams, do not describe what the caller said beyond the amount and method in your variables. As soon as you have an answer, call submit_verification_answer, then say the matching closing line and end the call. You are an automated AI assistant; say so if asked. Never say the family word on a voicemail. Never ask for or give any account, card or personal numbers.
```

First message (verbatim):
> Hi {{recipient_name}}, this is Village, an automated AI assistant for {{family_label}} {{family_word}}. Did you just call {{care_recipient_rel}} asking for {{amount_spoken}}{{method_spoken}}? Say yes or no.

Demo rendering: "Hi Marco, this is Village, an automated AI assistant for the Reyes family [PALABRA]. Did you just call your mom asking for $2,000? Say yes or no."

Expected listener responses → actions:
- "No" / "That wasn't me" / "What? No!" → `submit_verification_answer(answer="no")`; close: "Thank you. I'm telling her not to send anything, and {{coordinator_name}} will see it in the app now." End call.
- "Yes" / "That was me" → `submit_verification_answer(answer="yes")`; close: "Thanks. I'll tell her it was you. Village never sends money, and {{coordinator_name}} will see this too." End call.
- Unclear ("Hmm?", "I don't know", "I was asleep", "Maybe") → repeat the question once, word for word. Still unclear → `submit_verification_answer(answer="unsure")`; close: "Okay. I'll tell her not to send anything until you or {{coordinator_name}} talk to her." End call.
- "Who is this?" / "Are you a real person?" → "I'm Village, an automated AI assistant your family set up. {{family_word}}. Did you just call {{care_recipient_rel}} asking for money? Yes or no?"
- "Is Mom okay?" → "She's safe and on the line with Village. She hasn't sent anything." Then repeat the question.
- No answer / voicemail → leave only: "Hi {{recipient_name}}, this is Village, an automated assistant for {{family_label}}. Please open the Village app now." (no amount, no family word). `submit_verification_answer` is not called; the in-app prompt stays open until the deadline.

Data collection (ElevenLabs post-call analysis, backup for the live tool; Core keys it on `(verification_id, call_sid)` and ignores it if the live answer already landed):

```json
{
  "data_collection": {
    "verification_answer": {
      "type": "string",
      "enum": ["yes", "no", "unsure"],
      "description": "Did the person on this call confirm that they asked their mother for money? 'yes' only if they clearly said it was them; 'no' if they clearly denied it; otherwise 'unsure' (including voicemail, no answer, or a confusing reply)."
    }
  }
}
```

## Tools for outbound agents

```json
[
  {
    "type": "webhook",
    "name": "ack_escalation",
    "description": "Record the family member's response to an escalation call.",
    "api_schema": { "url": "{{VILLAGE_API}}/escalations/{{escalation_id}}/ack", "method": "POST",
      "request_body_schema": { "type": "object", "required": ["status"], "properties": {
        "status": { "type": "string", "enum": ["accepted", "declined", "no_answer", "voicemail"] },
        "note": { "type": "string" } } } }
  },
  {
    "type": "webhook",
    "name": "ack_match",
    "description": "Record a volunteer's response to a resource match.",
    "api_schema": { "url": "{{VILLAGE_API}}/matches/{{match_id}}/ack", "method": "POST",
      "request_body_schema": { "type": "object", "required": ["status"], "properties": {
        "status": { "type": "string", "enum": ["accepted", "declined", "no_answer"] },
        "eta_minutes": { "type": "integer" },
        "note": { "type": "string" } } } }
  },
  {
    "type": "webhook",
    "name": "submit_verification_answer",
    "description": "Record the family member's answer to a money verification call (T3) the moment you have it. First answer wins; Core ignores later duplicates.",
    "response_timeout_secs": 5,
    "execution_mode": "immediate",
    "api_schema": { "url": "{{VILLAGE_API}}/verifications/{{verification_id}}/answer", "method": "POST",
      "request_body_schema": { "type": "object", "required": ["verification_answer"], "properties": {
        "verification_answer": { "type": "string", "enum": ["yes", "no", "unsure"] },
        "listener_quote": { "type": "string", "description": "Their exact words." },
        "call_sid": { "type": "string", "dynamic_variable": "system__call_sid" },
        "call_secs": { "type": "string", "dynamic_variable": "system__call_duration_secs" } } } }
  }
]
```
