# RESULTS.md: measured smoke-test results (Oct 16 2026). Overrides every other document on measured facts.

| # | Test | Result | Notes |
|---|------|--------|-------|
| 00 | env check (10:20) | PARTIAL | set: Daytona, Anchor, Arize, AWS_REGION. missing: SurrealDB (instance + memory), ElevenLabs, LLM creds (Anthropic key / AWS). TUNNEL_URL pending Funnel enable |
|| 01 | LLM (10:35) | PARTIAL | Bedrock Mantle us-west-2 lab account: **only `anthropic.claude-haiku-4-5` works** (TTFT ~520-600 ms). 404 for sonnet-5-5, sonnet-5, sonnet-4-5, haiku-5-5, opus-4-6. Decision: Haiku 4.5 on Bedrock for all roles until an Anthropic API key gives Sonnet 5.5 (fallback client). `output_config.effort` not accepted on Mantle |
|| 02 | Daytona egress (10:30) | PASS (as expected) | sandbox created, code_run ok. Sandbox egress BLOCKED to every tested host (anchor, surreal.cloud, bedrock-mantle, example.com, dailymed). Only build+test in the sandbox; Core pulls results |
| 03 | Daytona preview | not run | |
|| 04 | Daytona snapshot (10:30) | FAIL | `DaytonaForbiddenError: Failed to create snapshot: Access denied` (account tier). Fallback under test: sandbox from a public image / default image + npm install at runtime |
|| 05 | Anchor (10:30) | PASS | session, live view, NWS, cooling centers, web unlocker, agent.task all PASS; coned outage map WARN |
| 06 | SurrealDB Agent Memory (11:05) | PASS | context id `06gk9fu5…` (name `village`): whoami 445 ms; scopes registered; remember 5mg→10mg supersession PASS; query hybrid ~3.8–4.0 s; asOf 2026-09-15 returns 5 mg |
| 06b | SurrealDB Cloud LIVE (10:40) | PASS | instance `…aws-use1.surreal.cloud`, user `village` (ROOT OWNER). live() 110 ms; 10/10 notifications, **p50 22 ms, p95 77 ms, max 103 ms** insert→notify |
| 07 | Arize (10:42) | PASS (exporter) | register project=village; traced Bedrock haiku-4-5 call 1825 ms; CHAIN>AGENT>GUARDRAIL/TOOL spans; force_flush 326 ms. UI confirmation pending (operator) |
| 08 | tool server | RUNNING on :8787 | Funnel URL https://richel-macbook.tail8feae0.ts.net preset in .env; enable click pending |
| 09 | ElevenLabs (10:50) | PARTIAL | TTS PASS (50 KB mp3, 656 ms). Agent + tool + call blocked on TUNNEL_URL (Funnel not yet enabled by operator). Twilio number +1 848 257 9221 bought; upgrade + import pending |

## Spine (core lane, 10:37)
- 3 WS clients (elder/coordinator/helper snapshots from the Reyes fixture) → `POST /tools/log_dose` → gate → SurrealDB Cloud write → change feed → `event` frame on all 3 clients in **~130 ms** (tool call to last frame). Decision row written. `uv run pytest -q` 16 core tests + 49 gate tests green offline.

## Public URL (10:52–11:10)
- Funnel enabled; `https://richel-macbook.tail8feae0.ts.net/health` → 200 from Anchor's browser (external); Carmen's view opens on the operator's phone. The Mac itself cannot resolve `*.ts.net` (userspace tailscaled); test from outside only. Funnel verified → Core :8790.
