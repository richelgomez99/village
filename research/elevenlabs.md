# ElevenLabs for Village: capability research (Oct 15 2026)

Sources: ElevenLabs live docs (`.md` pages fetched 2026-10-15), `~/.claude/skills/agents` (SKILL.md + references), `elevenlabs.io/pricing/agents`, Twilio trial docs. Items marked **[VERIFY]** are inferred and still need a live test.

---

## 1. Phone: fastest path to an inbound number

**Verdict: buy one Twilio number on an upgraded (paid) Twilio account and use the native import. ElevenLabs still does not sell numbers.** The import is one API call, and ElevenLabs configures the Twilio webhooks itself.

- **No direct numbers.** The docs list only Twilio native, SIP trunk (Telnyx, Plivo, Bandwidth, Sinch, Vonage), Exotel, and WhatsApp. The help center says Twilio needs "a paid Twilio account and an active Twilio phone number."
- **Trial Twilio does not work well here.** A trial can only call verified numbers (max 5) and only in your sign-up country. Trial calls also play a "trial account" preamble that the caller has to press a key to get past, which breaks a live demo **[VERIFY]**. Upgrading means loading about $20 of credit. A US local number costs about $1.15/mo.
- **Verified caller IDs** work for outbound only. They can't be assigned to an agent for inbound calls.
- **SIP trunk** is slower to set up: you need a provider account, digest auth, and an IP allowlist. Only use it if Twilio fails.

```bash
# Import + assign in one call
curl -X POST https://api.elevenlabs.io/v1/convai/phone-numbers -H "xi-api-key: $ELEVENLABS_API_KEY" \
 -d '{"provider":"twilio","label":"Mom line","phone_number":"+1555...","sid":"AC...","token":"...","agent_id":"agent_mom"}'
```

**Outbound calls** go to `POST /v1/convai/twilio/outbound-call`. The response is `{success, conversation_id, callSid}`.

```python
client.conversational_ai.twilio.outbound_call(
  agent_id=ESCALATION_AGENT, agent_phone_number_id=PHONE_ID, to_number="+1MARCO",
  conversation_initiation_client_data={
    "dynamic_variables": {"patient_name":"Carmen","missed_med":"blue pill (lisinopril)","missed_at":"9:00","village_id":"v_123","escalation_id":"esc_9"},
    "conversation_config_override": {"agent": {"first_message": "Hi Marco, this is Village. Carmen hasn't confirmed her {{missed_med}} from {{missed_at}}.", "language": "en"}}},
  telephony_call_config={"ringing_timeout_secs": 30})
```

- **Personalising inbound calls.** Enable the **conversation initiation webhook** in Settings, then turn on "fetch initiation data" in the agent's Security tab. ElevenLabs POSTs `{caller_id, agent_id, called_number, call_sid, conversation_id}` to your server while the phone is still ringing. Return `{"type":"conversation_initiation_client_data","dynamic_variables":{...}}`, and include **all** dynamic variables the agent declares. Core can use this to look up Carmen by caller ID and inject her schedule.
- **Failed outbound calls** produce a `call_initiation_failure` webhook with `failure_reason` set to busy, no-answer or unknown. Use it to retry with the next sibling.
- **Latency:** v4 Turbo TTS is about 100 ms (Flash v2.5 is about 75 ms). The LLM's time to first token dominates; Haiku/Flash-class models are typically 0.3–0.6 s. The post-call payload reports this per turn in `conversation_turn_metrics.convai_llm_service_ttfb`. Expect roughly 1 s of voice-to-voice delay on PSTN.

## 2. LLM: native Claude vs custom

**Verdict: Claude is available natively. Use it, not a custom LLM.**

- The supported-models page lists Anthropic models: Opus 5.5/5/4.8/4.7/4.6, **Sonnet 5.5**/5/4.6/4.5, and **Haiku 4.5**. Skill IDs include `claude-sonnet-5-5`, `claude-sonnet-4-6` and `claude-haiku-4-5`.
- Confirm the exact IDs with `GET /v1/convai/llm/list`.
- The docs recommend "Claude Sonnet 5.5" for tool-heavy agents.
- Native models get automatic backup LLM cascading (`cascade_timeout_seconds` defaults to 4).

