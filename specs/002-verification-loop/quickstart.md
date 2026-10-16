# Quickstart: FS-2 Verification loop (voice lane)

Prereqs: `.env` filled (`ELEVENLABS_API_KEY`, `VILLAGE_SECRET`, `CONTROL_TOKEN`, Twilio SID/token/number, `TEST_CALL_TO`, `DEMO_CARMEN_CALLER_ID`); Core running (`uv run uvicorn core.app:app --port 8787`); Funnel on (`tailscale funnel --bg 8787`, `curl https://richel-macbook.tail8feae0.ts.net/health`).

## 1. Agents as code
```bash
npm i -g @elevenlabs/cli && elevenlabs auth login            # or ELEVENLABS_API_KEY in env
cd agents && elevenlabs agents init                           # agents.json, tools.json, tests.json, *_configs/
# tool_configs/*.json and agent_configs/*.json are committed; wire ids:
elevenlabs tools add "report_money_request" --type webhook --config-path tool_configs/report_money_request.json   # repeat per tool
elevenlabs agents add "mom-line" --template minimal --config-path agent_configs/mom-line.json                    # + village-caller, setup
elevenlabs agents push --dry-run && elevenlabs agents push
elevenlabs agents list                                        # copy ids → ELEVENLABS_AGENT_{MOM_LINE,CALLER,SETUP}_ID
# workspace env vars (dashboard → Developers → Environment Variables, env production):
#   core_host = richel-macbook.tail8feae0.ts.net      core_secret = $VILLAGE_SECRET (secret)
# procedures (branch drafts + publish):
uv run scripts/push_procedures.py --agent $ELEVENLABS_AGENT_MOM_LINE_ID --all   # creates/updates drafts, then `agents update` publishes
```
Enable in the dashboard: workspace post-call webhook → `https://<core_host>/hooks/elevenlabs/post-call` (copy the secret to `ELEVENLABS_WEBHOOK_SECRET`); mom-line Security tab → "fetch initiation data" with the init URL from `agent_configs/mom-line.json`.

## 2. Import the Twilio number
```bash
curl -s -X POST https://api.elevenlabs.io/v1/convai/phone-numbers -H "xi-api-key: $ELEVENLABS_API_KEY" -H 'content-type: application/json' \
  -d "{\"provider\":\"twilio\",\"label\":\"Village Mom line\",\"phone_number\":\"$TWILIO_NUMBER\",\"sid\":\"$TWILIO_ACCOUNT_SID\",\"token\":\"$TWILIO_AUTH_TOKEN\",\"agent_id\":\"$ELEVENLABS_AGENT_MOM_LINE_ID\"}"
# → phone_number_id → .env ELEVENLABS_PHONE_NUMBER_ID   (Twilio account must be upgraded; trial = preamble + verified numbers only)
```

## 3. Curl the tools (no phone needed)
```bash
H='-H "X-Village-Secret: $VILLAGE_SECRET" -H "content-type: application/json"'
jq '.variants.denied.exchanges[0].request' contracts/fixtures/scam_call_tool_requests.json \
 | curl -s -X POST http://localhost:8787/tools/report_money_request -H "X-Village-Secret: $VILLAGE_SECRET" -H 'content-type: application/json' -d @- | jq .   # expect decision verify_with_member, data.status pending
# in a second terminal, answer as Marco within 30 s:
curl -s -X POST http://localhost:8787/verifications/ver_1016_01/answer -H "X-Village-Secret: $VILLAGE_SECRET" -H 'content-type: application/json' \
  -d '{"verification_answer":"no","via":"outbound_call","call_sid":"CA_test","call_secs":"8"}' | jq .state      # "denied"
jq '.variants.denied.exchanges[1].request' contracts/fixtures/scam_call_tool_requests.json \
 | curl -s -X POST http://localhost:8787/tools/await_verification -H "X-Village-Secret: $VILLAGE_SECRET" -H 'content-type: application/json' -d @- | jq .say
# → "Ese no era Marco. No mande dinero. Ana ya lo sabe."   (re-run the first curl unchanged → identical cached body)
curl -s -X POST http://localhost:8787/hooks/elevenlabs/init -H "X-Village-Secret: $VILLAGE_SECRET" -H 'content-type: application/json' \
  -d "{\"caller_id\":\"$DEMO_CARMEN_CALLER_ID\",\"agent_id\":\"x\",\"called_number\":\"$TWILIO_NUMBER\",\"call_sid\":\"CA1\",\"conversation_id\":\"conv_t\"}" | jq '.dynamic_variables | keys'   # 7 keys
```

## 4. First test calls
1. **Inbound:** from `DEMO_CARMEN_CALLER_ID` dial `$TWILIO_NUMBER`. Expect "Hola, Carmen. Soy Luz…" (init webhook worked). Say "Me llamó Marco llorando, dice que necesita dos mil dólares." Expect the hold line verbatim, the `prompt` on the judge phone (`/v/v_reyes/?m=<marco token>`), your `TEST_CALL_TO` phone ringing, and after a tap the outcome line verbatim. Check `GET /health` deps and the Control Room gate rows.
2. **Outbound only:** `curl -X POST localhost:8787/calls/outbound -H "Authorization: Bearer $CONTROL_TOKEN" -d '{"member_id":"m_marco","reason":"verification","template":"T3","verification_id":"ver_1016_01"}'` → phone rings with the T3 line; say "no"; the record shows `answers[0].via = outbound_call`.
3. **Web fallback:** open `https://elevenlabs.io/app/talk-to?agent_id=$ELEVENLABS_AGENT_MOM_LINE_ID` (or the kit `/call` page) and repeat step 1; `caller_id` is empty, Core resolves Carmen from `village_id`.
4. **Timeout:** step 1 but nobody taps or answers; at ~30 s Carmen hears "No pude confirmar con Marco. No mande dinero. Le aviso a Ana."; Ana's incident card appears; at 45 s the prompt closes.

## 5. Acceptance
`acceptance/run.sh V1 --lane voice` (runs `acceptance/v1.sh`, see tasks.md T024) and `uv run pytest core/voice -q`.
