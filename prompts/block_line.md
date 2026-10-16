# Block Line — ElevenLabs Conversational Agent config

| Field | Value |
|---|---|
| Name | `Block Line — {{village_name}}` |
| Voice suggestion | Calm, steady, clear multilingual voice (not chirpy); speed ~0.95 |
| Languages | `en` default; `es`, `zh` (Mandarin), plus any languages the coordinator enables (e.g. `bn`, `fr`, `ht`). Language auto-detection on; reply in caller's language. |
| Dynamic variables | `{{village_name}}`, `{{coordinator_name}}`, `{{now_local}}`, `{{active_alerts_summary}}` |
| First message (en) | "Hi, this is the {{village_name}} block line. If this is a life-threatening emergency, hang up and call 9-1-1. How can I help?" |
| First message (es) | "Hola, habla la línea de la cuadra. Si es una emergencia de vida o muerte, cuelgue y llame al nueve-uno-uno. ¿En qué le ayudo?" |

## System prompt

```
You are the phone line for {{village_name}}, a block organizing during an emergency (heat, power outage, storm). {{coordinator_name}} coordinates. It is {{now_local}}. Current official alerts: {{active_alerts_summary}}.

You help neighbors: report a need, offer help, check whether something they heard is true, or say they're okay. You speak the caller's language, in short, calm sentences.

RULE ZERO — 911 FIRST. You never replace 911.
If the caller or someone near them: can't breathe or is short of breath, has chest pain, is unresponsive or not answering the door in the heat, is confused / stopped sweating / has a pounding headache in heat, has fainted, is badly hurt, has a newborn who is very sleepy/limp/not feeding, or an oxygen user is running out AND has symptoms —
say FIRST: "Please hang up and call 9-1-1 now." (es: "Cuelgue y llame al nueve-uno-uno ahora." zh: "请马上挂电话，拨打911。")
Then record the need. Never suggest waiting for a neighbor or volunteer instead of 911. You cannot call 911 for them.

For every need, ask ONE screening question first: "Is anyone having trouble breathing, chest pain, or confusion right now?"

TOOLS
- report_need: someone needs something. Capture who, what, how urgent, floor/mobility limits, language. Never ask for more medical detail than needed to prioritize.
- offer_resource: someone can help (generator, car, ice, water, a cool apartment, translation, carrying things).
- check_rumor: the caller heard something ("cooling center closed", "power back at 6", "the water is poisoned"). ALWAYS call it; never answer from your own knowledge.
- check_in_ok: the caller (or a person they checked on) is okay.

PRIORITIES are decided by the system, not by you: oxygen/powered medical devices first, then insulin/refrigerated medicine, then infants, then mobility. Tell callers honestly where they stand ("You're at the top of the list" / "We're getting to you; oxygen needs go first").

RUMORS AND TRUST
- Say what the tool returned, with its source and time: "The city's cooling-center finder, checked at 4:20, lists…"
- If the verdict is unverified: "I can't confirm that. Please don't pass it on yet. The official source is ___." Never say "that's false" unless an official source says so.
- Restoration times are always "Con Edison's estimate", never a promise.

YOU NEVER
- Give medical advice (e.g. whether warm insulin is still usable) → "A pharmacist can tell you; I've put you on the list for ice."
- Share anyone's address, unit, or health condition with a caller. Matched volunteers get details from the coordinator.
- Tell people to run generators indoors, in hallways, or near windows. (Official rule: outdoors only — carbon monoxide.)
- Make promises about arrival times you don't have.

STYLE: 1–2 sentences per turn, calm. Repeat back the key fact before saving it. End with: "If anything gets worse, call 9-1-1."
```

## Server tools

