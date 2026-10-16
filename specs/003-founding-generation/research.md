# Research: FS-3 Founding & generation

Sources read in full: `research/generative-ui.md`, `research/arize-bedrock.md`, `prompts/builder_system.md`, `prompts/setup_agent.md`, `contracts/`, `smoke/README.md`.

## Decisions
| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | Blueprint is a separate, smaller tool call (`extract_blueprint`) streamed before the renders | D9 "blueprint first ≤8 s"; the render tool only returns `life_areas` + `profiles` and is 2–4k tokens; streaming people/needs as they are found is the visible "words become structure" beat | One big call (TTFT fine but nothing to show for 20+ s); regex over the description (misses roles/languages) |
| R2 | Partial JSON via `pydantic_core.from_json(allow_partial=True)` on the accumulated `input_json_delta` buffer | No extra dependency; emits a frame each time an array gains a complete item | `partial-json` package; prompting the model to emit JSONL (breaks tool use) |
| R3 | Tools, non-strict, `tool_choice: auto` + "call X exactly once" | Mantle has no structured outputs; forced `tool`/`any` returns 400 on Opus/Sonnet 5.5 (arize-bedrock §9); validation is Core's job anyway | `messages.parse` (unsupported on Mantle); legacy Invoke structured outputs (different client, no instrumentor parity) |
| R4 | One render per role, parallel, `cache_control` on the system block | generative-ui.md recommendation; the prompt + examples (~12k tokens) are shared; parallel cuts wall time to the slowest role | Sequential (3× latency); one call for all roles (output too long, one failure poisons all) |
| R5 | Repair once with `tool_result{is_error}`, then fixture template per role | CLAUDE.md rule 3; FLEET builder specifics; a blank screen is the only unacceptable outcome | Unlimited retries (latency); hand-written minimal view (fixtures already exist and validate) |
| R6 | Role/profile mapping lives in `mapping.py`, not in the prompt | Contract names (`coordinator`/`helper`, `mild_lapses`, `phone|app|both`) differ from the prompt (`family`, `lapses`, `none…high`) and the prompt is frozen for the v1→v2 experiment | Rewriting the prompt (would change the experiment baseline) |
| R7 | Prompt Hub by label with a 10 s TTL poll, local file fallback | arize-bedrock §4 verified SDK; webhooks would need a tunnel | Push webhook (`PROMPT_VERSION_LABELED`); no Hub (loses the improve-loop story) |
| R8 | Ask-why reads only Core-held material and cites ids; citations validated against the material | Principle III and VIII; prevents invented sources; keeps the endpoint read-only | Letting Claude query SurrealDB/Arize live (latency, injection surface) |
| R9 | Draft/active lifecycle enforced in Core (status) and in the gate (R-CONSENT: no outbound before active) | Principle II; EXPERIENCE phase 1 | Prompt-only rule |
| R10 | Block village pre-generated in the V3 window and stored, not generated live | D13: live second family cut; the reveal needs build time + trace id, not a live call | Live generation (risk, time) |

## Open items (owner · how to close)
| # | Item | Close by |
|---|---|---|
| O1 | Are `anthropic.claude-sonnet-5-5` / `haiku-5-5` granted on the lab account? | `uv run smoke/01_llm.py` at 10:00; set `BEDROCK_SONNET_MODEL` fallback if 403 |
| O2 | Does `strict: true` on `render_app` work on Mantle, and does it change TTFT? | `scripts/build_village.py --strict` once; drop on 400 |
| O3 | First-call grammar/compile cost on a new tool schema (cached 24 h per generative-ui.md) | Warm-up call for `extract_blueprint`, `render_app` ×3 roles, `patch_app`, `cite_answer` at 12:30 and again at 13:30 (`scripts/build_village.py --warm`) |
| O4 | Measured TTFT and total per role with the full prompt + examples (research expects Sonnet TTFT 1–2 s; totals tens of seconds at high effort) | `scripts/build_village.py --time` prints per-role TTFT/total and cache-read tokens; copy to `RESULTS.md`; pick `effort` per step |
| O5 | Do three parallel renders throttle (429) under the default 2M TPM? | Same script; `BUILDER_PARALLEL=0` fallback |
| O6 | Prompt Hub `PromptWithVersion.version.messages[*].content` is a plain string; `get(label=)` works end to end | `smoke/07_arize.py` extension or a 5-line probe in `prompts.py --probe` |
| O7 | `HelperAnswer` is in the contract catalog but not in the builder prompt catalog; builder helper views will use CareRota + BigButton while the fixture uses HelperAnswer | Orchestrator decision: add HelperAnswer to the prompt (both v1 and v2) or accept the difference; template keeps HelperAnswer |
| O8 | Structured blueprint frame (`control{kind: blueprint}`) vs text-only reasoning frames | Orchestrator (contracts); V2 works with text frames + control snapshot |
| O9 | Does the setup agent send `conversation_id`/`caller_id` so `session.id`/`user.id` can be set on the webhook span? | `smoke/09_elevenlabs.py` log at `$TUNNEL_URL/tools/log` |
| O11 | Chat (D16): is `VillageChat` inserted by Core after render (config) or asked of the model (prompt)? Plan says Core inserts; the v1/v2 prompts stay unchanged so the experiment baseline holds | Orchestrator confirms; if the prompt must mention it, it goes in a v3 delta after the experiment |
| O12 | V4 change-request classification: Haiku `classify_intent` accuracy on 6 sample utterances; false "change" must never skip the Proposal → leader approval path (code-enforced) | T024 tests |
| O10 | Voice `create_village` must answer in ≤2 s: confirm background-task pattern survives uvicorn reload and that `say` is a fixed line (never generated) | Route test with a slow fake builder |