**Custom LLM** needs an OpenAI-compatible `/v1/chat/completions` or `/v1/responses` endpoint that streams SSE (`data: {...}\n\n` … `data: [DONE]`). It is configured as `"llm":"custom-llm","custom_llm":{"url","model_id","api_key":{"secret_id"}, "api_type":"chat_completions"}`. System tools are passed through to it in the `tools` array.

**Bedrock option.** If the Bedrock story matters to judges, run a LiteLLM proxy (`model: bedrock/anthropic.claude-...`) behind cloudflared. The cost is an extra hop, about 200–500 ms, plus the risk of the tunnel dropping. Whether Bedrock itself now has an OpenAI-compatible endpoint for Claude is **[VERIFY]**.

**Recommendation:**
- Mom line: `claude-haiku-4-5` for speed, with `claude-sonnet-4-6` as backup.
- Setup agent: `claude-sonnet-5-5`.
- Use Bedrock-hosted Claude inside Core (the village generator and evals) and say so in the pitch: "Claude everywhere; Bedrock for reasoning, ElevenLabs-native Claude for the voice loop."

## 3. Server (webhook) tools

**Request format: the body is exactly the `request_body_schema` you define.** The API reference says the schema "will be sent as the json body". The skill doc's `{tool_call_id, tool_name, parameters, conversation_id}` envelope is likely wrong; treat it as **[VERIFY]** and log the raw body on the first call.

**Getting `conversation_id` and the caller's number to Core.** Add body properties sourced from dynamic variables (`dynamic_variable`; this is mutually exclusive with `description`):

```json
{"type":"webhook","name":"log_dose","description":"Log that Carmen took a medication. Call whenever she says she took a pill.",
 "response_timeout_secs":10,"pre_tool_speech":"off","tool_call_sound":"typing","tool_call_sound_behavior":"always",
 "interruption_mode":"disable_during_tool","execution_mode":"immediate",
 "api_schema":{"url":"https://{{system_env__core_host}}/tools/log_dose","method":"POST",
  "request_headers":{"X-Village-Secret":{"env_var_label":"core_secret"}},
  "request_body_schema":{"type":"object","required":["pill_description","utterance"],"properties":{
    "pill_description":{"type":"string","description":"Pill as Carmen described it, e.g. 'blue pill'"},
    "utterance":{"type":"string","description":"Carmen's exact words, verbatim, original language"},
    "conversation_id":{"type":"string","dynamic_variable":"system__conversation_id"},
    "caller_id":{"type":"string","dynamic_variable":"system__caller_id"},
    "call_secs":{"type":"string","dynamic_variable":"system__call_duration_secs"},
    "village_id":{"type":"string","dynamic_variable":"village_id"}}}},
 "assignments":[{"dynamic_variable":"gate_decision","value_path":"decision"},{"dynamic_variable":"say_text","value_path":"say"}]}
```

Other system variables: `system__called_number`, `system__call_sid`, `system__time_utc`, `system__agent_turns`, and `system__conversation_history` (full JSON history, evaluated at the moment it is referenced).

**Authentication.** Options:
- A secret header (workspace secret or `env_var_label`).
- Bearer, Basic or OAuth2 auth connections.
- A `secret__` dynamic variable: it is never sent to the LLM, and is redacted in transcripts.

**Timeouts.** `response_timeout_secs` defaults to 20. The API allows 1–120 (the skill says 5–120); MCP tools allow 5–300. Return within about 2 s for good UX.

**Blocking vs non-blocking (`execution_mode`):**
- `immediate` (the default) blocks the turn on the result.
- `post_tool_speech` runs the tool after the agent finishes speaking.
- `async` runs in the background. Use it for `ask_family` fan-out and escalations.

**Filling the wait:**
- `pre_tool_speech` is auto, force or off.
- `tool_call_sound` is typing or elevator1–4, with `tool_call_sound_behavior` auto or always.
- Soft timeout fillers: `turn.soft_timeout_config` (`timeout_seconds` 0.5–8, a `message`, with per-language translation).

**Can the tool dictate exact words?** A normal tool cannot: the LLM paraphrases the `result`.

