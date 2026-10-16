# Village Voice Agents

V0 is dry-run only. `ELEVENLABS_API_KEY`, the Twilio number, and `ELEVENLABS_PHONE_NUMBER_ID` are not available yet.

## Dry Run

```bash
uv run python scripts/check_tool_schemas.py
uv run python scripts/push_procedures.py --dry-run --all
cd agents && elevenlabs agents push --dry-run
```

Tool URLs use `https://{{system_env__core_host}}/...`. Set the ElevenLabs workspace environment variables when credentials exist:

- `core_host=richel-macbook.tail8feae0.ts.net`
- `core_secret=$VILLAGE_SECRET`

Local operator env:

- `CORE_HOST=https://richel-macbook.tail8feae0.ts.net`
- `VILLAGE_SECRET`
- `VILLAGE_PHONE_NUMBER=+18482579221` (Carmen's Village line; print as +1 848 257 9221 on the fridge card)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_PHONE_NUMBER_ID`
- `ELEVENLABS_AGENT_MOM_LINE_ID`
- `ELEVENLABS_AGENT_CALLER_ID`
- `ELEVENLABS_AGENT_SETUP_ID`
- `ELEVENLABS_WEBHOOK_SECRET`

## When Keys Exist

```bash
cd agents
elevenlabs agents push --dry-run
elevenlabs agents push
elevenlabs agents list
```

Copy the IDs into `.env` as `ELEVENLABS_AGENT_MOM_LINE_ID`, `ELEVENLABS_AGENT_CALLER_ID`, and `ELEVENLABS_AGENT_SETUP_ID`.

Import and attach the Twilio number:

```bash
curl -s -X POST https://api.elevenlabs.io/v1/convai/phone-numbers \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "content-type: application/json" \
  -d "{\"provider\":\"twilio\",\"label\":\"Village Mom line\",\"phone_number\":\"${VILLAGE_PHONE_NUMBER:-+18482579221}\",\"sid\":\"$TWILIO_ACCOUNT_SID\",\"token\":\"$TWILIO_AUTH_TOKEN\",\"agent_id\":\"$ELEVENLABS_AGENT_MOM_LINE_ID\"}"
```

Save the returned phone number id as `ELEVENLABS_PHONE_NUMBER_ID`.

Push procedure drafts after the agent IDs exist:

```bash
uv run python scripts/push_procedures.py --dry-run --agent "$ELEVENLABS_AGENT_MOM_LINE_ID" --all
```

Live procedure publish is intentionally disabled in the script until credentials are present and the orchestrator approves the API call shape.

## Smoke Test

Run the mock Core without real Core:

```bash
uv run uvicorn core.voice.mock_core:app --port 8788
```

Then point `core_host` at the tunnel or local forward for that server and run a denied money request. The expected headline line is:

```text
Ese no era Marco. No mande dinero. Ana ya lo sabe.
```
