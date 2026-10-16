# Tasks: FS-2 Verification loop

Format: `T### [P?] lane · version · minutes · deps · task → acceptance · principle`. [P] = parallel-safe (different files). Lanes: `voice` (`agents/`, `core/voice/`), `core` (`core/services.py`, `core/routes/`). Acceptance checks are in `acceptance/v1.sh` (T024) unless named otherwise.

## Phase A: setup and contracts (V0, 10:00–10:40)
- **T001** [P] voice · V0 · 15 · — · `agents/` CLI project (`agents.json`, `tools.json`, `agent_configs/`, `tool_configs/`, `procedures/`), `.gitignore` for pulled ids → `elevenlabs agents push --dry-run` exits 0 · IX
- **T002** [P] voice · V0 · 25 · T001 · 8 tool configs (`log_dose`, `report_symptom`, `whats_my_schedule`, `ask_family`, `report_money_request`, `await_verification`, `submit_verification_answer`, `create_village`; `get_today` optional) with `{{system_env__core_host}}` URLs, `X-Village-Secret` header, system dynamic vars, timeouts per plan table, assignments → `scripts/check_tool_schemas.py` proves each `request_body_schema` ⊆ `voice_tools.schema.json#/$defs/req_<tool>` · VI
- **T003** [P] voice · V0 · 20 · T001 · `agent_configs/mom-line.json` (es + en preset, patient turn settings, 7 dynamic-variable placeholders, guardrail, prompt from `prompts/mom_line.md` rewritten to the contract variable names), `village-caller.json` (T3 first message, data_collection), `setup.json` shell → push dry-run clean; prompt contains no variable outside the seven · V
- **T004** [P] voice · V0 · 20 · T002 · `agents/procedures/{money_check,dose_report,verify_answer}.json` + `scripts/push_procedures.py` (create/update draft → `agents.update` publish; prints `procedure_validation_failed` paths) → `--dry-run` serializes `content` as JSON string with a non-empty `steps` · V
- **T005** [P] voice · V0 · 20 · — · `core/voice/mock_core.py`: FastAPI app answering `/tools/*` and `/verifications/*/answer` from `scam_call_tool_requests.json` (keyed tool + conversation_id + tool_call_id; `await` sleeps `returned_at − at`) → `pytest core/voice/tests/test_mock_core.py` (5 variants) · VI
- **T006** [P] core · V0 · 20 · — · `core/services.py` stubs `start_verification`, `answer_verification`, `await_verification`, `tick_verifications`, `place_outbound` returning fixture shapes → importable, typed with pydantic models generated from the schemas · VI

