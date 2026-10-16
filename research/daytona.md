# Daytona capability research for Village (Oct 15 2026)

Sources: `docs/daytona-llms-full.txt` (generated 2026-10-12; line refs `L####`), daytona.io/pricing (fetched today), `~/.claude/skills/daytona`. "UNVERIFIED" = not stated in docs; test it tonight.

## 1. Preview URLs: PARTIAL (works, but there's a warning page)
- **Two kinds (L27285).** The standard URL is `https://{port}-{sandboxId}.proxy.daytona.work(s)` and needs the `x-daytona-preview-token` header. That token works for every port of the sandbox, including toolbox 2280 and terminal 22222, so never share it. The signed URL is `https://{port}-{token}.{proxyDomain}` with the token inside the URL. A signed token is bound to one port, expires, and can be revoked.
- **Phone opens the signed URL directly: YES.** "embeds the authentication token directly in the URL, requiring no headers".
- **Expiry:** default **60 s**, max **86,400 s (24 h)**. Always pass `expires_in_seconds`.
- **Ports:** any HTTP port from 1 to 65535. 22222, 2280 and 33333 always require auth.
- **Restarts:** a signed token "persists across sandbox restarts until it expires". A standard token is reissued on stop/start; pause/resume keeps it. A signed URL also dies if "signing keys are rotated" (L48074).
- **Public flag: YES.** `public=True` at create time, or `sandbox.set_public(True)` (L62542). Preview links then need no auth. Reserved ports still do.
- **WebSocket: YES.** "fully supports WebSocket… skip the preview warning page" (L27507). SSE through the preview is not documented, but it is plain HTTP streaming, so it probably works (UNVERIFIED for buffering). We don't need it, because SSE goes phone → Core.
- **CORS:** the default "allows all origins with credentials". The `X-Daytona-Disable-CORS: true` header turns it off.
- **Custom domain:** only through a **Custom Preview Proxy** that you host yourself (samples: github.com/daytonaio/daytona-proxy-samples).
- **WARNING INTERSTITIAL: YES, phones will see it.** "When opening a preview link in a browser for the first time, Daytona displays a warning page" (L27472). You skip it with the `X-Daytona-Skip-Preview-Warning: true` **header**, by being on **Tier 3**, or with a custom proxy. Once a visitor accepts, a `daytona-preview-page-accepted` cookie lasts 24 h. A phone can't send headers, so every judge's phone gets one extra tap. The docs list `public=True` separately from these skip options, so assume a public sandbox still shows the page (`GET /preview/{id}/preview-warning` reports the state).
```python
signed = sb.create_signed_preview_url(4173, expires_in_seconds=86400)
qr_url = signed.url                          # https://4173-<token>.proxy.daytona.works
sb.expire_signed_preview_url(4173, signed.token)  # revoke
```
- **Fix: Core as the custom preview proxy.** FastAPI route `/v/{village}/{path}` → httpx stream to the standard preview URL with these headers:
  - `X-Daytona-Preview-Token`
  - `X-Daytona-Skip-Preview-Warning: true`
  - `X-Daytona-Skip-Last-Activity-Update: false`

  Build Vite with `base: './'`. Result: one tunnel origin, no CORS, no interstitial, and it is the documented pattern (judge-friendly).

## 2. Lifecycle, resources, cost
- **Create latency:** "<90ms" for a container from a snapshot (marketing). A guide measured about 3 s for a cold create to ready (L44104). Budget 2–5 s, and up to minutes the first time a snapshot runs in a region.
- **Defaults (L960):** 1 vCPU / 1 GiB / 3 GiB. **Per-sandbox max 4 vCPU / 8 GiB / 10 GiB.** Built-in snapshots: `daytona-small` 1/1/3, `daytona-medium` 2/4/8, `daytona-large` 4/8/10.
- **auto_stop_interval:** default **15 min**; `0` disables it. Timer resets on: preview traffic, toolbox/SDK process/fs calls, SSH, state changes. Background `npm run preview` alone does not reset it. `sandbox.refresh_activity()` keeps it alive.
- **auto_archive_interval:** default 7 days; `0` means the 30-day max. Containers only.
- **auto_delete_interval:** unset = never; `0` = delete on stop; `-1` = off.
- **ttl_minutes:** wall-clock kill in any state. `ephemeral=True` deletes on stop.
- **Org pools (L47457):**

  | Tier | vCPU | RAM | Disk | Requirement |
  |---|---|---|---|---|
  | 1 | 10 | 10 GiB (another table says 20) | 30 GiB | email verified |
  | 2 | 100 | 200 GiB | 300 GiB | card + $25 top-up |
  | 3 | 250 | 500 GiB | 2000 GiB | $500 top-up |

  Sandbox-create rate limit: 300/min on T1, 400/min on T2.
