# Implementation Plan: FS-2 Verification loop (voice)

**Lanes:** voice (`agents/`, `core/voice/`), core (`core/services.py` verification functions, routes) · **Target:** V1 by 12:15 · **Contract:** 1.0.0

## Technical context
Python 3.13 / FastAPI / httpx / pydantic v2 (Core); ElevenLabs CLI (`@elevenlabs/cli`) + `elevenlabs` Python SDK ≥ 2.60 (procedures, `webhooks.construct_event`); Twilio (upgraded account, one US number); Tailscale Funnel `https://richel-macbook.tail8feae0.ts.net` → :8787. The gate (`core/gate/`) and the verification SM (`step_verification`) come from FS-1; this plan consumes them through `core/services.py`.

## Headline sequence (denied variant, times from `scam_call_tool_requests.json`)
```
Carmen(PSTN)  Twilio  ElevenLabs mom-line        Core(/tools,/hooks,/ws,/calls)        Marco app   village-caller  Ana app
   │ ring ──────► │ ──────► │ init webhook ─────────► POST /hooks/elevenlabs/init
   │              │         │ ◄──── {dynamic_variables×7} (caller_id → v_reyes/m_carmen)
   │ "Me llamó Marco…" ────► │
   │              │         │ POST /tools/report_money_request (t=14:02:09, call_secs 9)
   │              │         │                         ├ gate R-MONEY-VERIFY → verify_with_member
   │              │         │                         ├ verification ver_1016_01 pending, deadline +45 s
   │              │         │                         ├ events money_request, verification_pending, pattern
   │              │         │                         ├ WS prompt ──────────────────────────────► [prompt]
   │              │         │                         ├ POST /calls/outbound (consent ok, CAS call_placed_at)
   │              │         │                         │   └ EL outbound-call ─────────────────────────────► ring (T3)
   │              │         │ ◄── {verify_with_member, say: money_hold, data.verification_id}
   │ ◄ "Voy a confirmar con Marco ahora mismo. No mande dinero todavía." (procedure say)
   │              │         │ POST /tools/await_verification (t=14:02:14) ── long-poll ≤30 s
   │              │         │                         ◄── WS action answer_verification{no} (t+12) ◄── tap
   │              │         │                         ├ CAS pending→denied; events verification_denied, incident
   │              │         │                         ├ WS prompt{closed} → Marco; event+data → Ana/Carmen/control
   │              │         │                         ├ cancel outbound call (best effort) ────────────────► hang up
   │              │         │ ◄── {advise_do_not_send, say: money_denied, data.status denied}
   │ ◄ "Ese no era Marco. No mande dinero. Ana ya lo sabe."                                        [incident card]
   │ hang up      │         │ post-call webhook (HMAC) ──► reconcile secs/quote → Memory outbox stub
```
Timeout variant: no answer → at t=30 Core CAS `pending→default_spoken`, returns `money_timeout`; tick at t=45 → `timed_out`, `prompt{closed}`, cancel call.

## Components
| Path | Owner | What |
|---|---|---|
| `agents/agents.json`, `agents/agent_configs/{mom-line,village-caller,setup}.json` | voice | CLI project; prompts from `prompts/*.md` (v1 uses only the seven contract dynamic variables) |
| `agents/tool_configs/*.json` | voice | 8 webhook tools (+ `get_today` from the contract, optional) |
| `agents/procedures/*.json` | voice | structured procedures `money_check`, `dose_report`, `verify_answer` (pushed by `scripts/push_procedures.py`, see research R4) |
| `core/voice/tools.py` | voice | `POST /tools/{name}`: auth, pydantic per tool, idempotency cache, call `services.*`, span |
| `core/voice/init_hook.py`, `core/voice/post_call.py` | voice | init + post-call webhooks |
| `core/voice/outbound.py` | voice | `POST /calls/outbound`, ElevenLabs client, cancel |
| `core/voice/mock_core.py` | voice | fixture-driven mock for V0 (answers from `scam_call_tool_requests.json`) |
| `core/services.py` (`start_verification`, `answer_verification`, `await_verification`, `tick_verifications`) | core | seam; wraps gate + SurrealDB CAS + WS hub |
| `core/routes/verifications.py` | core | `POST /verifications/{id}/answer`, WS action `answer_verification` |