- **Prompt-only route:** return `{"say": "..."}` and add the system-prompt rule "When a tool returns `say`, speak it verbatim and add nothing." With Claude at temperature 0 this works but isn't guaranteed.
- **Deterministic route:** a **structured (deterministic) procedure**. Its steps are `tool_call(log_dose)` → `branch` with an `expression` condition on `gate_decision` → a `say` step. `say` "says an exact message verbatim" and supports `message_translations: {"es": {"value": "..."}}`.
  - Expression branches read dynamic variables that tool `assignments` filled, so the policy gate in Core decides the branch and the spoken text is fixed.
  - Whether `say` text can interpolate `{{say_text}}` is **[VERIFY]**. If it can't, write one `say` per gate outcome: OK_LOGGED, DOUBLE_DOSE_BLOCKED, UNKNOWN_PILL.
- **Guardrails:** add a `custom` blocking guardrail, "never confirm a dose the tool did not confirm". Leave the `medical_and_legal_information` content category off, or test it: it may block medication talk.

## 4. Setup agent in the browser: client tools and SDK

- **Packages:** `@elevenlabs/react` (re-exports `@elevenlabs/client`) and `@elevenlabs/client` for vanilla JS. Server-side: `@elevenlabs/elevenlabs-js` and Python `elevenlabs` (≥2.60 for procedures). The old `elevenlabs` npm package is deprecated.
- **Private agent flow:**
  1. Set `platform_settings.auth.enable_auth=true`.
  2. Core calls `GET /v1/convai/conversation/token?agent_id=...` for a WebRTC token (Python: `conversations.get_webrtc_token`, which returns token and conversation_id), or `GET /v1/convai/conversation/get-signed-url` for a WebSocket URL that **expires in 15 min**.
  3. The client calls `startSession({conversationToken})` or `startSession({signedUrl})`.
  4. Also add the app's hostname (tunnel or Vercel) to the allowlist (max 10).

```tsx
<ConversationProvider onError={console.error}>
  <Setup/>
</ConversationProvider>
function Setup() {
  useConversationClientTool("render_village_preview", async ({ village_json }) => { setPreview(JSON.parse(village_json)); return { shown: true }; });
  const { startSession } = useConversationControls();
  return <button onClick={async () => startSession({ conversationToken: (await fetch("/api/el-token").then(r => r.json())).token,
    dynamicVariables: { caregiver_name: "Ana" } })}>Describe your family</button>;
}
```

- Client tool definitions need `"type":"client"`. Set `expects_response: true` if the result goes back to the LLM. The timeout is 1–120 s, or -1 to wait forever.
- Make `create_village` a **webhook** tool so Core persists the village and provenance is server-side. Add a client tool to render the live preview.
- `onMessage`/`onUserTranscript` callbacks give a live transcript in the UI.

## 5. Post-call webhooks and real-time data (provenance and Arize)

- **Setup:** workspace setting (overridable per agent). There are 3 types: `post_call_transcription`, `post_call_audio` (base64 MP3, chunked), and `call_initiation_failure`.
- **Auth:** HMAC via the `ElevenLabs-Signature` header. Python: `client.webhooks.construct_event(rawBody=..., sig_header=..., secret=...)`. It checks the timestamp and returns a dict. Must return 200 (it retries, and is auto-disabled after 10 consecutive failures).
- **Payload:** `data.transcript[]` has, per turn, `role`, `message`, `time_in_call_secs` (**start offset per turn, in whole seconds; no word-level timing**), `tool_calls`, `tool_results`, and `conversation_turn_metrics` (LLM TTFB, time to first sentence).
- Also in the payload:
  - `metadata`: start_time_unix_secs, call_duration_secs, cost, termination_reason, phone details.
  - `analysis`: evaluation_criteria_results, data_collection_results, call_successful, transcript_summary.
  - `conversation_initiation_client_data.dynamic_variables`, plus `version_id` and `branch_id`.
- **Provenance span** = `(conversation_id, turn_index, time_in_call_secs, start_time_unix_secs + offset)`. If you need sub-second spans, run Scribe v2 (batch STT, word timestamps) on the `post_call_audio` MP3, or use Forced Alignment.
- **Real-time:**
  - The monitor WebSocket `wss://.../v1/convai/conversations/{id}/monitor` is **enterprise-only**.
  - Practical substitute: the server-tool request itself. Pass `utterance` (verbatim) + `system__call_duration_secs`, and write the provisional memory record at tool time.
  - Reconcile it when the post-call transcript arrives.
  - Pull a full record any time with `GET /v1/convai/conversations/{id}`.
  - Arize: one trace per conversation_id. Turn spans come from the transcript, with LLM TTFB taken from turn metrics; tool spans come from Core. Map ElevenLabs `evaluation_criteria_results` to Arize annotations.