- **Disk quota:** stopped containers **keep using disk quota until archived or deleted**.
- **Pricing (daytona.io/pricing), billed per second:** vCPU $0.0504/h, RAM $0.0162/GiB-h, disk $0.000108/GiB-h (first 5 GiB free). New accounts get $200 free.
- **What $100 buys:** a 2 vCPU / 4 GiB sandbox costs about $0.166/h, so about 600 sandbox-hours. A 1/2 sandbox is about $0.083/h, so about 1,200 h. Money is not the constraint. **The Tier-1 quota is: 10 GiB RAM ≈ 2 medium sandboxes at once.**

## 3. Network egress: PARTIAL
- **Tier 1/2 (L27995):** "Network access is restricted and cannot be overridden at the sandbox level… Even with networkAllowList or domainAllowList… the organization's network restrictions still apply." A per-sandbox list **can only restrict, never add**.
- **Tier 3/4:** "Full internet access by default". A sandbox list replaces the default and is strict (essential services are not auto-allowed).
- **Essential services (allowed on T1/2, L28596):**
  - `*.anthropic.com`, `claude.ai`, `platform.claude.com`: **YES**.
  - Bedrock: **YES via region wildcards.** `*.us-east-1/2`, `*.us-west-1/2`, eu-central-1/2, eu-north-1, eu-south-1/2, eu-west-1/2/3 and ap-south-1 `.amazonaws.com` are allowed, so `bedrock-runtime.us-east-1.amazonaws.com` is OK. Bare `*.amazonaws.com` is **NOT** allowed, nor are other regions (e.g. ap-northeast-1) or the global `sts.amazonaws.com`. Use regional STS or static keys.
  - `registry.npmjs.org`, `nodejs.org`, `deb.nodesource.com`, yarn, bun, github, `unpkg.com`, `jsdelivr.net`, `fonts.googleapis.com`: **YES**.
  - `otlp.arize.com`, `app.arize.com`, `app.phoenix.arize.com`: **YES**. `*.langfuse.com` also YES.
  - `api.elevenlabs.io` YES; `cloudflare.com` and `*.workers.dev` YES.
  - **`trycloudflare.com`: NO.** The sandbox cannot call Core over a quick tunnel, and your own domain is not reachable either. Core must **pull**, as in §5. The browser reaching Core is unaffected.
- **Tier 3:** a $500 top-up for unrestricted egress and no warning page. Not worth it.
- `outbound_proxy_url` exists. Whether it bypasses tier policy is UNVERIFIED; assume it doesn't.

## 4. Snapshots / Declarative Builder: YES
```python
from daytona import Daytona, Image, CreateSnapshotParams, CreateSandboxFromSnapshotParams, Resources
img = (Image.base("node:22-bookworm-slim")
  .run_commands("apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*")
  .add_local_dir("village-template", "/home/daytona/app")     # package.json + lockfile + kit
  .workdir("/home/daytona/app")
  .run_commands("cd /home/daytona/app && npm ci && npx vite build"))  # warm node_modules + vite cache
d = Daytona()
d.snapshot.create(CreateSnapshotParams(name="village-node22-v1", image=img,
                  resources=Resources(cpu=2, memory=2, disk=6)), on_logs=print)
sb = d.create(CreateSandboxFromSnapshotParams(snapshot="village-node22-v1",
      auto_stop_interval=60, auto_delete_interval=120, labels={"village": vid},
      env_vars={"DAYTONA_SANDBOX_OTEL_SERVICE_NAME": "village-apps"}))
```
- Declarative images are cached for 24 h per runner. Expect about 2–6 min for a Node + npm-deps build (UNVERIFIED; build it tonight).
- Snapshots go **inactive after 2 weeks unused**.
- No explicit size cap was found. Disk is bounded by the per-sandbox max of 10 GiB.
- Builds are containers only (not VMs). Daytona runs the image as the `daytona` user, so `chown` the app dir (L8980).
- Default snapshots already include Node, `@anthropic-ai/claude-code`, the `claude-agent-sdk` (py) and `typescript` (L6766). The Node major version is unknown.

## 5. Process / files / git: YES
```python
await sb.process.create_session("build")
cmd = await sb.process.execute_session_command("build",
        SessionExecuteRequest(command="npm run build && npx vitest run --reporter=dot", run_async=True))
await sb.process.get_session_command_logs_async("build", cmd.cmd_id,
        lambda o: hub.emit(vid, "build.out", o), lambda e: hub.emit(vid, "build.err", e))  # -> SSE
st = await sb.process.get_session_command("build", cmd.cmd_id); st.exit_code
await sb.process.execute_session_command("srv", SessionExecuteRequest(
        command="npx vite preview --host 0.0.0.0 --port 4173", run_async=True))
await sb.fs.upload_files([FileUpload(source=b, destination=f"app/src/{p}") for p, b in files])  # bulk
sb.git.clone(url="https://github.com/...", path="workspace/repo")
```
- Use `AsyncDaytona` in FastAPI.
- Keep log callbacks non-blocking: blocking sync callbacks drop the WebSocket (L22521).
- PTY sessions exist for interactive use.