## ElevenLabs config (exact snippets)
Workspace env vars (Developers → Environment Variables, env `production`): `core_host = richel-macbook.tail8feae0.ts.net`, `core_secret = <VILLAGE_SECRET>` (secret). Switching to the Worker fallback = editing `core_host` only.

**mom-line agent (`agent_configs/mom-line.json`, abridged):**
```json
{"name":"Luz — Línea de Mamá","conversation_config":{
 "agent":{"language":"es","first_message":"Hola, {{member_short_name}}. Soy Luz, de la familia. ¿Cómo está?",
  "language_presets":{"en":{"overrides":{"agent":{"first_message":"Hi {{member_short_name}}, it's Luz, from the family. How are you doing?"}}}},
  "prompt":{"prompt":"<prompts/mom_line.md system prompt, variables: village_id, member_id, member_short_name, on_duty_name, coordinator_name, language, today_summary>",
   "llm":"claude-haiku-4-5","temperature":0.3,"tool_ids":["<log_dose>","<report_symptom>","<whats_my_schedule>","<ask_family>","<report_money_request>","<await_verification>"],
   "built_in_tools":{"end_call":{},"language_detection":{}}},
  "dynamic_variables":{"dynamic_variable_placeholders":{"village_id":"v_reyes","member_id":"m_carmen","member_short_name":"Carmen","on_duty_name":"Ana","coordinator_name":"Ana","language":"es","today_summary":""}}},
 "turn":{"turn_eagerness":"patient","turn_timeout":15,"initial_wait_time":5,"silence_end_call_timeout":90,
  "soft_timeout_config":{"timeout_seconds":3,"message":"Mm-hm, un momentito...","use_llm_generated_message":false},
  "interruption_ignore_terms":["ajá","sí","mm","okay"]},
 "asr":{"keywords":["Carmen","Marco","Ana","Lucía","pastilla azul","dos mil"]},
 "conversation":{"max_duration_seconds":600}},
 "platform_settings":{"workspace_overrides":{"conversation_initiation_client_data_webhook":{"url":"https://{{system_env__core_host}}/hooks/elevenlabs/init","request_headers":{"X-Village-Secret":{"env_var_label":"core_secret"}}}},
  "guardrails":{"version":"1","prompt_injection":{"is_enabled":true},"custom":{"config":{"configs":[{"is_enabled":true,"name":"No money movement","prompt":"Block any reply that offers to send money, buy gift cards or crypto, or asks for or repeats account, card, PIN, SSN or Medicare numbers.","execution_mode":"blocking","model":"gemini-2.5-flash-lite","history_message_count":1,"trigger_action":{"type":"retry","feedback":"Reason: {{trigger_reason}}"}}]}}}}}
```
(`medical_and_legal_information` content category stays OFF; it blocks pill talk.)