## Phase B: Core handlers (V1, 10:40–11:30)
- **T007** core · V1 · 30 · T006, FS-1 gate · real `services.start_verification`: gate call (R-MONEY-*), id alloc, SurrealDB insert of `verification` + events `money_request`, `verification_pending`, `pattern`; returns the tool response → `pytest core/tests/test_services_verification.py` T29, T36, T37, T44, T45, T46 with FakeClock · I, III
- **T008** core · V1 · 25 · T007 · `services.answer_verification` CAS on `version` (`applied|dup|conflict|ignored`), events `verification_confirmed|denied|timeout|answer_conflict`, incident upsert `inc_<id>` → tests T30, T32, T34, T35, T50 · I
- **T009** core · V1 · 20 · T007 · `services.await_verification` long-poll (asyncio Event per id, 30 s cap → CAS `default_spoken`, say `money_timeout`; cached say on terminal rows) and `tick_verifications` (5 s, Clock, `timed_out`, prompt close, cancel call) → tests T31, T33, "deadline during in-flight await", time-warp jump · I
- **T010** [P] voice · V1 · 25 · T006 · `core/voice/tools.py`: `POST /tools/{name}`, secret check, per-tool pydantic (`additionalProperties: false`), `call_secs` coercion, digit redaction in `utterance`, idempotency cache (`(conversation_id, tool_call_id)` → fallback key), 503 on degraded deps, TOOL span → `pytest core/voice/tests/test_tools.py` replays all 5 fixture variants byte-for-byte; T49 duplicate returns cached body · I, VIII
- **T011** [P] voice · V1 · 20 · T006 · `core/voice/init_hook.py`: `caller_id` → member via village `members[].phone` + `DEMO_CARMEN_CALLER_ID` override; builds the seven vars (`today_summary` from dose/rota bindings); guest set for unknown; creates `voice_call` row → test: known/unknown/web(empty caller) all return exactly 7 keys, < 200 ms · II
- **T012** [P] voice · V1 · 25 · T006 · `core/voice/outbound.py`: `POST /calls/outbound` (control token or in-process), consent re-read, CAS `call_placed_at`, ElevenLabs `twilio.outbound_call` with T3 dynamic vars + `ringing_timeout_secs: 30`, channel `ringing`, `escalation` event; `cancel(call_sid)` via Twilio REST best effort; `FakeDialer` in tests → tests: consent false → `placed: false` + `skipped_no_consent`; second call → no dial; terminal row → no dial · II
- **T013** core · V1 · 20 · T008 · `POST /verifications/{vid}/answer` (secret or member token; 403 wrong member) and WS `action answer_verification` → `result`; `prompt` send to the claimed member's sockets at creation and `prompt{closed}` on resolution → hub test replays `ws_sequence_scam.json` `start` + `denied` for client `marco` · II
- **T014** [P] voice · V1 · 25 · T011 · `core/voice/post_call.py`: HMAC verify (`webhooks.construct_event`, raw body, 401 on bad sig, else always 200), handle the 3 types, `call_initiation_failure` → channel `failed` + incident `call_failed`, provenance reconcile (secs/quote, superseding notes), backup `data_collection.verification_answer` keyed `(verification_id, call_sid)`, Memory outbox stub file, `[PALABRA]` redaction → tests with a signed sample payload; tampered body → 401 · III
- **T015** core · V1 · 15 · T007, T008 · incident binding `bv_incident` (title/summary localized, `provenance[]` with the call source, `verification_status`, `pattern_flag`) + `scams_stopped` control counter → `ws_sequence_scam.json` `denied` frames for client `ana` match · III

## Phase C: live wiring (V1, 11:30–12:10)
- **T016** voice · V1 · 15 · T002, T003 · `elevenlabs agents push`; set workspace env vars `core_host`, `core_secret`; enable init webhook + post-call webhook; ids into `.env` → `elevenlabs agents status` clean; `curl /hooks/elevenlabs/init` from the dashboard test returns 7 vars · IX
- **T017** voice · V1 · 15 · T016 · Twilio import (`POST /v1/convai/phone-numbers`), assign inbound to mom-line → `ELEVENLABS_PHONE_NUMBER_ID` set; smoke 09 `--call` rings `TEST_CALL_TO` (resolves R5) · II
- **T018** voice · V1 · 20 · T004, T016 · push procedures to mom-line and village-caller; resolve R2/R3 with one dose call; apply fallback (a)/(b) if needed → one inbound call speaks the `log_dose` `say` verbatim (transcript check) · V
- **T019** voice · V1 · 15 · T010–T013, T017 · first end-to-end phone run (denied, timeout, confirmed) with the judge phone; record RTTs in `RESULTS.md` → all three outcome lines spoken verbatim; incident on Ana's app; spans in Arize (`session.id = village-v_reyes`) · VIII
- **T020** [P] voice · V1 · 15 · T016 · web-call fallback: kit `/call` page or talk-to link with the seven dynamic vars; Core resolves subject from `village_id` when `caller_id` is empty → one browser call reaches `/tools/report_money_request` with `caller_id: ""` and still opens a verification · VII
- **T021** [P] voice · V1 · 10 · T019 · Round-1 insurance: 30 s screen+phone recording of the denied run → file in `docs/media/` linked from DEVPOST V1 · VIII

## Phase D: hardening and acceptance (V1, by 12:15)
- **T022** [P] core · V1 · 15 · T009 · restart safety: boot-time scan closes past-deadline rows, never redials rows with `call_placed_at` → test "restart mid-pending" · I
- **T023** [P] voice · V1 · 10 · T010 · `.env.example` additions (orchestrator PR) and `docs` note on `core_host` switch to the Worker fallback → `uv run smoke/00_env_check.py` lists the new vars · IX
- **T024** voice+core · V1 · 25 · T007–T015 · `acceptance/v1.sh` (below) → exits 0 locally against Core with `FakeDialer` and the mock ElevenLabs caller · VII