## 6. Multilingual, voices, turn-taking for an elderly caller

- **One agent, many languages.** Set `agent.language:"es"` (Carmen's primary), and add `language_presets` for `en` (Mom line) and `zh` (block line), each with its own first_message and voice.
- Add `built_in_tools.language_detection` (`{}`). It switches on detected audio language or on request. Keep `only_at_conversation_start` false for code-switching Carmen; set it true for the block line to avoid false switches.
- **TTS:** the default `eleven_v4_turbo` (90+ languages, about 100 ms, audio tags like `[warmly]`). v4 drops the **speed** and **style** sliders and SSML. To slow down: pick a naturally slow voice, prompt for short sentences with pauses ("…"), or use `eleven_multilingual_v2`/`flash_v2_5` with `speed: 0.85` (min 0.7).
- `eleven_v3_conversational` is now "previous generation" (about 280 ms). v4's "native accent handling" means one cloned or designed voice speaks fluent Spanish, English and Mandarin with no accent carry-over: one consistent "Village" voice across languages.
- **Voice:** use Voice Library "language top picks" for a warm Latin-American Spanish voice. Or **Voice Design** a persona, e.g. "warm, unhurried Mexican-American woman in her 50s, soft and reassuring" (works on the free tier too). Set stability around 0.6–0.7 for calm delivery.
- **Turn settings for Carmen:**

```json
"turn": {"turn_eagerness":"patient","turn_timeout":15,"initial_wait_time":5,"silence_end_call_timeout":90,
  "soft_timeout_config":{"timeout_seconds":3,"message":"Mm-hm, un momentito...","use_llm_generated_message":false},
  "interruption_ignore_terms":["ajá","sí","mm","okay"],"transcribe_on_disabled_interruptions":true},
"asr":{"keywords":["Carmen","Marco","lisinopril","metformina","pastilla azul"]},
"conversation":{"max_duration_seconds":600}
```

- Leave interruptions on (allowed), but set `interruption_mode: "disable_during_tool"` on dose tools so gate confirmations play in full.

## 7. Agents as code: CLI, workflows, procedures

- `npm i -g @elevenlabs/cli` (or `brew install elevenlabs/tap/elevenlabs`).
- `elevenlabs agents init` creates `agents.json`, `tools.json`, `tests.json`, plus `agent_configs/`, `tool_configs/` and `test_configs/`.
- Then `elevenlabs agents add "Mom line" --template minimal`, `elevenlabs tools add "log_dose" --type webhook --config-path tool_configs/log_dose.json`, and `elevenlabs agents push [--dry-run]` / `pull`.
- Auth comes from the `ELEVENLABS_API_KEY` env var. `elevenlabs generate-skills` writes SKILL.md files for coding agents.
- Commit these to the Village repo; that is the spec-driven story.
- **Workflows:** node graphs with `override_agent`, `dispatch_tool`, `agent_transfer` and `transfer_to_number` nodes, plus `expression` edges.
- **Procedures:** `free_form` or `deterministic`. They live on a branch: write a draft, then publish by PATCHing the agent. A failed validation returns `400 procedure_validation_failed`.
- **Hosted MCP server** (`elevenlabs.io/docs/_mcp/server`): manage agents from Claude Code.

## 8. Creator plan limits and gotchas

| Plan | Price | Agent minutes | Concurrency |
|---|---|---|---|
| Free | $0 | 15 | 4 |
| Starter | $6 | 75 | 6 |
| **Creator** | **$22 ($11 first month)** | **275** | **10** |
| Pro | $99 | 1,238 | 20 |

- Overage is $0.08/min (Pay-As-You-Go credits are needed to exceed quota). Burst runs to 3× concurrency at 2× price.
- "Telephony is included on every plan." There is no stated per-plan limit on phone numbers, and outbound/batch calling is not plan-gated (Twilio carrier costs are separate).
- LLM costs pass through separately.
- Silences longer than 10 s are billed at a 95% discount, which helps slow speakers.
- **Gotchas:**
  - The default `api_schema.method` is GET, so set POST explicitly.
  - The initiation webhook must return *all* declared dynamic variables, or the call fails.
  - `secret__` values are redacted in post-call data.
  - Batch calls use at most min(50% of workspace concurrency, 70% of agent concurrency).
  - Post-call webhooks arrive after analysis, which takes seconds to tens of seconds, so don't block the demo on them.
  - Cloudflared quick-tunnel URLs change on restart. Use `{{system_env__core_host}}` or a named tunnel.
  - Zero Retention Mode cannot be used with batch calls.

## 9. What would impress a "Best Use of ElevenLabs" judge

1. **Deterministic voice safety:** a structured procedure with a `say` step, driven by the Core policy gate. Demo a live double-dose attempt that the agent refuses, word for word, in Spanish.
2. **Agent Testing in CI:** `tool` tests (Spanish "me tomé la pastilla azul" → `log_dose` with pill=blue) and a `simulation` test with a persona ("forgetful 82-year-old, mixes Spanish/English, tries a second dose"). Use `tool_mock_overrides` to force a gate=BLOCK path. Run them with `POST /v1/convai/agents/{id}/run-tests`, and show the pass rate on a slide.
3. **One designed "Village" voice** across ES/EN/ZH (v4 native accents), plus audio tags for warmth.
4. **Batch calling** for the blackout block. Upload a CSV with a `generator` column → dynamic variables → batch job; results come back via webhooks.
5. **The ElevenLabs stack beyond agents:** Scribe v2 for word-level provenance spans from the call audio, `evaluation_criteria` + `data_collection` (e.g. extract `symptom`, `severity`) feeding Arize, and agents-as-code via the CLI.
6. Optional: `post_call_audio` → a "listen to the moment" link on each memory record in the app.

---

## Recommended decisions for Village

1. **Phone:** an upgraded Twilio account with one US number, imported via API and assigned to the Mom line agent. Reuse the same number for outbound escalations. Fall back to the browser widget if Twilio fails.
2. **Agents:** three agents in the repo via the CLI.
   - `mom-line`: es primary, en preset, Haiku 4.5, patient turns.
   - `setup`: web, Sonnet 5.5, token auth, `create_village` webhook + preview client tool.
   - `village-caller`: outbound escalation + block line, with es/zh presets, language detection, and dynamic variables.
3. **LLM:** native ElevenLabs Claude; Bedrock Claude inside Core. Skip the custom LLM.
4. **Tools:** every webhook gets `conversation_id`, `caller_id`, `call_duration_secs` and a verbatim `utterance` through dynamic-variable or LLM params. Core returns `{decision, say}`, and an `assignments` mapping writes those into dynamic variables.
5. **Exact speech:** a deterministic procedure for "dose reported": tool_call → expression branch on `gate_decision` → `say` with es/en translations. A prompt rule ("speak `say` verbatim") is the fallback.
6. **Provenance:** write at tool time (provisional), then reconcile from `post_call_transcription` (HMAC-verified) keyed by `conversation_id` + `time_in_call_secs`. Arize: one trace per conversation.
7. **Inbound context:** the conversation initiation webhook returns Carmen's schedule and village_id, keyed by `caller_id`.

## Open risks to test tonight

1. **Twilio:** does the trial preamble block inbound calls? Upgrade now to avoid finding out at the demo. Confirm the import succeeds and an inbound call reaches the agent.
2. **Raw webhook body:** log the first request. Is it exactly the schema fields, or an envelope? Does `dynamic_variable` for `system__caller_id` populate (it is empty on web calls)?
3. **`say`:** can it interpolate `{{say_text}}`? Do `assignments` from a tool response feed an `expression` branch in the same turn?
4. **Latency through cloudflared:** measure the round trip and keep tool responses under 1.5 s. Check that `tool_call_sound` plays on PSTN.
5. **Spanish ASR** on slow, quiet elderly speech: check that patient eagerness plus a 15 s turn timeout doesn't cut Carmen off. Check how language detection handles code-switching.
6. **Mandarin** voice quality on v4 Turbo over 8 kHz phone audio.
7. **Post-call webhook delay**, and whether `tool_calls`/`tool_results` show up in the transcript turns.
8. Confirm the exact Claude IDs with `GET /v1/convai/llm/list`, and that the account is on Creator (10 concurrency, 275 min ≈ enough for about 90 demo calls).
9. Confirm `enable_auth` + the token flow work from the generated app's origin (allowlist).