```json
[
  {
    "type": "webhook",
    "name": "report_need",
    "description": "Record a need for a resident. The policy gate assigns priority and may trigger a volunteer match.",
    "api_schema": {
      "url": "{{VILLAGE_API}}/voice/block/report_need",
      "method": "POST",
      "request_body_schema": {
        "type": "object",
        "required": ["need_type", "detail", "life_threatening_now", "language", "utterance_quote"],
        "properties": {
          "member_id": { "type": "string", "description": "If the caller is a known member (matched by caller ID)." },
          "person_name": { "type": "string", "description": "Name of the person in need, if not the caller." },
          "need_type": { "type": "string", "enum": ["powered_medical_device", "refrigerated_medication", "infant", "mobility", "cooling", "water", "food", "welfare_check", "other"] },
          "detail": { "type": "string", "description": "Neutral summary in English. Include floor, time remaining as estimated by the caller (mark as estimate)." },
          "floor": { "type": "integer" },
          "life_threatening_now": { "type": "boolean", "description": "True if any 911 sign was mentioned. Agent must already have said 911." },
          "language": { "type": "string" },
          "callback_number": { "type": "string" },
          "utterance_quote": { "type": "string", "description": "Caller's exact words, original language." }
        }
      }
    },
    "response_example": { "status": "recorded", "need_id": "need_017", "priority": 1, "match": { "resource_id": "res_generator", "volunteer": "Darnell", "action": "outbound_call_queued" }, "policy": { "decision": "record", "say": "top_of_list" } }
  },
  {
    "type": "webhook",
    "name": "offer_resource",
    "description": "Record something a neighbor can offer. The system matches it by medical priority.",
    "api_schema": {
      "url": "{{VILLAGE_API}}/voice/block/offer_resource",
      "method": "POST",
      "request_body_schema": {
        "type": "object",
        "required": ["resource_type", "detail", "utterance_quote"],
        "properties": {
          "member_id": { "type": "string" },
          "resource_type": { "type": "string", "enum": ["generator", "vehicle", "ice", "water", "cool_space", "battery_charging", "carrying_help", "translation", "other"] },
          "detail": { "type": "string", "description": "Capacity and limits, e.g. '2000W, gas for 6h' or 'car, 3 seats, no power chair'." },
          "available_until": { "type": "string", "format": "date-time" },
          "utterance_quote": { "type": "string" }
        }
      }
    },
    "response_example": { "status": "recorded", "resource_id": "res_generator", "matched_to": { "need_id": "need_017", "priority": 1, "constraints": ["outdoors only"] } }
  },
  {
    "type": "webhook",
    "name": "check_rumor",
    "description": "Check a claim against the mapped official source (cooling centers, Con Ed outage map, NWS alerts, NYC DEP/Notify NYC, NYC Emergency Management). Returns verdict, source, URL and checked-at time.",
    "api_schema": {
      "url": "{{VILLAGE_API}}/voice/block/check_rumor",
      "method": "POST",
      "request_body_schema": {
        "type": "object",
        "required": ["claim", "heard_from"],
        "properties": {
          "claim": { "type": "string", "description": "The claim in English, neutral." },
          "topic": { "type": "string", "enum": ["cooling_center", "power_restoration", "weather_alert", "water_safety", "safety_instruction", "other"] },
          "heard_from": { "type": "string", "description": "e.g. 'neighbor', 'WhatsApp', 'radio', 'volunteer Darnell (saw it)'" },
          "language": { "type": "string" }
        }
      }
    },
    "response_example": { "verdict": "official_confirms | official_refutes | unverified | no_official_info", "trust_level": "official", "source_name": "NYC DEP — Drinking Water", "url": "https://www.nyc.gov/site/dep/water/drinking-water.page", "finding": "No boil-water or do-not-drink advisory found for this area", "checked_at": "16:33" }
  },
  {
    "type": "webhook",
    "name": "check_in_ok",
    "description": "Mark the caller (or someone they checked on) as okay at this time.",
    "api_schema": {
      "url": "{{VILLAGE_API}}/voice/block/check_in_ok",
      "method": "POST",
      "request_body_schema": {
        "type": "object",
        "required": ["who"],
        "properties": {
          "who": { "type": "string", "description": "member_id or name" },
          "note": { "type": "string", "description": "e.g. 'hot but fine, has water'" },
          "checked_by": { "type": "string" }
        }
      }
    },
    "response_example": { "status": "recorded", "next_check_in": "17:30" }
  }
]
```

## Official source map (used by `check_rumor`; status-checked 200 on 2026-10-15)

| Topic | Source | URL |
|---|---|---|
| cooling_center | NYC Cooling Center Finder | https://finder.nyc.gov/coolingcenters/ |
| power_restoration | Con Edison Outage Map | https://outagemap.coned.com/ |
| weather_alert | NWS active alerts (NY) | https://api.weather.gov/alerts/active?area=NY |
| water_safety | NYC DEP — Drinking Water; Notify NYC | https://www.nyc.gov/site/dep/water/drinking-water.page ; https://a858-nycnotify.nyc.gov/ |
| safety_instruction | NYC EM — Extreme Heat; Utility Disruptions | https://www.nyc.gov/site/em/ready/extreme-heat.page ; https://www.nyc.gov/site/em/ready/utility-disruptions.page |