### `acceptance/v1.sh` (mocked ElevenLabs caller; real Core, gate, SurrealDB, WS)
```bash
#!/usr/bin/env bash
set -euo pipefail
: "${CORE:=http://localhost:8787}" "${VILLAGE_SECRET:?}" "${CONTROL_TOKEN:?}"
F=contracts/fixtures/scam_call_tool_requests.json
H=(-H "X-Village-Secret: $VILLAGE_SECRET" -H 'content-type: application/json')
tool() { jq -c ".variants.$1.exchanges[$2].request" $F | curl -sf -X POST "$CORE/tools/$3" "${H[@]}" -d @-; }
step() { echo "== $1"; }
step "0 reset + fake dialer";  curl -sf -X POST "$CORE/demo/reset" -H "Authorization: Bearer $CONTROL_TOKEN" -d '{"dialer":"fake","clock":"2026-10-16T14:02:00-04:00"}' >/dev/null
step "1 open WS as marco/ana/control (scripts/ws_tap.py records frames to out/ws_*.jsonl)";  uv run scripts/ws_tap.py --village v_reyes --clients marco,ana,control --out out & TAP=$!; sleep 1
step "2 denied: report → prompt → app answer → await";  R=$(tool denied 0 report_money_request); echo "$R" | jq -e '.decision=="verify_with_member" and .data.status=="pending"' >/dev/null
VID=$(echo "$R" | jq -r .data.verification_id)
grep -q '"type": *"prompt"' out/ws_marco.jsonl                                   # prompt delivered to Marco only
! grep -q '"type": *"prompt"' out/ws_ana.jsonl
curl -sf -X POST "$CORE/calls/outbound" -H "Authorization: Bearer $CONTROL_TOKEN" -H 'content-type: application/json' -d "{\"member_id\":\"m_marco\",\"reason\":\"verification\",\"template\":\"T3\",\"verification_id\":\"$VID\"}" | jq -e '.placed==true' >/dev/null
(sleep 3; uv run scripts/ws_answer.py --as marco --verification "$VID" --answer no) &
S=$(tool denied 1 await_verification); echo "$S" | jq -e '.say=="Ese no era Marco. No mande dinero. Ana ya lo sabe." and .data.answered_via=="app_prompt"' >/dev/null
grep -q '"kind": *"incident"' out/ws_ana.jsonl && grep -q '"closed": *true' out/ws_marco.jsonl
step "3 duplicate webhook → identical cached body";  diff <(tool duplicate_webhook 0 report_money_request) <(tool duplicate_webhook 1 report_money_request)
step "4 timeout: no answer → safe default at 30 s, timed_out at 45 s";  curl -sf -X POST "$CORE/demo/reset" -H "Authorization: Bearer $CONTROL_TOKEN" -d '{"dialer":"fake","clock":"2026-10-16T14:02:00-04:00"}' >/dev/null
tool timeout 0 report_money_request >/dev/null; T0=$(date +%s); S=$(tool timeout 1 await_verification); T1=$(date +%s)
echo "$S" | jq -e '.say=="No pude confirmar con Marco. No mande dinero. Le aviso a Ana." and .data.state=="default_spoken"' >/dev/null; [ $((T1-T0)) -ge 29 ] && [ $((T1-T0)) -le 32 ]
curl -sf -X POST "$CORE/clock/warp" -H "Authorization: Bearer $CONTROL_TOKEN" -H 'content-type: application/json' -d '{"minutes":1}' >/dev/null; sleep 6
curl -sf "$CORE/verifications/ver_1016_01" "${H[@]}" | jq -e '.state=="timed_out"' >/dev/null
step "5 confirmed via village-caller answer";  curl -sf -X POST "$CORE/demo/reset" -H "Authorization: Bearer $CONTROL_TOKEN" -d '{"dialer":"fake","clock":"2026-10-16T14:02:00-04:00"}' >/dev/null
tool confirmed 0 report_money_request >/dev/null
(sleep 2; jq -c '.variants.confirmed.answers[0].body' $F | curl -sf -X POST "$CORE/verifications/ver_1016_01/answer" "${H[@]}" -d @- | jq -e '.state=="confirmed"' >/dev/null) &
tool confirmed 1 await_verification | jq -e '.say | startswith("Marco dice que sí fue él.")' >/dev/null
step "6 unknown claimed → no verification";  tool unknown_claimed 0 report_money_request | jq -e '.rule_id=="R-MONEY-UNKNOWN" and .data.verification_id==null' >/dev/null
step "7 no consent → app prompt only";  curl -sf -X POST "$CORE/demo/consent" -H "Authorization: Bearer $CONTROL_TOKEN" -d '{"member_id":"m_marco","ai_calls":false}' >/dev/null
tool denied 0 report_money_request | jq -e '.data.channels==["app_prompt"]' >/dev/null
step "8 init webhook: known, unknown, web";  for C in "$DEMO_CARMEN_CALLER_ID" "+10000000000" ""; do curl -sf -X POST "$CORE/hooks/elevenlabs/init" "${H[@]}" -d "{\"caller_id\":\"$C\",\"agent_id\":\"a\",\"called_number\":\"n\",\"call_sid\":\"s\",\"conversation_id\":\"c\"}" | jq -e '.dynamic_variables | keys | length==7' >/dev/null; done
step "9 post-call HMAC";  uv run scripts/sign_postcall.py contracts/fixtures/postcall_sample.json | curl -sf -X POST "$CORE/hooks/elevenlabs/post-call" -H @- >/dev/null
curl -s -o /dev/null -w '%{http_code}' -X POST "$CORE/hooks/elevenlabs/post-call" -H 'ElevenLabs-Signature: t=1,v0=bad' -d '{}' | grep -q 401
step "10 gate tests model-off";  uv run pytest core/gate core/voice -q
kill $TAP; echo "V1 voice acceptance: PASS"
```
Steps 2–7 are the scenarios in spec.md §User scenarios 1–3, 6–8; step 9 is FR-010; step 10 is Constitution I.