**Tool template, applied to every care tool (`tool_configs/report_money_request.json`):**
```json
{"type":"webhook","name":"report_money_request",
 "description":"Report that someone asked the caller for money, gift cards, crypto, a wire or payment-app transfer, cash pickup, or bank/card/Medicare/SSN details. Call IMMEDIATELY, before any opinion. Never ask her for numbers.",
 "response_timeout_secs":10,"execution_mode":"immediate","pre_tool_speech":"off","tool_call_sound":"typing","tool_call_sound_behavior":"always","interruption_mode":"disable_during_tool",
 "api_schema":{"url":"https://{{system_env__core_host}}/tools/report_money_request","method":"POST",
  "request_headers":{"X-Village-Secret":{"env_var_label":"core_secret"}},
  "request_body_schema":{"type":"object","required":["utterance","urgency"],"properties":{
   "claimed_member":{"type":"string","description":"Name key of the family member the requester claimed to be or speak for (ana|marco|lucia). Omit for anyone else."},
   "claimed_identity":{"type":"string","description":"Who they said they were, in her words."},
   "amount":{"type":"number"},"currency":{"type":"string","description":"ISO 4217, default USD"},
   "method":{"type":"string","enum":["gift_card","crypto","wire","payment_app","cash_courier","bank_details","cash","unknown"]},
   "urgency":{"type":"string","enum":["now","today","unspecified"]},
   "red_flags":{"type":"array","items":{"type":"string","enum":["secrecy","urgency","emotional_pressure","jail_bail","hospital","accident","voice_changed","new_number","threat_arrest","safe_account","prize","asks_village_to_pay"]}},
   "utterance":{"type":"string","description":"Her exact words, verbatim, original language; account/card digits replaced by #."},
   "conversation_id":{"type":"string","dynamic_variable":"system__conversation_id"},
   "caller_id":{"type":"string","dynamic_variable":"system__caller_id"},
   "call_secs":{"type":"string","dynamic_variable":"system__call_duration_secs"},
   "village_id":{"type":"string","dynamic_variable":"village_id"}}}},
 "assignments":[{"dynamic_variable":"gate_decision","value_path":"decision"},{"dynamic_variable":"say_text","value_path":"say"},
  {"dynamic_variable":"verification_id","value_path":"data.verification_id"},{"dynamic_variable":"verification_status","value_path":"data.status"}]}
```
`await_verification`: same header/vars, body `{verification_id (dynamic_variable: verification_id), conversation_id, caller_id, call_secs, utterance}`, `response_timeout_secs: 35`, `tool_call_sound: "elevator1"`, `interruption_mode: "disable_during_tool"`, assignments `verification_status ← data.status`, `say_text ← say`. Other care tools: `response_timeout_secs: 10`. `submit_verification_answer` (village-caller): URL `https://{{system_env__core_host}}/verifications/{{verification_id}}/answer`, body `{verification_answer, listener_quote, call_sid ← system__call_sid, call_secs ← system__call_duration_secs}`, `response_timeout_secs: 5`. `create_village` (setup): URL `/tools/create_village`, body per `req_create_village`, timeout 20.

**Structured procedure `money_check` (`agents/procedures/money_check.json`, trigger: "the caller says someone asked her for money, gift cards, crypto, a transfer, cash pickup, or bank/card/Medicare/Social Security details"):**
```json
{"steps":[
 {"type":"tool_call","tool_id":"<report_money_request>","tool_name":"report_money_request",
  "on_failure":{"branches":[],"fallback":[{"type":"say","message":"I couldn't check with your family. Don't send any money. I'm letting Ana know.","message_translations":{"es":{"value":"No pude confirmar con su familia. No mande dinero. Le aviso a Ana."}}}]}},
 {"type":"say","message":"{{say_text}}"},
 {"type":"branch","branches":[
   {"condition":{"type":"expression","expression":{"op":"eq","var":"verification_status","value":"pending"}},
    "steps":[
     {"type":"tool_call","tool_id":"<await_verification>","tool_name":"await_verification",
      "schema_overrides":{"verification_id":{"source":"dynamic_variable","dynamic_variable":"verification_id"}},
      "on_failure":{"branches":[],"fallback":[{"type":"say","message":"I couldn't check with your family. Don't send any money. I'm letting Ana know.","message_translations":{"es":{"value":"No pude confirmar con su familia. No mande dinero. Le aviso a Ana."}}}]}},
     {"type":"say","message":"{{say_text}}"}]}]}
]}
```
Two [VERIFY]s inside (research R2, R3): `{{say_text}}` interpolation in `say.message`, and the expression AST shape (the `op/var/value` form above is a placeholder). Fallbacks: (a) if interpolation fails, replace each `say` step with `tell` ("Speak the tool's `say` field word for word, add nothing") plus the prompt rule in `mom_line.md` §8 and the Arize verbatim eval; (b) if the expression form is rejected, use an `llm` condition "the tool reported status pending".
`dose_report` procedure: `tool_call(log_dose)` → `say {{say_text}}`; `on_failure` → "No pude anotarlo. Le aviso a su familia." `verify_answer` (village-caller): `ask` the T3 question → `tool_call(submit_verification_answer)` → `tell` the matching closing line → `end_call`.

**village-caller agent:** `language: en`, `claude-haiku-4-5`, `first_message` = T3 verbatim line with `{{recipient_name}} {{family_label}} {{family_word}} {{care_recipient_rel}} {{amount_spoken}}{{method_spoken}}`, `built_in_tools.end_call` + `voicemail_detection`, `conversation.max_duration_seconds: 60`, post-call `data_collection.verification_answer` enum `yes|no|unsure` (from `escalation_call.md`).