## 6. Fork / snapshot-from-sandbox: PARTIAL
- **Fork:** **Linux VM sandboxes only**. "Forking is not supported for container sandboxes" (L3540). It copies memory and filesystem copy-on-write: fork 0.66 s, child serving 1.78 s p50 (L44104).
- **VM sandbox limits:** must be created from a VM snapshot (`daytona-vm-small`, …). The declarative builder can't make one. VM quota may need a tier upgrade (L47920), so probably unavailable on a fresh hackathon org.
- **Container alternative:** a cold `create_snapshot(name)` of a **stopped** sandbox, then create from it (tens of seconds+).
- **"Try a variant" for Village:** simpler is a second `vite build` into `dist-b/` in the same sandbox, served on another port with its own signed URL.

## 7. Claude Agent SDK inside Daytona: YES (guide L31534)
- **Guide flow:**
  1. Create `daytona-medium`.
  2. `pip install` the SDK.
  3. Upload `coding_agent.py`.
  4. Open a code-interpreter context and run `coding_agent.run_query_sync(PROMPT)`.

  Streaming comes back through `onStdout`/`onStderr` callbacks. Agent options: `ClaudeSDKClient(ClaudeAgentOptions(allowed_tools=["Read","Edit","Glob","Grep","Bash"], permission_mode="acceptEdits", system_prompt=...))`.
- **Auth:** the guide puts `ANTHROPIC_API_KEY` in `envVars`, or better, a **Daytona Secret**:
  - Create it with `daytona.secret.create({name, value, hosts:['api.anthropic.com']})`, then pass `secrets:{ANTHROPIC_API_KEY:'anthropic-api-key'}` (SDK ≥0.192).
  - The sandbox only ever sees `dtn_secret_…`; the egress proxy swaps it into **HTTPS headers only** and scrubs responses.
- **Bedrock instead:**
  - Env: `CLAUDE_CODE_USE_BEDROCK=1`, `AWS_REGION=us-east-1`, plus `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`(/`AWS_SESSION_TOKEN`), or `AWS_BEARER_TOKEN_BEDROCK`.
  - **SigV4 creds cannot use Secrets.** The signature is computed from the secret in the sandbox, so they must be plain env vars; use short-lived STS creds.
  - A Bedrock API key goes in an `Authorization: Bearer` header, so it *might* work as a Secret with `hosts:["bedrock-runtime.us-east-1.amazonaws.com"]` (UNVERIFIED).
- **Setup time:** zero install on default snapshots, since claude-code and claude-agent-sdk are preinstalled. Otherwise about 30–60 s of pip/npm.
- **Alternative (L32125):** `claude -p '…' --output-format stream-json --verbose --dangerously-skip-permissions` in a PTY with `on_data` gives structured events to forward to SSE.
- **MCP:** `brew install daytonaio/cli/daytona && daytona login && daytona mcp init claude` (or `daytona mcp config` → `{"command":"daytona","args":["mcp","start"]}`). Useful for driving dev from Claude Code; it is not part of the product path.

## 8. OTel → Arize: PARTIAL/feasible
Org-level sandbox telemetry (owner only; Dashboard → Settings → OpenTelemetry):
```bash
curl -X PUT https://app.daytona.io/api/organizations/$ORG/otel-config -H "Authorization: Bearer $DAYTONA_API_KEY" \
 -H 'Content-Type: application/json' -d '{"endpoint":"https://otlp.arize.com","headers":{"arize-space-id":"…","arize-api-key":"…"}}'
```
- It exports traces, logs and metrics: CPU/mem/fs metrics, stdout logs and HTTP spans.
- Labels: set `DAYTONA_SANDBOX_OTEL_EXTRA_LABELS="openinference.project.name=village,village=<id>"`.
- Arize is LLM-trace oriented. It may reject logs and metrics, and whether the path appends `/v1/traces` is not documented (UNVERIFIED).
- **SDK tracing** in Core: `AsyncDaytona(DaytonaConfig(otel_enabled=True))` + standard `OTEL_EXPORTER_OTLP_ENDPOINT/HEADERS`. This is the reliable one; Daytona spans nest under your Arize agent trace.
- Agent spans from inside the sandbox can reach `otlp.arize.com`, which is on the allowlist.
- Daytona's own retention is 3 days. You can also pull `GET /api/sandbox/{id}/telemetry/{logs|traces|metrics}`.

