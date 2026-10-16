# Arize AX + Bedrock: capability research for Village

Researched Oct 15 2026. **[V]** means I checked it against installed packages in a scratch venv: arize 8.59.1, arize-otel 0.14.1, arize-ax-cli 0.39.0, openinference-instrumentation 0.1.71, openinference-instrumentation-bedrock 0.1.60, openinference-instrumentation-anthropic 3.0.3, anthropic 1.15.0. **[D]** means the claim comes from docs only. **[?]** means it isn't verified, so test it tonight.

---

## ARIZE

### 1. Tracing setup (Bedrock, manual spans, agent graph, sessions)

**Verdict.** Don't use boto3 Converse. Call Claude through `anthropic.AnthropicBedrockMantle` and trace it with `openinference-instrumentation-anthropic`. Use OITracer decorators for everything that isn't an LLM call.

- **Why not Converse.** Opus 5.5, Sonnet 5.5 and Haiku 5.5 have no ARN-versioned IDs. Per the Anthropic docs they're served by the Mantle endpoint (`bedrock-mantle.{region}.api.aws/anthropic/v1/messages`) and by InvokeModel on bedrock-runtime. Converse is documented only for the legacy models (Opus 4.6 and older), and Claude Code itself says it "does not support the Converse API" [D].
- **What the Bedrock instrumentor would capture [V].** It wraps `converse`, `converse_stream`, `invoke_model`, `invoke_model_with_response_stream`, `apply_guardrail` and `invoke_agent` (Converse needs botocore >= 1.34.116). For Converse it records `toolConfig` as `llm.tools`, `toolUse` and `toolResult` blocks as tool calls, streamed `toolUse` deltas re-assembled into JSON, and cache-read/cache-write tokens. So Converse with tools and streaming *would* be traced, if the 5.5 models answer on Converse at all [?].
- **Anthropic instrumentor [V].** It wraps the `Messages` class methods: `create`, `stream`, `parse` and the `beta.*` variants. `AnthropicBedrockMantle().messages` is that same class. I ran a call through it and got a span `messages.create`, kind=LLM, `llm.model_name=anthropic.claude-sonnet-5-5`, `llm.provider=anthropic`, status ERROR on the 403. So the Mantle client traces with no extra work.
- **Span kinds available as decorators [V].** `@tracer.agent`, `.chain`, `.tool`, `.guardrail`, `.evaluator`, `.decision`, `.retriever`, `.reranker`, `.llm`. GUARDRAIL and EVALUATOR are real decorators in 0.1.71, even though the skill doc says they must be hand-rolled.
- **Context managers [V].** `using_session`, `using_user`, `using_metadata`, `using_tags`, `using_prompt_template`, and `using_attributes` (which combines them).
- **Agent graph [D].** The Agent Trajectory view needs `graph.node.id` on every node you want drawn, plus `graph.node.parent_id` (recommended; otherwise it's inferred from the span hierarchy).

```python
# pip install "arize-otel" "openinference-instrumentation-anthropic" "anthropic[bedrock]"
import os, json
from arize.otel import register
from openinference.instrumentation import OITracer, TraceConfig, using_attributes, using_prompt_template
from openinference.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry import trace
from anthropic import AnthropicBedrockMantle, Anthropic

tp = register(space_id=os.environ["ARIZE_SPACE_ID"], api_key=os.environ["ARIZE_API_KEY"],
              project_name="village")             # endpoint defaults to https://otlp.arize.com/v1 (gRPC)
AnthropicInstrumentor().instrument(tracer_provider=tp)
tracer = OITracer(tp.get_tracer("village"), config=TraceConfig())

def llm():   # Bedrock first, Anthropic API fallback; both are traced by the same instrumentor
    if os.getenv("USE_BEDROCK", "1") == "1":
        return AnthropicBedrockMantle(aws_region=os.getenv("AWS_REGION", "us-east-1")), "anthropic.claude-sonnet-5-5"
    return Anthropic(), "claude-sonnet-5-5"

def node(node_id, parent=None):                    # agent-graph attrs on the current span
    s = trace.get_current_span()
    s.set_attribute("graph.node.id", node_id)
    if parent: s.set_attribute("graph.node.parent_id", parent)

@tracer.guardrail(name="policy_gate")              # GUARDRAIL span; args become input, return becomes output, status set
def policy_gate(action: dict) -> dict:
    node("policy_gate", "core")
    verdict = evaluate_rules(action)                 # deterministic
    trace.get_current_span().set_attribute("metadata", json.dumps({"rule_id": verdict["rule"], "decision": verdict["decision"]}))
    return verdict                                   # {"decision": "allow|deny|escalate", "rule": ..., "reason": ...}

@tracer.tool(name="daytona_build", description="Build+test generated app in Daytona sandbox")
def daytona_build(spec_json: str) -> dict:
    node("daytona_build", "builder")
    return run_in_sandbox(spec_json)                 # {"ok": bool, "tests_passed": n, "log_tail": ...}

@tracer.agent(name="rumor_checker")
def rumor_check(claim: str) -> dict:
    node("rumor_checker", "core")
    return anchor_check(claim)                       # wrap the Anchor call in @tracer.tool inside it

@tracer.agent(name="builder")
def build_village(description: str, prompt) -> dict:
    node("builder", "core")
    client, model = llm()
    with using_prompt_template(template=prompt.text, variables={"description": description},
                               version=prompt.version_id):   # ties the LLM span to its Prompt Hub version
        msg = client.messages.create(model=model, max_tokens=16000, system=prompt.text,
                                     messages=[{"role": "user", "content": description}],
                                     tools=[VILLAGE_SPEC_TOOL])   # schema-in-tool; see Bedrock section 9
    spec = extract_spec(msg)
    return {"spec": spec, "build": daytona_build(json.dumps(spec))}

# Request handler: one session per village, user per member
@tracer.chain(name="core.handle")
def handle(req):
    node("core")
    with using_attributes(session_id=f"village-{req.village_id}", user_id=req.member_id,
                          metadata={"route": req.route}, tags=["village"]):
        ...
```

Notes:
- Server tools (log_dose etc.) are called by the ElevenLabs agents over HTTP. Decorate the FastAPI handler body with `@tracer.tool` and open `using_attributes(session_id=..., user_id=...)` inside the handler. ElevenLabs passes conversation/user IDs in its tool payload; map those to `village_id` and `member_id`.
- Call `tp.force_flush()` in scripts. Spans show up in the UI about 30 s after export [D: session-tracking ref].

### 2. Online evals (continuous tasks)

**Verdict.** You can set one up quickly with `ax`. Continuous tasks run **every ~2 min on new spans** [D: arize.com/docs/ax/evaluate/online-evals]. One caveat: the skill warns that the eval index can lag **1-2 h** for *backfill* `trigger-run`, so a window ending "now" scores 0 spans [D]. Don't build the live demo around waiting for an online eval to land; pre-warm it this afternoon.

Judge provider options:
- **Anthropic API key (fastest).** `ax ai-integrations create --name anthropic --provider ANTHROPIC --api-key $ANTHROPIC_API_KEY --enable-default-models`. AI integrations are account-scoped, so the command takes no `--space` [D].
- **Bedrock.** The integration supports three auth modes: an IAM role ARN that Arize assumes (trust policy with Arize's principal + external ID), a **Bedrock API key (bearer)**, or custom headers [D]. The CLI form is `--provider AWS_BEDROCK --provider-metadata '{"role_arn": ...}'`. Lab accounts probably can't create the trust relationship, and bearer keys expire with the session. Treat Bedrock-as-judge as optional.
- **No provider at all.** A *code evaluator* (deterministic, runs server-side) or a *remote evaluator* (your HTTPS endpoint; Arize POSTs `{metadata, input:{...}}` and expects `{label, score, explanation}` back). A remote evaluator can call Bedrock with your own creds, but it needs a public URL (cloudflared tunnel) [D].
- **Most reliable fallback: log evals yourself [V].** Run the judge in-process with Bedrock, then call `ArizeClient().spans.update_evaluations(space_id=..., project_name="village", dataframe=df)`. The dataframe has `context.span_id` plus `eval.<name>.label|score|explanation`. There's no index lag on the task side, and it can be filtered the same way afterwards [?: time-to-visible].

CLI flow (current ax 0.39 syntax [V]; the skill docs use an older `create-template-evaluator` form):

```bash
export ARIZE_API_KEY=...; ax profiles create --api-key $ARIZE_API_KEY
ax evaluators create-evaluator template --name spec_coverage --space SPACE \
  --commit-message v1 --template-name spec_coverage --ai-integration-id INT_ID \
  --model-name claude-sonnet-5-5 --include-explanations --use-function-calling \
  --classification-choices '{"covered":1,"missing":0}' --direction MAXIMIZE \
  --template 'Group description: {input}
VillageSpec JSON: {output}
Does the spec cover every member, medication/schedule and escalation contact mentioned?
Respond with exactly one of these labels: covered, missing'
ax tasks create-evaluation --name spec_coverage_live --task-type TEMPLATE_EVALUATION \
  --project village --space SPACE \
  --evaluators '[{"evaluator_id":"EVAL_ID","column_mappings":{"input":"attributes.input.value","output":"attributes.output.value"}}]' \
  --query-filter "name = 'builder'" --is-continuous --sampling-rate 1.0
```

- Filter on `attributes.openinference.span.kind`, never on `span_kind`. Custom `metadata.*` attributes may not be indexed.
- Results appear as `eval.spec_coverage.label` on spans.
- Code evaluators: `ax evaluators create-evaluator code`. They must subclass `CodeEvaluator`, imported from `arize.experimental.datasets.experiments.evaluators.base`; put imports in `--imports`; give `evaluate()` named params (`**kwargs` alone gives 0 variables, and the run silently cancels at 0/0/0) [D: skill].

### 3. Datasets + experiments from Python [V signatures]

```python
from arize import ArizeClient
from arize.experiments.evaluators.types import EvaluationResult
import json, jsonschema
ax = ArizeClient()                                    # reads ARIZE_API_KEY
ax.datasets.create(name="village-descriptions", space=SPACE,
                   examples=[{"description": d, "expected_members": n} for d, n in ROWS])  # 20 rows

def task(dataset_row):                               # bound params: input|output|metadata|dataset_row
    return json.dumps(build_spec_only(dataset_row["description"], prompt_label=PROMPT_LABEL))

def spec_valid(output) -> EvaluationResult:          # code eval: runs locally
    try: jsonschema.validate(json.loads(output), VILLAGE_SPEC_SCHEMA); return EvaluationResult(score=1, label="valid")
    except Exception as e: return EvaluationResult(score=0, label="invalid", explanation=str(e)[:300])

def coverage(output, dataset_row) -> EvaluationResult:   # LLM judge: runs locally on Bedrock, no Arize integration needed
    verdict = bedrock_judge(dataset_row["description"], output)   # returns {"label","explanation"}
    return EvaluationResult(score=1 if verdict["label"] == "covered" else 0, **verdict)

for label in ("v1", "v2"):
    PROMPT_LABEL = label
    exp, df = ax.experiments.run(name=f"builder-{label}", dataset="village-descriptions", space=SPACE,
                                 task=task, evaluators=[spec_valid, coverage], concurrency=4, timeout=180)
```

To compare, open the dataset's **Experiments** tab, select both runs and click **Compare** [D]. Use `dry_run=True` first, which runs 10 rows and uploads nothing. The run also emits per-example traces to an experiment project.

### 4. Prompt Hub fetch-by-label and live reload [V]

**Verdict: yes.** Labels are mutable pointers. The SDK has `prompts.get(prompt=, space=, label="production")`, `create_version(...)` and `set_labels(version_id=, labels=[...])`. `set_labels` **replaces** all labels on that version. The endpoints are marked BETA; they log a warning but work.

```python
from arize._generated.api_client import LLMMessageRequest, InputVariableFormat, LlmProvider
_cache = {"t": 0}
def get_builder_prompt(label="production", ttl=10):
    if time.time() - _cache["t"] > ttl:
        p = ax.prompts.get(prompt="village-builder", space=SPACE, label=label)
        _cache.update(t=time.time(), text=next(m.content for m in p.version.messages if m.role == "SYSTEM"),
                      version_id=p.version.id)
    return _cache

# self-improvement loop pushes v2
v = ax.prompts.create_version(prompt="village-builder", space=SPACE, commit_message="fix: missing escalation contacts",
        input_variable_format=InputVariableFormat.F_STRING, provider=LlmProvider.AWS_BEDROCK,
        model="anthropic.claude-sonnet-5-5", messages=[LLMMessageRequest(role="SYSTEM", content=new_text)])
ax.prompts.set_labels(version_id=v.id, labels=["production"])
```

The CLI equivalents are `ax prompts get village-builder --label production` and `ax prompts set-version-labels prv_x --label production`.

For push instead of polling, `ax webhooks subscriptions create --source-type PROMPT --event PROMPT_VERSION_LABELED` POSTs to an HTTPS URL [V CLI]. That needs a tunnel, so a 10 s TTL poll is simpler. Messages `role` must be `SYSTEM|USER|ASSISTANT|TOOL`, uppercase [V].

Prompt Learning (`PromptLearningOptimizer` from github.com/Arize-ai/prompt-learning) is OpenAI-keyed in the docs [D]. Use the skill's meta-prompt with Claude instead (section 5).

### 5. MCP and `ax` for the agent's self-read

- **MCP [D].** Hosted at `https://api.arize.com/mcp`, auth `Authorization: Bearer <ARIZE_API_KEY>`. It's **read-only and Alpha**. Tools include `list_spans`, `list_traces`, `get_prompt_label`, `get_prompt_version`, `list_task_runs`, `search_experiment_runs` and `list_evaluators`.
  - Claude Code: `claude mcp add-json arize-ax --scope project '{"type":"http","url":"https://api.arize.com/mcp","headers":{"Authorization":"Bearer ${ARIZE_API_KEY}"}}'`
  - The Anthropic MCP connector isn't available on Bedrock, so an in-app Bedrock agent can't attach the MCP server natively. Either run the "improver" with the Claude Agent SDK (MCP plus `ax` via Bash), or call the SDK directly.
- **Read failures (SDK).** `ax.spans.list(project="village", space=SPACE, filter="eval.spec_coverage.label = 'missing'", limit=20)`. CLI: `ax spans export village --filter "eval.spec_coverage.label = 'missing'" -l 20 --stdout`. The `eval.` prefix comes from the evaluator column naming, but the exact filter grammar is unverified [?]; the skill uses `annotation.<name>.label` for human labels.
- **Pattern.** Read through MCP or the SDK, write through the SDK or `ax`. That matches Arize's own guidance: "agent reads through MCP tools and acts through the CLI" [D]. It's also what the judge's rubric asks for ("meaningful tracing + MCP").

### 6. Signal and Alyx [D]

- **Signal.** Project → Signal tab → **Enable Signal**. The default cadence is every 6 h, configurable down to a 3 h minimum. Free gets 10 issues/month, Pro gets 25. No repo or fix PRs below Enterprise. **Time to first result is hours**, so enable it *now* on a project with seeded failing traces, or don't count on it. It shows an issue overview, evidence traces and a proposed fix, with a "Create Evaluator" button.
- **Alyx.** On by default (Cmd+L), runs on an Arize-managed model, needs no setup. It can create evaluators, run experiment comparisons, and answer "What issues has Signal found?". Good for a 10 s on-stage cameo: "@village find traces where policy_gate denied and summarize".

### 7. Guardrails [D, V]

Arize Guards are Guardrails-AI validators: `ArizeDatasetEmbeddings` (embedding similarity to bad examples) and a RAG LLM judge. They're designed around OpenAI and add real latency. **Skip them.**

Model the deterministic policy gate as a GUARDRAIL span with `@tracer.guardrail` [V]. Put the decision, rule_id and reason in output/metadata, and set an ERROR status or a label when it blocks. If you ever call Bedrock Guardrails `apply_guardrail` through boto3, the Bedrock instrumentor traces it automatically [V].

Add a **code evaluator** that checks the "gate-consistency" invariant: on `name='policy_gate'` spans, the output decision must match the rule table. That gives you an eval-on-trace that is fully deterministic.

### 8. Free vs Pro [D: pricing page]

| | Free | Pro ($50/mo; coupon HackSprintNYC26) |
|---|---|---|
| Spans | 25k/mo | 50k/mo |
| Retention | 15 d | 30 d |
| Storage | 1 GB | 10 GB |
| Evals, experiments, datasets, prompts, playground, Alyx | unlimited | unlimited |
| Signal issues | 10/mo | 25/mo |

Neither tier allows a custom AI provider for Signal; that's Enterprise only. Free is enough for the demo. Apply the coupon only if span volume or Signal count becomes a problem.

---

## BEDROCK

### 9. Models and features (Claude in Amazon Bedrock / Mantle) [D: platform.claude.com]

**Model IDs and access.**

| Model | Mantle ID | Access |
|---|---|---|
| Opus 5.5 | `anthropic.claude-opus-5-5` | "See Access", i.e. account-gated |
| Sonnet 5.5 | `anthropic.claude-sonnet-5-5` | "See Access", i.e. account-gated |
| Haiku 5.5 | `anthropic.claude-haiku-5-5` | "See Access", i.e. account-gated |
| Sonnet 5 | `anthropic.claude-sonnet-5` | Open to all Bedrock customers |
| Opus 4.8 | `anthropic.claude-opus-4-8` | Open |
| Haiku 4.5 | `anthropic.claude-haiku-4-5` | Open |
| Fable 5.1 | `anthropic.claude-fable-5-1` | Open |

- **No `us.`/`global.` prefix on Mantle.** Global vs regional is an endpoint type; regional costs 10% more.
- **On the InvokeModel API,** Claude Code uses inference profiles such as `us.anthropic.claude-opus-5-5` or `global.anthropic.claude-opus-5-5`. Use the `AnthropicBedrock` legacy client for that path.
- **Regions.** us-east-1, us-east-2 and us-west-2 support Global, US and in-region.
- **Quota.** 2M input TPM by default.

**Features on Mantle.**

| Supported | Not supported |
|---|---|
| Messages API, SSE streaming | Structured outputs (`output_config.format` / `messages.parse`) |
| Tool use | Batches |
| Prompt caching (explicit breakpoints) | Files API |
| Thinking (adaptive; effort via `output_config.effort`) | Web search, code execution |
| Citations | MCP connector |
| | Server-side `fallbacks` |

Structured outputs *is* listed as supported on the legacy Invoke path for some models. For the VillageSpec, define it as a tool's `input_schema`, set `tool_choice: auto` (forced `any`/`tool` returns a 400 on Opus 5.5 and Sonnet 5.5), add a prompt instruction "call emit_village_spec", then validate with jsonschema/pydantic and retry once with the error as a `tool_result` with `is_error`. Try `strict: true` on the tool [?]; drop it if it 400s.

**Thinking.**
- Opus 5.5: thinking can't be disabled (`disabled` or `budget_tokens` returns 400). Effort defaults to `medium`.
- Sonnet 5.5: to turn thinking off, use `{"type":"between_tools"}`. Effort defaults to `high`.

Use `output_config={"effort":"low"}` for the voice server-tool paths.

**Caching.** Put `cache_control: {"type":"ephemeral"}` on the system block. The legacy Bedrock path rejects top-level automatic caching. Verify with `usage.cache_read_input_tokens`.

**Clients.**
- `AnthropicBedrockMantle(aws_region=...)` uses SigV4 from the standard AWS chain, including `AWS_SESSION_TOKEN`, or `api_key=<bearer>`.
- `AnthropicBedrock` is the legacy InvokeModel client. Both have the same `messages.create`/`.stream` surface [V].
- IAM actions: Mantle needs `bedrock-mantle:CreateInference` (plus `CountTokens`); Invoke needs `bedrock:InvokeModel*`.

**Latency [? measure tonight].** Expect Sonnet-class TTFT of roughly 1-2 s and Haiku under 1 s. Opus 5.5 at medium effort with a 2-4k token spec output will take tens of seconds. Use Sonnet 5.5 for the Builder (stream it), Haiku for voice-tool paths, and Sonnet for the judge.

### 10. AWS Workshop Studio lab accounts

- **Credentials.** The event page's "Get AWS CLI credentials" gives `AWS_ACCESS_KEY_ID`/`SECRET`/`SESSION_TOKEN` exports. They're temporary (typically about 1 h, sometimes longer), and the account is destroyed at event end [D: workshop pages; exact TTL ?].
- **Refresh options, in order of preference:**
  1. Ask the organizers whether a long-term Bedrock API key or an IAM user is allowed. A long-term key (`AWS_BEARER_TOKEN_BEDROCK`) survives session expiry. Short-term keys last at most 12 h *and* never outlive the minting session.
  2. Keep creds in `.env.aws` and make Core reconstruct the client on `ExpiredToken`/403: catch the error, re-read the file, rebuild the client. Re-paste fresh creds hourly (a 30 s chore).
  3. Fall back automatically to the Anthropic API on auth errors. Already in the plan; wire it as a single `llm()` factory with a circuit breaker.
- **Model access.** Bedrock now auto-subscribes serverless models on first invoke, but Anthropic still needs the one-time use-case form, and the caller needs `aws-marketplace:Subscribe`. Lab accounts often get this pre-done by organizers or block it with an SCP. The 5.5 models are "See Access"-gated, so in the first 5 minutes run a probe against `anthropic.claude-sonnet-5-5`, `-haiku-5-5` and `-sonnet-5`. If 5.5 returns 403, use **Sonnet 5 / Opus 4.8 / Haiku 4.5 (open)**.
- **Probe:** `aws bedrock list-inference-profiles --region us-east-1 | grep anthropic`, then one `messages.create` per candidate model.

### 11. Claude Agent SDK on Bedrock [D]

It works, because the Agent SDK is the Claude Code harness.

- **Invoke path:** `CLAUDE_CODE_USE_BEDROCK=1`, `AWS_REGION=us-east-1`, plus AWS creds or `AWS_BEARER_TOKEN_BEDROCK`. Optionally `ANTHROPIC_MODEL=us.anthropic.claude-sonnet-5-5` and `ANTHROPIC_DEFAULT_HAIKU_MODEL=...`. The default primary model is `us.anthropic.claude-opus-5-5`.
- **Mantle:** `CLAUDE_CODE_USE_MANTLE=1` with `--model anthropic.claude-sonnet-5-5`. Set both flags to route by ID format.
- **Credential refresh:** the `awsAuthRefresh` / `awsCredentialExport` settings; `CLAUDE_CODE_SKIP_AWS_CRED_CACHE=1` re-resolves the chain on every request.
- **Limits:** no WebSearch on Bedrock, and Invoke only (no Converse).
- **Tracing:** Arize has a dedicated Claude Agent SDK tracing integration (docs_ax_integrations_python-agent-frameworks_claude-agent-sdk).

---

## Recommended decisions for Village

1. **LLM client.** One `llm()` factory: `AnthropicBedrockMantle` (Sonnet 5.5, falling back to Sonnet 5 if 403), then `Anthropic()` on auth failure. Same Messages API, same instrumentor, same tool schema. No boto3, no Converse.
2. **Instrumentation.** `arize-otel` `register()`, `AnthropicInstrumentor`, and OITracer decorators: AGENT (builder, rumor_checker, escalation), TOOL (daytona_build, anchor_check, every ElevenLabs server tool), GUARDRAIL (policy_gate), EVALUATOR (inline self-check), CHAIN (core.handle). Use `graph.node.id`/`parent_id` on every one of them, `session.id=village-<id>`, `user.id=<member>`, and `using_prompt_template(version=...)` on builder calls.
3. **Structured spec.** Tool-schema VillageSpec, jsonschema validation, one repair retry.
4. **Evals.**
   - Code eval `spec_valid` (jsonschema) and code eval `gate_consistency` on GUARDRAIL spans.
   - LLM judge `spec_coverage`, using the Anthropic-API integration for Arize-side online tasks, or Bedrock in-process with results pushed via `spans.update_evaluations`.
   - Same evaluators reused in experiments.
5. **Prompts.** The builder system prompt lives in Prompt Hub (`village-builder`, label `production`) and is fetched with a 10 s TTL. v1 should be deliberately weak (for example, no escalation-contact instruction) so the loop has something to fix.
6. **Dataset.** 20 descriptions, about 5 of which mention escalation contacts or meds that v1 misses.
7. **Enable Signal at setup** (it runs hours later, so it's a bonus). Use Alyx for one on-stage question.

## Demoable Arize self-improvement loop (≤60 s on stage)

Pre-stage: run experiment `builder-v1`, which scores about 60% coverage. Live builder traces carry `eval.spec_coverage=missing` on a few spans, pre-logged.

1. **(0-10 s)** Speak a group description. Core builds the spec and Daytona builds it. Show the Arize trace graph: core → builder → daytona_build, policy_gate as GUARDRAIL, all under one `session.id`.
2. **(10-20 s)** Click "Improve": an `/improve` endpoint runs the **Improver agent** (Claude on Bedrock):
   - (a) reads its own failures via `ax.spans.list(filter="eval.spec_coverage.label = 'missing'")`, or via MCP `list_spans` if it's running on the Agent SDK;
   - (b) pulls the judge explanations and the current prompt with `prompts.get(label="production")`;
   - (c) applies the optimization meta-prompt and proposes a v2 diff, shown on screen.
3. **(20-40 s)** The Improver runs `experiments.run("builder-v2", ...)` on 20 rows with `concurrency=10` (about 15-20 s with Haiku/Sonnet), using the same code eval and judge. Show the Arize Experiments Compare view: v1 60% → v2 95%.
4. **(40-50 s)** Gate on improvement: if v2 beats v1 and `spec_valid` is 100%, call `set_labels(v2, ["production"])`. That gives a promotion with a human-auditable commit message. The Improver's own run is traced as an AGENT span with an EVALUATOR child.
5. **(50-60 s)** Re-speak the same description. The builder picks up v2 within the 10 s TTL. Show the new trace with prompt-template version v2 and `spec_coverage=covered`.

**Fallback if live experiments are too slow:** precompute v2's experiment and show only the label flip plus the re-run.

## Open risks to test tonight

1. Do `anthropic.claude-sonnet-5-5`, `opus-5-5` and `haiku-5-5` answer on Mantle with lab creds? (403 with no action named means the model isn't granted.) Test the Sonnet 5 / Opus 4.8 fallback too.
2. Workshop credential TTL. Does the reconnect-on-expiry path work? Is a long-term Bedrock API key permitted?
3. Is `strict: true` on tools accepted on Mantle? What's the measured TTFT and total time for a full VillageSpec?
4. How long from `spans.update_evaluations` until the evals are visible and filterable via `ax.spans.list(filter="eval.X.label = ...")`? Confirm the filter grammar.
5. How fast does a continuous online task score new spans (the 2 min claim versus the 1-2 h index-lag warning)? Pre-warm it this afternoon.
6. Does the Prompt Hub BETA SDK work end to end (`create_version`, `set_labels`, `get(label=)`)? Check that `PromptWithVersion.version.messages[*].content` is a plain string.
7. Do ElevenLabs server-tool calls carry an ID we can map to `session.id`/`user.id`?
8. Does the MCP server connect, and do `list_spans` filters work? It's Alpha, so have the SDK path as backup.
9. `experiments.run` with concurrency 10 under the Bedrock default quota: watch for 429 throttling.
10. Does Signal's first sweep produce anything before demo time? If not, drop it from the pitch.
