# Sponsor audit: what we actually use, what judges expect, and the cheapest "wow" left (Oct 16, read-only)

Sources: `research/*.md` (Recommended decisions / Open risks), `docs/SPONSOR-MAXIMIZE.md`, `SPONSORS.md`, `RESULTS.md`, the code listed under each sponsor, and greps of the raw vendor docs in `~/village-prep/docs/`. Every API named under (c) was found in those docs or is already called in our code. Anything unverified is marked as unverified. The 14:00 rule from SPONSOR-MAXIMIZE still applies: anything that touches the demo path goes behind a flag or waits.

---

## Daytona ($1,000)

**(a) Used today**
- `CreateSandboxFromImageParams(image=…, auto_stop_interval=0, labels=…)`, with a fallback to `CreateSandboxFromSnapshotParams` (`core/release/daytona_svc.py:80-108`). Snapshot creation is FORBIDDEN on our tier (RESULTS #04), so image sandboxes do the work.
- `sb.fs.upload_files`, `sb.process.exec` (npm install, vite build, vitest), and `sb.fs.download_file` for `vitest.json` and `dist.tgz` (`daytona_svc.py:119-200`).
- `process.create_session` + `execute_session_command` for `vite preview`, and `create_signed_preview_url` as Anchor's target (`daytona_svc.py:227-240`).
- Pre-warm and keepalive (`core/release/warm.py`). Measured: 29.7 s cold, 15.0 s warm. The caught-and-fixed contrast failure (r3 → r4) and a second village in 13.4 s are in RESULTS.

**(b) Judges expect, we don't use**
- Snapshots (blocked by our tier; say so, don't hide it).
- Streamed logs (`get_session_command_logs_async`): today the build logs are invisible.
- Webhooks for sandbox state.
- Agent-in-sandbox / `code_run` for model code (deliberately skipped; egress is blocked, RESULTS #02).

**(c) ≤30-min wow, ranked by impact per minute**
1. **Sandbox id + labels + test count on the receipt** (~10 min). We already have the sandbox, the labels and `vitest.json`. Render "Built in Daytona sandbox `<id>` · 33/33 floor tests · build 2.1 s". *Screen:* receipt + Devpost. *Risk:* low, display only.
2. **Devpost screenshot of the Daytona dashboard** filtered by our `labels`, showing one sandbox per release (~5 min). *Screen:* Devpost. *Risk:* none.
3. **Live build log tail in the Control Room** via `sandbox.process.get_session_command_logs_async(session, cmd_id, on_stdout, on_stderr)` (confirmed in `daytona-llms-full.txt` ~L20630). This needs the build moved from `process.exec` to `execute_session_command(run_async=True)` (~30 min). *Screen:* Control Room release strip. *Risk:* high. It changes the build path that is measured and working, so only do it behind a flag.

**(d) Table line:** "Every version of every family's app is AI-written, and none of it reaches a phone until a Daytona sandbox has built it and passed 33 floor tests. You can see one we caught failing contrast and fixed in 15 seconds."

---

## Anchor ($500)

**(a) Used today**
- `sessions.create_session(browser={"viewport": 390×844}, session={"tags":["village-release"], "recording":{"active":True}})` (`core/release/anchor_qa.py:85-91`).
- Playwright `connect_over_cdp` click-through plus a full-page `screenshot` per release (`anchor_qa.py:131-140`), and `delete_session` in cleanup (`:98`).
- `live_view_url` goes into the receipt evidence **labelled "recording"** (`core/release/pipeline.py:259-260`). Measured QA: 5.2 s warm.
- During smoke tests we also exercised Web Unlocker, `agent.task` and NWS/cooling-center fetches (RESULTS #05), but they are not in the product path.

**(b) Judges expect, we don't use**
- **The recording MP4.** We turn recording on and never fetch it. The receipt "recording" link is a live-view URL, which stops working once the session is deleted. That is a real gap.
- The live view embedded where people can watch it (no `<iframe>` exists in the UI; the only grep hits are specs).
- Automation tasks, profiles/identities, webhooks.

**(c) ≤30-min wow**
1. **Fetch the MP4 and link it on the receipt.** Call `anchor_client.recordings.fetch_primary_recording(session_id)` (confirmed, `anchor-llms-full.txt` L9454 / L23386) after `delete_session`, save it under the release artifacts, and swap the evidence entry from the live-view URL to the MP4 (~20 min). *Screen:* receipt + Devpost video. *Risk:* the recording may take 30–60 s to become available after delete (anchor.md open risk 7). Fetch it in the background and don't block the release.
2. **Live view iframe in the Control Room during the anchor_qa stage**, with `style="pointer-events:none"` (confirmed, docs ~L804-830). It needs `keep_session=True` until the stage ends (~20 min). *Screen:* Control Room. *Risk:* medium. The release only takes ~5 s, so the frame could be blank on stage. Iframing from our origin is also unverified (anchor.md risk 4).
3. **Receipt names the three taps** (free copy change, from SPONSOR-MAXIMIZE). *Screen:* receipt. *Risk:* none.

**(d) Table line:** "Before any rebuilt app reaches Carmen's phone, an Anchor browser opens it at her exact screen size and taps through it. The recording is the evidence on the receipt."

---

## Arize ($500)

**(a) Used today**
- `arize.otel.register` + `AnthropicInstrumentor` (`core/obs/tracing.py:43-86`).
- Every span has `openinference.span.kind` (AGENT/TOOL/GUARDRAIL/CHAIN/EVALUATOR/LLM/RETRIEVER), `session.id=village-<id>`, `graph.node.id` and `graph.node.parent_id` (`tracing.py:28,165-170`).
- `client.spans.update_evaluations` for the session eval (`possible_fraud` 0.95) and the release evals (`evals/arize_io.py:31`, `evals/session_eval.py`).
- Dataset `village-scam-eval` + experiment `scam-model-20261016T153959Z`: 30/30 caught, 0/20 false alarms (`evals/arize_experiment.py`, `evals/scam_experiment.py`).

**(b) Judges expect, we don't use**
- **Human-in-the-loop annotation.** Ana's "approve" is the human approval in their detect → investigate → fix → verify thesis, but it never reaches Arize.
- The agent reading Arize back (traces/evals queried via `ax.spans.list` or MCP) to justify a proposal. Today the proposal cites our own detector, not Arize.
- Prompt Hub and online evals / Signal (deliberately skipped).

**(c) ≤30-min wow**
1. **Write Ana's approval as an annotation on the proposal span.** Annotation configs and queues exist in the v8 Python client (`arize-llms.txt` L342-343). The `arize-annotation` skill names `update_annotations`; the exact signature is unverified, so check it before coding. Create one categorical config `human_approval` (approved/rejected) and write it from the approve route (~25 min). *Screen:* Arize trace view (show it on the Control Room laptop) + Devpost screenshot. *Risk:* medium. The span id has to be at hand, and indexing can lag (arize-bedrock.md risk 4). Pre-capture a screenshot.
2. **Proposal card cites the Arize eval it used** ("eval `scam_pattern` = flagged · session village-v_reyes") (~15 min, from SPONSOR-MAXIMIZE). *Screen:* Ana's phone + Control Room. *Risk:* low if it shows the local value we already pushed. Don't claim a live Arize read we don't do.
3. **Devpost screenshots**: the trace graph (AGENT → TOOL daytona_build ✗ → LLM → TOOL ✓) and the experiment view (~5 min). *Risk:* none.

**(d) Table line:** "Arize is the agent's senses. A session eval flagged the scam call, the rebuild was scored against our 50-case experiment (30/30, 0 false alarms), and a human approved it before anything shipped."

---

## SurrealDB ($500)

**(a) Used today**
- **Cloud:** `signin` + `query` (`core/db.py:128,153`) and `live(` LIVE SELECT pushes to every phone (`core/live.py:45`). Measured p50 22 ms insert→notify; ~130 ms from tool call to the last phone.
- **Agent Memory** (`core/memory/client.py`): `POST /scopes`, `POST /facts` with `observed_at` and provenance labels (`src=`, `secs=`, `url=`, `agent=`, `village=`), `GET /entities/{type}/{name}` (Fact view/history), `GET /uncertainty` + `POST /uncertainty/{id}/resolve`, `POST /query` (incl. `asOf`), `POST /scopes/forget`, plus an outbox.
- Measured: lisinopril 5 → 10 mg supersession; asOf 2026-09-15 returns 5 mg.

**(b) Judges expect, we don't use**
- **"Retrieval traced to source" as an on-screen artifact.** `GET /traces/{trace_id}` exists (`surreal-agent-memory-agents.md` L92, L210), but we never call it.
- Visible proof that memory is **shared across more than one agent**. The `agent=` label is written but never displayed.
- Graph relations (`RELATE` / `covers` edges) in Surrealist. They are in the research data model, not in code.

**(c) ≤30-min wow**
1. **"Written by" chips on the Fact card**, read from the `agent=` label on each fact (mom-line / builder / verifier) (~15 min). *Screen:* Ana's phone (Fact view). *Risk:* low, since labels are already written. Check that the history payload returns labels.
2. **"Why this answer" on recall**: take `traceId` from the `/query` response, call `GET /traces/{id}`, and show `resolutionTier` + the source of the top candidate (~25 min). *Screen:* Control Room / "Ask Village why". *Risk:* medium. Query takes ~3.7 s, so pre-run it and display the cached result.
3. **Devpost**: their six phrases verbatim, each mapped to a code path, plus screenshots of the LIVE SELECT and the 5 → 10 mg history (~5 min). *Risk:* none.

**(d) Table line:** "Carmen's dose went from 5 to 10 mg on Oct 3. Village keeps both, each with the call and second it came from, every agent reads the same memory, and SurrealDB LIVE pushes the change to every phone in about 20 ms."

---

## ElevenLabs (Scale tier)

**(a) Used today**
- Three agents (`agents/agents.json`: mom-line, village-caller, setup) with `first_message`, `language_presets`, `language_detection`, `dynamic_variables`, `turn_eagerness`, `guardrails` and `end_call` (`agents/agent_configs/*.json`).
- 11 server tools (`agents/tool_configs/`, e.g. `report_money_request`, `await_verification`, `screen_caller`).
- Procedures with `tool_call` → `say {{say_text}}` → expression `branch` (`agents/procedures/money_check.json`).
- Init webhook and HMAC-verified post-call webhook (`core/voice/init_hook.py`, `core/voice/post_call.py`), Twilio outbound `/v1/convai/twilio/outbound-call` (`core/voice/outbound.py:61`), live captions polling `GET /v1/convai/conversations/{id}` (`core/voice/captions.py`), and TTS for founding audio.
- Live call measured: refusal at 0:31, 109 s.

**(b) Judges expect, we don't use**
- **Success evaluation criteria and Data collection** on our agents (docs L210-211). No `criteria`/`evaluation` block exists in the configs. The "Successful" in SPONSOR-MAXIMIZE is the platform default.
- Voicemail detection on village-caller outbound (docs L132), and Workflows (we use procedures instead).

**(c) ≤30-min wow**
1. **Add evaluation criteria + data collection to mom-line.** Criteria: "caller did not send money", "AI disclosed". Data fields: `money_amount`, `requester_claimed_identity`, `verification_result`. Push with the CLI (~15 min). They show up in the conversation Analysis tab and in the post-call webhook we already verify. *Screen:* Devpost screenshot of the Analysis tab; Control Room if we surface the post-call payload. *Risk:* medium. It edits the live agent, so do it before 14:00 and re-run one call. Exact JSON field names are unverified in our greps; check them in the Success-evaluation page.
2. **Voicemail detection on village-caller** (system tool, ~10 min). *Screen:* none on stage, Devpost only. *Risk:* low impact, so skip unless the time is free.
3. **Devpost transcript screenshot** with tool calls and timings (free).

**(d) Table line:** "Carmen just calls her number. The agent screens the money request, checks with Marco live through a server tool, and says a scripted Spanish refusal that comes from our gate, not from the model."

---

## AWS Bedrock ($75 credits)

**(a) Used today**
- `anthropic.AnthropicBedrockMantle(aws_region=…)`, with role routing: watcher/verifier/explainer on Haiku (`core/llm.py:30-67`). Only `anthropic.claude-haiku-4-5` answers on the lab account (RESULTS #01).
- That covers scam extraction (30/30), consider_options (5.2 s), and captions/evals. Sonnet 5.5 for Founder/Builder comes via the Anthropic API, not Bedrock.
- Traced through `AnthropicInstrumentor`.

**(b) Judges expect, we don't use**
- Bedrock-native features: Guardrails `ApplyGuardrail`, Knowledge Bases, AgentCore, model invocation logging. All of them need boto3 or the console, and none were verified on the lab account. Sonnet/Opus on Bedrock return 404 for us.

**(c) ≤30-min wow**
1. **Model chip on the receipt / Control Room**: "Bedrock · claude-haiku-4-5 · us-west-2 · 520 ms TTFT", read from `client.village_model` (exposed at `core/llm.py:77`) (~10 min). *Screen:* receipt + Control Room. *Risk:* none.
2. **Devpost architecture paragraph**: which roles run on Bedrock, the measured numbers, and the honest note that only Haiku 4.5 was granted (~5 min).
3. Anything Bedrock-native (Guardrails, etc.) is **not recommended**: unverified on this account, and it would need a new SDK in the demo path.

**(d) Table line:** "Every safety-critical model call (scam extraction, the watcher, the verifier) runs on Claude Haiku 4.5 on Bedrock, scoring 30 of 30 on our eval set with zero false alarms."

---

## Pick for the last hour

| Sponsor | Wow item | Minutes | Screen |
|---|---|---|---|
| Anchor | `recordings.fetch_primary_recording(session_id)` → MP4 replaces the dead live-view "recording" link | 20 | Receipt + Devpost |
| Arize | Ana's approve → `human_approval` annotation on the proposal span (pre-capture screenshot) | 25 | Arize trace view on Control Room laptop + Devpost |
| SurrealDB | "Written by" agent chips from `agent=` fact labels on the Fact card | 15 | Ana's phone |
| ElevenLabs | Success-evaluation criteria + data collection on mom-line (before 14:00) | 15 | Devpost (Analysis tab) |
| Daytona | Receipt line: sandbox id + labels + "33/33 floor tests · build 2.1 s" | 10 | Receipt + Devpost |
| AWS Bedrock | Model chip "Bedrock · claude-haiku-4-5 · 520 ms" from `client.village_model` | 10 | Receipt + Control Room |