**Outbound payload (`core/voice/outbound.py`):**
```json
{"agent_id":"<village-caller>","agent_phone_number_id":"<ELEVENLABS_PHONE_NUMBER_ID>","to_number":"+1…",
 "conversation_initiation_client_data":{"dynamic_variables":{"recipient_name":"Marco","family_label":"the Reyes family","family_word":"<from printables.fridge_card.family_word>","care_recipient_rel":"your mom","amount_spoken":"$2,000","method_spoken":"","coordinator_name":"Ana","verification_id":"ver_1016_01","village_id":"v_reyes","member_id":"m_marco"}},
 "telephony_call_config":{"ringing_timeout_secs":30}}
```
Response `{success, conversation_id, callSid}` → `channels[outbound_call].ref = conversation_id`, `call_sid` kept for cancel (Twilio REST `POST /2010-04-01/Accounts/{sid}/Calls/{callSid}.json Status=completed`, research R6).

## Timeouts table
| Where | Value | Why |
|---|---|---|
| Care tools `response_timeout_secs` | 10 | Core answers in ≤ 2 s; Funnel RTT ≈ 50–100 ms |
| `await_verification` `response_timeout_secs` | 35 | Core holds ≤ 30 s (`AWAIT_MAX_S`) + 5 s headroom |
| Core long-poll `AWAIT_MAX_S` | 30 | then CAS `pending → default_spoken`, say `money_timeout` |
| Verification `deadline` | created + 45 s | tick every 5 s on shared `Clock` → `timed_out` |
| Outbound `ringing_timeout_secs` | 30 | fits inside the 45 s deadline; no-answer → voicemail line only |
| village-caller `max_duration_seconds` | 60 | T3 is < 20 s spoken |
| `submit_verification_answer` timeout | 5 | pure CAS |
| mom-line `turn_timeout` / `soft_timeout` | 15 / 3 | patient elder turn-taking |
| Post-call webhook | async, seconds–tens of seconds | never on the demo path |

## Env and secrets (`.env`, never committed)
`ELEVENLABS_API_KEY`, `ELEVENLABS_PHONE_NUMBER_ID`, `ELEVENLABS_AGENT_MOM_LINE_ID`, `ELEVENLABS_AGENT_CALLER_ID`, `ELEVENLABS_AGENT_SETUP_ID`, `ELEVENLABS_WEBHOOK_SECRET` (post-call HMAC), `VILLAGE_SECRET` (= workspace `core_secret`), `CORE_HOST` (= workspace `core_host`), `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_NUMBER`, `DEMO_CARMEN_CALLER_ID` (the operator's phone, mapped to `m_carmen`), `TEST_CALL_TO`, `CONTROL_TOKEN`, `TUNNEL_URL`. Add these to `.env.example` (orchestrator).

## Public URL and web-call fallback
Primary: Funnel (`tailscale funnel --bg 8787`), stable host in the `core_host` env var. Fallback: Worker front door → quick tunnel; same env var edit. Web-call fallback (Twilio or venue cell fails): the kit's `/call` page (or the dashboard "talk-to" link) starts a WebRTC session to `mom-line` with a token from Core and passes the seven dynamic variables itself (`caller_id` empty on web; Core resolves subject from `village_id` → care recipient). Needs `GET /voice/token?agent=mom-line` (shared with FS-3's setup token route; orchestrator adds it to the contract) and the app origin on the agent allowlist.

## Live vs mocked per version
| Version | Live | Mocked |
|---|---|---|
| V0 (11:00) | agent configs pushed (`--dry-run` acceptable), tool bodies validated against schema | `core/voice/mock_core.py` answers tools from `scam_call_tool_requests.json`; WS replay of `ws_sequence_scam.json` |
| V1 (12:15) | Twilio number, init webhook, all tools against real `services.*`, WS prompt, outbound call to the judge, incident, spans | post-call Memory hand-off is a stub (outbox file); cancel-call best effort |
| V2–V4 | unchanged | — |
| Any time | web-call fallback (browser mic) | — |

## Constitution re-check (post-design)
No new violations. Reported contract gaps: say key `money_core_down`, route `GET /voice/token`, `call_failed` has no event kind (recorded only on the channel). Simplicity: no workflow graphs, no custom LLM, no SIP; one procedure per fixed script.