## Addendum (D18): live captions
- T025 [voice+core, V1, 20 min] On each mom-line turn (tool request `utterance`, and post-call turns), Core emits `control{kind: caption, es, en, secs}` to the Control Room (Claude Haiku translation, cached per utterance). The judge playing Marco only ever sees English. Acceptance: the scam call shows es + en lines on the projector within 1 s of each turn. Principle VIII.

## Addendum (D19): receptionist mode on Carmen's line
- T026 [voice, V4, 35 min] `mom-line` gains an inbound **screening** branch: when `system__caller_id` is not a known member (init webhook returns `caller_known=false`), first message is the receptionist greeting ("Carmen's phone, this is Village. Who's calling?"); tool `screen_caller{claimed_identity, purpose, money_request, amount, utterance, conversation_id}` → Core gate (R-MONEY-VERIFY / R-MONEY-UNKNOWN) → verification with the real member on their own device → `await_verification` → verbatim outcome to the caller ("Marco says this isn't him. I won't put you through.") or pass-through (`transfer_to_number` to Carmen) when confirmed. Known members pass through immediately. Acceptance: a call from an unknown number claiming to be Marco never reaches Carmen without Marco's confirmation (mock caller in `acceptance/v4.sh`). Principles I, II.
- T027 [core, V4, 15 min] After a refused screen, Core places/queues a short outbound to Carmen ("Alguien que decía ser Marco llamó; no lo pasé.") and posts the incident to the village chat.

## Addendum (D22): evening check-in call (optional capability)
- T028 [voice, V3 stretch, 25 min] Outbound check-in at the evening slot (if the family enabled it and Carmen consented on the welcome call): "¿Ya se tomó las de la tapa azul?" → `log_dose{slot: evening, answer}`; the family sees the event live. If she says she already took one and asks about another: the reviewed line "Ya está anotada; no puedo aconsejar sobre dosis. Le aviso a Marco."
