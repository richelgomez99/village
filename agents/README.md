# Village voice agents (ElevenLabs agents-as-code)

Three agents, eleven webhook tools, all from this directory. The source of truth is these files; `agents/live/*.json` is the last pulled snapshot of what is actually on ElevenLabs.

| Agent | File | Env var | What it is |
|---|---|---|---|
| Luz · Línea de Mamá (mom line) | `agent_configs/mom-line.json` | `ELEVENLABS_AGENT_ID` | Inbound line on +1 848 257 9221. Bilingual (es default, en preset, `language_detection`). Care tools + money check + D19 receptionist branch (`receptionist == "on"`). |
| Village Caller | `agent_configs/village-caller.json` | `ELEVENLABS_AGENT_CALLER_ID` (alias `ELEVENLABS_CALLER_AGENT_ID`) | Outbound: money verification to the real member, and the Spanish welcome call (prompt/first message override, `call_purpose=welcome`). |
| Village Setup | `agent_configs/setup.json` | `ELEVENLABS_SETUP_AGENT_ID` | Founding intake (prompts/setup_agent.md v2): `create_village`, then `submit_answer` after every answer. Web mic via `GET /voice/token?agent=setup`. |

## Env vars (.env, never committed, never printed)

| Var | Meaning |
|---|---|
| `ELEVENLABS_API_KEY` | API key (deploy, simulate, caption polling, token route). |
| `ELEVENLABS_PHONE_NUMBER_ID` | Imported Twilio number (`phnum_…`), attached to the mom line. |
| `VILLAGE_PHONE_NUMBER` | +18482579221, the number printed on the fridge card. |
| `TUNNEL_URL` | Public Core URL; replaces `${TUNNEL_URL}` in tool/agent configs at push time (Funnel `https://richel-macbook.tail8feae0.ts.net` → :8790). |
| `VILLAGE_TOOL_SECRET` | Value of the ElevenLabs workspace secret `VILLAGE_TOOL_SECRET`, sent as `X-Village-Secret` on every tool call and the init webhook. Core enforces it **only when set** in Core's env (legacy name `VILLAGE_SECRET`). `deploy_elevenlabs.py --sync-secret` generates it into .env if empty and updates the workspace secret. Copy the same value into the live Core's .env to turn enforcement on. |
| `ELEVENLABS_WEBHOOK_SECRET` | HMAC secret of the workspace post-call webhook; Core verifies `ElevenLabs-Signature` only when set. Written by `--post-call-webhook`. |
| `TEST_CALL_TO` | Operator's phone (plays Carmen) for test/welcome calls. |
| `DEMO_ELDER_CALLER_ID` (old: `DEMO_CARMEN_CALLER_ID`) | Caller id the init hook treats as the care recipient. |
| `VILLAGE_RECEPTIONIST` | `on`/`off` forces receptionist mode; otherwise the spec decides (`R-MONEY-UNKNOWN.params.receptionist_mode`, set by Evolve). |
| `VILLAGE_CAPTIONS` | `off` disables live caption polling (default on when the API key is set). |

## Deploy

```bash
uv run python scripts/deploy_elevenlabs.py --check        # every {{var}} referenced (prompt, first message, presets, tool URLs/bodies) has a default
uv run python scripts/deploy_elevenlabs.py --pull         # snapshot live agents -> agents/live/, merge live default vars into configs
uv run python scripts/deploy_elevenlabs.py --dry-run      # what would change (tool URLs, timeouts, vars, overrides)
uv run python scripts/deploy_elevenlabs.py --yes-live     # push tools + agents + verbatim-say procedures (ONLY with the coordinator's "push now")
uv run python scripts/deploy_elevenlabs.py --yes-live --only setup
uv run python scripts/deploy_elevenlabs.py --yes-live --sync-secret
uv run python scripts/deploy_elevenlabs.py --yes-live --post-call-webhook   # workspace HMAC webhook -> ${TUNNEL_URL}/hooks/elevenlabs/post-call
```

Rules: a live agent must have **zero required dynamic variables** (a call with a missing one dies: "Missing required dynamic variables"); the push fails if `--check` fails. The mom line's first message is static and bilingual; Core's init webhook (`/hooks/elevenlabs/init`) returns all ten variables and overrides the first message only when receptionist mode is on and the caller is unknown.

