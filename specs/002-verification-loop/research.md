# Research: FS-2 Verification loop

Sources: `research/elevenlabs.md`, `research/public-url.md`, ElevenLabs `agents` skill (procedures, outbound calls), `contracts/`, `ARCHITECTURE-VALIDATION.md` edges 4–7. Status: ✅ verified · 🟡 docs-checked · 🔴 [VERIFY] with the smoke script that resolves it.

## Decisions
| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| D1 | Native ElevenLabs Claude (`claude-haiku-4-5`) on both phone agents | lowest TTFB on PSTN; backup cascade is automatic | custom LLM via LiteLLM→Bedrock (+200–500 ms, tunnel risk) |
| D2 | Tool body = exactly `request_body_schema`, no envelope; system vars via `dynamic_variable` properties | matches `voice_tools.schema.json` (`req_*` have `additionalProperties: false`) | skill's `{tool_call_id, parameters}` envelope (likely stale) |
| D3 | Verbatim speech by structured procedure, prompt rule as fallback | `say` step "says an exact message verbatim"; gate owns the text | prompt-only (not guaranteed) |
| D4 | Procedures pushed by a small script over the SDK (`procedures.create` → `agents.update`) kept in `agents/procedures/*.json` | the CLI `agents push` syncs agents/tools/tests; procedures live on a branch with drafts and need a publish PATCH | hand-editing in the dashboard (not spec-driven) |
| D5 | In-app prompt primary, outbound call secondary | ARCHITECTURE-VALIDATION §4.2; ring + answer can exceed 30 s | call-only |
| D6 | Blocking `await_verification` with `response_timeout_secs: 35`, Core hold 30 s | 5 s headroom; same safe default on either timeout | async tool + callback turn (no way to interrupt the agent with a result) |
| D7 | One Twilio number (upgraded account), imported via API, inbound → mom-line, outbound → village-caller | `agent_phone_number_id` is per call; trial accounts play a preamble and only reach verified numbers | SIP trunk, second number |
| D8 | Cancel a superseded outbound call through Twilio REST (`Status=completed`), best effort | ElevenLabs has no documented hang-up endpoint for an outbound leg | leaving it ringing (village-caller then gets `outcome: ignored`, harmless) |
| D9 | Unknown caller: init webhook returns the full seven-variable guest set, never non-2xx | a missing variable fails the call; T42 handles money from an unknown caller | 403 from init (drops the call, no incident) |
| D10 | Idempotency key `(conversation_id, tool_call_id)` with fallback `(conversation_id, tool, call_secs)` | no documented system variable for the tool-call id | — |

## Open [VERIFY] items (resolve with the smoke scripts, in this order)
| # | Item | Resolves with | If it fails |
|---|---|---|---|
| R1 | Raw tool body is the bare schema; `system__caller_id`, `system__call_duration_secs`, `system__conversation_id` populate on PSTN (`caller_id` empty on web) | smoke 08 (`$TUNNEL_URL/tools/log`) + smoke 09 `--keep`; one call to the talk-to link and one from the phone | adapt the pydantic parser to the observed envelope; never the contract |
| R2 | `say.message` interpolates `{{say_text}}` filled by a tool `assignments` in the same turn | smoke 09 `--keep`, then `scripts/push_procedures.py --agent $ELEVENLABS_AGENT_ID --procedure dose_report`; call and say "I took my lisinopril" | fallback (a): `tell` + prompt rule + Arize verbatim eval |
| R3 | Expression-condition AST shape for `verification_status == "pending"` | same push; a `400 procedure_validation_failed` returns the offending `path` | `llm` condition "the tool reported status pending" |
| R4 | Does a `tool_call_id` (or any per-call id) appear in the body? | smoke 08 log | D10 fallback key |
| R5 | Twilio: upgraded account, inbound reaches mom-line without a preamble; outbound rings `TEST_CALL_TO` | smoke 09 `--call` after import (quickstart §2) | web-call fallback for Carmen; in-app prompt only for Marco |
| R6 | Cancelling a ringing outbound call via Twilio REST hangs it up within ~2 s | manual: place a call to `TEST_CALL_TO`, cancel from `scripts/cancel_call.py <callSid>` | leave ringing; village-caller's answer is stored `ignored` |
| R7 | `money_core_down` line and `GET /voice/token` accepted into the contract | orchestrator (contract bump 1.0.1) | keep the line only in agent config; web fallback uses the dashboard talk-to link |
| R8 | `ElevenLabs-Signature` verification with `client.webhooks.construct_event` on the exact raw body through Funnel (no body rewrite) | smoke 09 `--keep` + hang up; check Core log `post_call ok` | log the failure, accept transcript only from `GET /v1/convai/conversations/{id}` (pull) |
| R9 | `init` webhook round trip through Funnel < 1 s and returns all seven vars; the agent config declares exactly those seven | smoke 08 (`/health` from cellular) + first phone call to mom-line | keep `today_summary` short; if the call drops, disable "fetch initiation data" and use placeholders |
| R10 | `tool_call_sound` plays on PSTN during the 30 s hold | first real money call | add a `say` filler before `await` ("Quédese conmigo un momentito.") |

R1–R5 can block V1; R6–R10 degrade gracefully.

## Notes carried from edges 4–7
- Round trip via Funnel ≈ 50–100 ms; keep every non-await handler under 1.5 s (ARCHITECTURE-VALIDATION edge 4).
- Holding Carmen 30 s needs a filler: `tool_call_sound` + the hold line itself (edge 5).
- Twilio must be upgraded; the demo never depends on the ring (edge 6).
- Setup agent over WebRTC needs the origin allowlisted and HTTPS mic (edge 7); FS-3 owns the conversation, FS-2 ships the agent shell + `create_village` tool.
