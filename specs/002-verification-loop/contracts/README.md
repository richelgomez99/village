# FS-2 contracts in use (all defined in `/contracts`, v1.0.0; nothing here is new)

Exact bodies. Auth: `X-Village-Secret` on tools, init and the village-caller answer; `ElevenLabs-Signature` on post-call; member token on app answers; control token on `/calls/outbound`.

## 1. Tool webhooks `POST /tools/{name}` (`voice_tools.schema.json#/$defs/req_<name>`)
Request (report_money_request, from the fixture):
```json
{"conversation_id":"conv_demo_1016_scam","caller_id":"+15555550101","call_secs":"9","utterance":"Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares.","tool_call_id":"toolu_01","village_id":"v_reyes","claimed_member":"marco","claimed_identity":"Marco (her son)","amount":2000,"currency":"USD","method":"unknown","urgency":"now","red_flags":["urgency","emotional_pressure"]}
```
Response (`$defs/response` + `data_report_money_request`):
```json
{"decision":"verify_with_member","say":"Voy a confirmar con Marco ahora mismo. No mande dinero todavía.","say_key":"money_hold","rule_id":"R-MONEY-VERIFY","lang":"es","decision_id":"dc_1016_1402_money",
 "data":{"status":"pending","verification_id":"ver_1016_01","claimed_member_id":"m_marco","channels":["app_prompt","outbound_call"],"deadline":"2026-10-16T14:02:54-04:00","deadline_secs":45,"next":"await_verification"}}
```
`await_verification` request: `{conversation_id, caller_id, call_secs, utterance, tool_call_id?, village_id?, verification_id}`; response `data`: `{status: confirmed|denied|timeout|unsure|unreachable, verification_id, state, answered_via: app_prompt|outbound_call|null, answered_at_secs, incident_id}` with `say` ∈ `money_confirmed|money_denied|money_timeout` (es/en per `lang`). Unknown claimed identity: `data.status: unverifiable`, `verification_id: null`, `next: none`, `say_key: money_unknown`. Errors: `401` bad secret, `422` body mismatch, `503` degraded (agent speaks the fixed core-down line). Duplicate `(conversation_id, tool_call_id)` → identical cached 200.
Other tools: `log_dose`, `report_symptom`, `whats_my_schedule`, `get_today`, `ask_family`, `create_village` per their `req_*`/`data_*` defs.

## 2. Init webhook `POST /hooks/elevenlabs/init`
Request (ElevenLabs): `{"caller_id":"+1…","agent_id":"agent_…","called_number":"+1…","call_sid":"CA…","conversation_id":"conv_…"}`.
Response (200, always):
```json
{"type":"conversation_initiation_client_data",
 "dynamic_variables":{"village_id":"v_reyes","member_id":"m_carmen","member_short_name":"Carmen","on_duty_name":"Ana","coordinator_name":"Ana","language":"es","today_summary":"Viernes 16 de octubre, 2:02 pm. Pastillas de la mañana anotadas a las 8:02. Ana está de turno."},
 "conversation_config_override":{"agent":{"language":"es"}}}
```
Unknown caller: same seven keys with `member_id: "m_unknown"`, `member_short_name: ""`, `today_summary: ""`, and `conversation_config_override.agent.first_message: "Hola, habla Luz, la línea de la familia Reyes. ¿Con quién hablo?"`.

## 3. Post-call webhook `POST /hooks/elevenlabs/post-call`
Headers: `ElevenLabs-Signature: t=<unix>,v0=<hmac_sha256>`. Body: `{"type":"post_call_transcription"|"post_call_audio"|"call_initiation_failure","event_timestamp":…, "data":{"agent_id","conversation_id","transcript":[{"role","message","time_in_call_secs","tool_calls":[…],"tool_results":[…],"conversation_turn_metrics":{…}}],"metadata":{"start_time_unix_secs","call_duration_secs","termination_reason","phone_call":{…}},"analysis":{"data_collection_results":{"verification_answer":{"value":"no"}},"transcript_summary":"…"},"conversation_initiation_client_data":{"dynamic_variables":{…}}}}`.
Response: `200 {"ok":true}` after signature check; `401` on bad signature (ElevenLabs retries; auto-disables after 10 failures, so never 5xx on parse errors).

## 4. Outbound `POST /calls/outbound` (control token; also called in-process)
Request: `{"member_id":"m_marco","reason":"verification","template":"T3","verification_id":"ver_1016_01"}`.
Response: `{"decision":{…R-VERIFY-CONSENT…},"placed":true,"conversation_id":"conv_verify_ver_1016_01","call_sid":"CA…"}` or `placed: false` (no consent / already placed / terminal row).
ElevenLabs call it makes (`POST https://api.elevenlabs.io/v1/convai/twilio/outbound-call`): see plan.md "Outbound payload"; response `{"success":true,"conversation_id":"conv_…","callSid":"CA…"}`.

## 5. Answer `POST /verifications/{vid}/answer` (`$defs/verification_answer_request`)
From village-caller (`X-Village-Secret`): `{"verification_answer":"no","listener_quote":"What? No!","call_sid":"CA…","call_secs":"8"}` (`via` defaults to `outbound_call`). From the app (member token): `{"verification_answer":"no","via":"app_prompt"}`; preferred path is WS `action{name: answer_verification}`.
Response: the full verification record (`verification.schema.json`) after the answer; `403` if the member is not the claimed member; `404` unknown id. Applied/dup/conflict/ignored is visible in `answers[].outcome`.

## 6. WS frames (`ws_messages.schema.json`)
`prompt` to Marco: `{"type":"prompt","verification_id":"ver_1016_01","question":{"en":"Did you just call Mamá asking for $2,000?","es":"¿Acaba de llamar a Mamá pidiendo $2,000?"},"detail":{"en":"Someone on the phone said they were you and that you're in trouble. She hasn't sent anything."},"options":[{"id":"no","label":{"en":"That wasn't me"}},{"id":"yes","label":{"en":"Yes, it was me"}}],"deadline":"2026-10-16T14:02:54-04:00"}`; close with `{"type":"prompt","verification_id":"…","closed":true,…}`. Full per-client order: `contracts/fixtures/ws_sequence_scam.json` (`start` then `denied|timeout_tail|confirmed_tail`).

## 7. Twilio import `POST https://api.elevenlabs.io/v1/convai/phone-numbers`
`{"provider":"twilio","label":"Village Mom line","phone_number":"+1…","sid":"AC…","token":"…","agent_id":"<mom-line>"}` → `{"phone_number_id":"…"}` = `ELEVENLABS_PHONE_NUMBER_ID`.

## Gaps reported to the orchestrator (not implemented locally)
`money_core_down` say key; `GET /voice/token?agent=` for the web-call fallback; `call_failed` has no event kind (recorded on `verification.channels[]` + `incident{type: call_failed}` only).