Tools: every tool posts to `${TUNNEL_URL}/tools/<tool>` (Core's dispatcher; tools it does not own fall back to `core.voice.tools`), `submit_verification_answer` to `/verifications/{{verification_id}}/answer`. `await_verification` and `screen_caller` time out at 35 s (Core waits ≤ 30 s). Every care tool sends `lang` (es|en): `say` comes back in that language, with both lines in `data.say_es` / `data.say_en` for the projector captions. Procedures published on the mom line: "Money check - verbatim say", "Receptionist screen - verbatim say".

## Test without a phone

```bash
# your own Core + public URL (never the live :8790 Core: its dialer is real)
SURREAL_DB_URL= VILLAGE_MEMORY=off VILLAGE_DIALER=fake uv run uvicorn core.app:app --port 8794
cloudflared tunnel --url http://127.0.0.1:8794          # prints https://<x>.trycloudflare.com
uv run python scripts/voice_check.py --core http://127.0.0.1:8794 --simulate https://<x>.trycloudflare.com
```

`--simulate` makes a throwaway copy of the mom line (tools tagged `[voice2-sim]`, pointing at your tunnel), runs ElevenLabs `simulate-conversation` with a scripted Carmen ("Me llamó Marco llorando… dos mil dólares en tarjetas"), POSTs the agent's own tool params to your Core through the tunnel (secret header included), plays Marco answering "no" on his device, then re-runs the simulation with Core's real responses and checks every `say` was spoken verbatim. It deletes the copies afterwards. (simulate-conversation does not execute webhook tools itself, hence the two passes.)

`uv run python scripts/voice_check.py --core http://127.0.0.1:8794` posts the denied fixture to `report_money_request` and prints the say.

## Stage: one presenter phone, two roles (`scripts/stage.sh caller`)

```bash
scripts/stage.sh caller elder     # default: the presenter's number (DEMO_ELDER_CALLER_ID) is the care recipient (Run beat)
scripts/stage.sh caller unknown   # same number is treated as an unknown caller (Receptionist beat: presenter plays the scammer)
scripts/stage.sh status
```

It calls `POST /admin/demo-caller {role}` (control token or admin key; in memory, `reset` returns to `elder`). The init webhook reads it: with `unknown`, the presenter's caller id gets the guest variables (`caller_known=false`), so when receptionist mode is on (Evolve approved it, or `VILLAGE_RECEPTIONIST=on`) the call opens with "Carmen's phone, this is Village. Who's calling?" and `screen_caller` decides. Switch back to `elder` before the next Carmen beat. Env: `CORE_URL` (default http://127.0.0.1:8790), `CONTROL_TOKEN`, `DEMO_VILLAGE_ID`.

## Evaluation and data collection (mom line)

Every conversation is scored by ElevenLabs (`platform_settings.evaluation.criteria`, type `prompt`): `safe_money_outcome` (never agreed to send money; read each tool `say` word for word), `verified_with_real_member` (money request → report_money_request + await_verification), `usted_register`, `ai_disclosed`. Data collection: `claimed_identity`, `amount`, `outcome` (denied|timeout|confirmed|none), `caller_language`. Both arrive in the post-call webhook (`analysis.evaluation_criteria_results`, `analysis.data_collection_results`) and in `GET /v1/convai/conversations/{id}`.

## Calls (operator only)

```bash
uv run python scripts/voice_check.py --call                 # verification call (Village Caller) to TEST_CALL_TO
uv run python scripts/voice_check.py --welcome --dry-run    # welcome-call payload, phone masked
uv run python scripts/voice_check.py --welcome              # Spanish welcome call to TEST_CALL_TO
```

The welcome call asks consent, the evening check-in, what to call her and her quiet hours. Its post-call webhook (`data_collection`: `welcome_consent`, `preferred_name`, `evening_checkin`, `quiet_hours`, `quiet_hours_words`) calls `core.builder.founding.confirm_quiet_hours()`, so P-QH-01 becomes her words with `source_ref = welcome_call:<conversation_id>@<call time>` and the second in the call she said it. Needs the post-call webhook (`--post-call-webhook`).

## Live captions (D18)

Each transcript turn becomes `control{kind: caption, payload: {es, en, speaker, final}}` (Haiku 5.5 translation through `core.llm.llm("haiku")`; `en=""` if the model is off). Sources: Core polls `GET /v1/convai/conversations/{id}` every 2 s while a call is active (started by the init webhook for inbound calls and by `/calls/outbound`; by hand: `POST /hooks/elevenlabs/captions/{conversation_id}`), and the post-call webhook flushes any turn the poller missed.

## Routes Core gets from core/voice

`/hooks/elevenlabs/init`, `/hooks/elevenlabs/post-call`, `/hooks/elevenlabs/tools/{tool}` (alias of the tool path with the secret check), `/hooks/elevenlabs/token` (and `/voice/token` once core/app.py grafts the `/voice/` prefix), `/hooks/elevenlabs/captions/{id}`, `/calls/outbound`.