## 9. Webhooks: PARTIAL
- Events: `sandbox.created`, `sandbox.state.updated` (oldState/newState), `snapshot.*`, `volume.*`. Configured in the Dashboard only.
- **They may need support to enable:** "If you don't see Webhooks… contact support". The endpoint must be HTTPS; the cloudflared URL is fine.
- Fallback: poll `sandbox.refresh_data()`/state.

## 10. Judge-impressive, Village-fitting
- **Secrets with host allowlist + response scrubbing**: "the agent in the sandbox can't read its own key".
- **Signed, per-port, revocable, expiring preview URLs** in the QR, with a **"revoke access" button**.
- **Custom preview proxy via Core**: no interstitial, one origin.
- **Declarative-builder snapshot** with streamed build logs shown in the UI.
- **Session + async command log streaming** shown live as the build log.
- **Labels** (`village=<id>`) and `ttl_minutes`/auto-delete hygiene.
- **Volumes with subpath per village** (tenant isolation): persist village data and specs across sandbox rebuilds.
- **Linked sandboxes** (ephemeral child on the parent's link network): e.g. an untrusted generated component tested in a child with `network_block_all`. That needs T3 to restrict; otherwise skip.
- **Warm pools:** instant claim, but **gated by support** and requires no custom env/secrets/volumes.
- **Audit logs**, `get_metrics()` CPU/mem sparkline per village, and **webhooks** feeding the SSE hub.

## 11. Demo gotchas
1. **Preview warning page on every judge's phone.** Proxy through Core, or tell judges "tap Continue".
2. **Signed URL default is 60 s.** Pass 86400. Revocation and signing-key rotation kill the QR, so regenerate on demand.
3. **Auto-stop at 15 min idle.** A background `vite preview` doesn't count. Set `auto_stop_interval=0` (or 120) during judging and call `refresh_activity()` from a Core heartbeat.
4. **Tier-1 RAM of 10 GiB** limits concurrent sandboxes. Stopped containers still hold disk; delete stale ones, label everything, and keep 1 spare pre-created village.
5. **Standard tokens change after stop/start.** Re-fetch them in the proxy.
6. **Egress:** trycloudflare is blocked, as are non-listed AWS regions and global STS.
7. Snapshot build failures leave an error state that blocks reuse of the name. Version the names (`-v2`).
8. **Rate limit:** 300 creates/min (fine). Handle `DaytonaRateLimitError`.
9. Sync log callbacks that block cause WebSocket disconnects.
10. Vite must bind `--host 0.0.0.0`. Use `vite preview` (static) rather than dev HMR on phones.

## Recommended decisions for Village
- Containers, not VMs: one prebuilt snapshot `village-node22-vN` (node 22, kit, `npm ci` done, vite cache warm), 2 vCPU / 2–4 GiB, `auto_stop_interval=0` during the demo, `ttl_minutes=360`, labels.
- Write the spec + components with `fs.upload_files`, then `execute_session_command(run_async)`. Stream the logs to Core's SSE hub, then `vite preview` on 4173.
- QR = **Core proxy URL** (`/v/{id}/`) with skip-warning + preview-token headers. Keep the signed 24 h URL as a fallback and a "direct Daytona link" talking point.
- Core pulls everything (logs, status); nothing in the sandbox calls Core.
- The agent in the sandbox is **optional**. If used: default snapshot tools, `ANTHROPIC_API_KEY` via Daytona Secret (`hosts:["api.anthropic.com"]`). If it must be Bedrock, use short-lived STS env creds in us-east-1/us-west-2.
- Enable SDK OTel in Core → Arize. Treat org-level sandbox OTel as a bonus.
- Ask Daytona staff at the venue to enable webhooks and warm pools, and to confirm the tier.

## Open risks to test tonight
- Does a phone (iOS Safari) hit the warning page on a signed URL and on a `public=True` sandbox? Does the Core proxy fully suppress it?
- Snapshot build time and size for node22 + kit. Cold create-from-snapshot → first served page time.
- `vite build` + vitest duration at 2 vCPU/2 GiB vs 4 GiB (OOM?).
- Bedrock call from inside the sandbox (us-east-1) with STS creds; a Secrets-wrapped `AWS_BEARER_TOKEN_BEDROCK`.
- Org tier/quota after redeeming the $100 coupon: how many concurrent sandboxes; is the VM class visible?
- OTel PUT to `otlp.arize.com`: do traces land; are logs/metrics rejected noisily?
- Is the webhooks tab present? Does SSE through the preview proxy stream unbuffered (only if we ever need it)?
