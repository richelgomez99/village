# Village Voice Agents

Real agents are managed from this directory. Live outbound calls are still held until Twilio geo-permissions are fixed; use dry-run or local checks until then.

## Dry Run

```bash
uv run python scripts/check_tool_schemas.py
uv run python scripts/push_procedures.py --dry-run --all
cd agents && elevenlabs agents push --dry-run
```

Tool URLs use `https://richel-macbook.tail8feae0.ts.net/...`.

Local operator env:

- `CORE_HOST=https://richel-macbook.tail8feae0.ts.net`
- `TUNNEL_URL=https://richel-macbook.tail8feae0.ts.net`
- `VILLAGE_TOOL_SECRET`
- `VILLAGE_PHONE_NUMBER=+18482579221` (Carmen's Village line; print as +1 848 257 9221 on the fridge card)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_PHONE_NUMBER_ID`
- `ELEVENLABS_AGENT_ID`
- `ELEVENLABS_CALLER_AGENT_ID`
- `ELEVENLABS_AGENT_SETUP_ID`
- `ELEVENLABS_WEBHOOK_SECRET`

## Push Agents And Tools

```bash
cd agents
elevenlabs tools push --dry-run
elevenlabs agents push --dry-run
elevenlabs tools push
elevenlabs agents push
elevenlabs agents list
```

Copy the IDs into `.env` as `ELEVENLABS_AGENT_ID` for mom-line and `ELEVENLABS_CALLER_AGENT_ID` for village-caller.

Import and attach the Twilio number:

```bash
curl -s -X POST https://api.elevenlabs.io/v1/convai/phone-numbers \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "content-type: application/json" \
  -d "{\"provider\":\"twilio\",\"label\":\"Village Mom line\",\"phone_number\":\"${VILLAGE_PHONE_NUMBER:-+18482579221}\",\"sid\":\"$TWILIO_ACCOUNT_SID\",\"token\":\"$TWILIO_AUTH_TOKEN\",\"agent_id\":\"$ELEVENLABS_AGENT_MOM_LINE_ID\"}"
```

Save the returned phone number id as `ELEVENLABS_PHONE_NUMBER_ID`.

Push procedure drafts after the agent ID exists:

```bash
uv run python scripts/push_procedures.py --dry-run --agent "$ELEVENLABS_AGENT_ID" --all
```

The money procedure speaks the tool `say` field verbatim, then calls `await_verification` when `verification_status` is `pending`.

## Smoke Test

Run the mock Core without real Core:

```bash
uv run uvicorn core.voice.mock_core:app --port 8788
```

Then point `core_host` at the tunnel or local forward for that server and run a denied money request. The expected headline line is:

```text
Ese no era Marco. No mande dinero. Ana ya lo sabe.
```

Local check without a phone:

```bash
uv run python scripts/voice_check.py
```

Do not run `--call` until Twilio geo-permissions are fixed.
