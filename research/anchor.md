# Anchor Browser: capability research for Village (Oct 16 2026 build)

Sources: `docs/anchor-llms-full.txt` (llms-full snapshot), installed and read `anchorbrowser==1.0.1` (PyPI, 1.0 generated from OpenAPI), `~/.claude/skills/anchorbrowser-cli/SKILL.md`, docs.anchorbrowser.io, and third-party benchmarks. **No API key on this machine, so none of the latency numbers below were measured here.** Measure them tonight (see the end of this file).

---

## 1. Session create latency, SDK names, async Playwright over CDP

**Verdict: about 1.5–4 s to create a session and about 0.2–1 s to connect over CDP. Pre-warm the QA session; don't create it on the click path.**
- Browserless benchmark: Anchor took 3,730 ms for the whole lifecycle: create 1,528 ms, connect 1,015 ms, release 315 ms. https://www.browserless.io/blog/how-fast-is-your-hosted-browser-a-practical-benchmark-for-automation-workloads
- Steel benchmark: create 3,797 ms, connect 184 ms. https://steel.dev/blog/remote-browser-benchmark
- Some options add time. Profile warm-up adds about 10 s and a volume mount adds a few seconds (docs lines 9958 and 5242). Proxy and stealth also take longer, so use `POST /v1/sessions/async` and the `session.ready` webhook for those.
- Rate limits: the Free plan allows **5 session creates per minute** and **5 concurrent browsers**. A `429` without `Retry-After` means you hit the concurrency cap (docs "Browser Sessions → Rate limits").

**Python SDK 1.0.x method names.** The SDK is generated from OpenAPI, and the old 0.x names (`sessions.create`) no longer exist.
```python
from anchorbrowser import Anchorbrowser, AsyncAnchorbrowser   # reads ANCHORBROWSER_API_KEY (NOT ANCHOR_API_KEY)
c = Anchorbrowser()
s = c.sessions.create_session(session={...}, browser={...}, identities=[...])  # s.data.id / .cdp_url / .live_view_url
c.sessions.create_session_async(...); c.sessions.get_async_session_status(req_id)
c.sessions.goto(sid, url=...); c.sessions.get_session_screenshot(sid)   # binary PNG
c.sessions.delete_session(sid)       # end session
c.tools.fetch_webpage(url=...)       # Web Unlocker -> HTML str
c.tools.screenshot_webpage(url=..., width=390, height=844, session_id=...)
c.tools.perform_web_task(prompt=..., url=..., async_=True, output_schema=...)
c.tools.get_perform_web_task_status(workflow_id)
c.agent.task(prompt, task_options={...}, session_id=None)   # hand-written helper
c.recordings.list_recordings(sid); c.recordings.fetch_primary_recording(sid)
c.tasks.run_task(task_id, input_params={...}, sync=True)
c.browser.create() / c.browser.connect(sid)                  # Playwright context managers
```
Requirements are Python ≥3.10 and pydantic v2. The SDK also ships `AsyncAnchorbrowser` with the same surface.

**Async Playwright from FastAPI on macOS.** `pip install anchorbrowser playwright` is enough. **You don't need `playwright install`** because `connect_over_cdp` never launches a local Chromium.
```python
import os
from playwright.async_api import async_playwright
from anchorbrowser import AsyncAnchorbrowser

ab = AsyncAnchorbrowser()  # ANCHORBROWSER_API_KEY
async def qa_session():
    s = await ab.sessions.create_session(
        browser={"viewport": {"width": 390, "height": 844}},           # phone-sized QA
        session={"recording": {"active": True},
                 "timeout": {"max_duration": 15, "idle_timeout": 5}})  # minutes
    return s.data
async def qa_run(sess, preview_url):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(sess.cdp_url)    # cdp_url embeds apiKey: never log it
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(preview_url, wait_until="networkidle")
        await page.get_by_role("button", name="I took my pills").click()
        await page.get_by_text("Logged").wait_for(timeout=8000)
```
- Gotcha: `AsyncBrowserResource.create()` is an `async def` that *returns* an async context manager, so call it as `async with await ab.browser.create() as browser:`. Using `connect_over_cdp` directly, as above, is clearer.
- Gotcha: `browser.close()` only disconnects. To stop billing, call `delete_session`.

## 2. Live view embed

**Verdict: you can embed it in a plain iframe on your own origin.** `curl -I https://live.anchorbrowser.io/inspector.html?sessionId=x` returned HTTP 200 with **no `X-Frame-Options` and no CSP `frame-ancestors`** (checked tonight). The docs' recommended embed:
```html
<iframe src="{live_view_url}" sandbox="allow-same-origin allow-scripts"
  allow="clipboard-read; clipboard-write" style="border:0;width:100%;height:100%;pointer-events:none"></iframe>
```
- **Read-only view:** there is no URL parameter for it. Set `pointer-events:none` on the iframe, as the docs do.
- **No browser chrome:** the docs have a "Fullscreen view (hide navigation bar)" section, but its URL was lost from the snapshot. Headless sessions show only the page, without the address bar. Test both tonight.
- **Headful vs headless:** headful is the default and shows the full Chrome UI, including the address bar. The live view always follows the active tab. Headless also has a live view, but the docs warn that it "points to the browser default first page", so navigate in the first tab. `one_time_url: true` needs headful.
- `&show_cursor=1` draws the remote cursor. That makes the agent's taps visible in the demo.
- The URL format is `https://live.anchorbrowser.io/inspector.html?sessionId=<id>`. It contains no API key, so it's safe to put in the dashboard. `cdp_url` does contain the key.

## 3. Reading pages: Web Unlocker vs screenshot vs agent vs Playwright

| Method | Latency | Cost | Output | Use in Village |
|---|---|---|---|---|
| `tools.fetch_webpage` (Web Unlocker, `POST /v1/tools/fetch/webpage`) | "typically a few seconds", no cold start, capped at about 120 s | **$0.005 per 200 response** (failures are free) | **Rendered HTML** after JS runs; PDF/JSON returned as-is | **Default reader.** Pipe it to `markdownify`/`trafilatura`, then Claude extracts with your own schema |
| `tools.screenshot_webpage` | session spin-up + render | browser $0.01 + minutes | PNG | Evidence thumbnail for a rumor check |
| `perform_web_task` / `agent.task` | session (≈2–4 s) + N steps × ~3–8 s (estimate) | **$0.10 per task + $0.01–0.10 per step** + browser | JSON string matching `output_schema` | Only for pages that need clicking (ConEd map search box, finder ZIP filter) |
| Playwright over CDP | session + your code | $0.01 + $0.05/h | anything | QA flows (deterministic) |

- Web Unlocker doesn't use a session, doesn't count toward concurrency, and allows 2,000 requests/min. It solves CAPTCHAs on every plan because it's billed per request. The FAQ says plainly that it returns **raw HTML, not markdown**.
- The "Get Webpage Content (markdown)" endpoint is still linked from "Control a Session", but its API page **returns 404** and the 1.0 SDK doesn't include it. In the older SDK it was `fetch_webpage(format='markdown')` (seen in `langchain-anchorbrowser` 0.2.0's `AnchorContentTool`). **Treat it as gone. Convert HTML to markdown locally.**
- Probed from here: `finder.nyc.gov/coolingcenters/` returns a 2 KB SPA shell, so it **needs JS rendering** (Web Unlocker or a session). `outagemap.coned.com` is also an SPA. **NWS (`api.weather.gov/alerts/active?area=NY`) and DailyMed (`dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name=`) are plain JSON APIs**: call them directly with httpx and send a User-Agent for NWS. Use Anchor only for the human-facing label page and the SPAs. That keeps credits and latency low and the demo reliable.
- Structured extraction with `agent.task`:
```python
r = c.agent.task("Find max daily dose and listed interactions with warfarin",
    task_options={"url": dailymed_setid_url, "output_schema": Dose.model_json_schema(), "max_steps": 8})
data = json.loads(r.data.result)   # result is a JSON *string*; the docs' ast.literal_eval example is fragile
```
Schema gotcha (docs ~line 2626): optional fields fail validation on `null`. Add a `"none"` sentinel instead.

## 4. agent.task / perform-web-task

- **Agents:** `browser-use` (default; claimed 89% on WebVoyager), `openai-cua`, `gemini-computer-use`, `anthropic-cua`, `yutori` (n1, "2.5× faster, 4–5× cheaper"), `jev`.
- **Models** (browser-use): Anthropic `claude-opus-4-8/4-7/4-6/4-5`, `claude-sonnet-5`, `claude-sonnet-4-6/4-5`, `claude-haiku-4-5`. OpenAI `gpt-5.6-sol/terra/luna`, `gpt-5.5`, `gpt-5.4(-mini/nano)`, and older. Gemini `3.1-pro-preview`, `3.6/3.5-flash`. Groq `openai/gpt-oss-120b`, llama-4, kimi-k2. Azure `o3`, `o4-mini`.
- SDK typing quirk: the 1.0.1 `provider` Literal is `openai|gemini|groq|azure|xai`, without `anthropic`, even though the docs list anthropic. Python doesn't enforce the Literal at runtime, so pass it or use `extra_body`.
- **BYOK:** add the key under Dashboard → Project Settings → BYOK, with providers `anthropic`, `openai`, `google`, `vertex`, `azure`, `custom`. **Bedrock is not listed**; the only route would be an OpenAI-compatible proxy as `custom`. Send `key_slug` per request. It isn't an SDK kwarg, so use `extra_body={"key_slug":"village-anthropic","model":"claude-sonnet-4-6"}`. With BYOK, **every step costs a flat $0.01**. BYOK works for sessions and perform-web-task, not Tasks.
- **Step pricing (from Aug 21 2026):** Light $0.01 (gpt-5-mini, gpt-oss-120b), Standard $0.05 (Haiku 4.5, gemini-3.5-flash), High $0.10 (Sonnet/Opus). There's also a **$0.10 (0.1 credit) charge per task**. Pick Haiku 4.5 or gpt-oss on Groq for speed and cost.
- **max_steps:** the docs say the default is 40 (the async table says 200). Plan cap is **120 on Free/Starter**. For rumor checks, set 6–10.
- **Latency per step isn't documented.** From browser-use experience, estimate 3–8 s per step with Sonnet and about 1–3 s with Groq. Measure it.
- **Streaming progress:** `task_options={"on_agent_step": cb}`. The SDK opens `wss://api.anchorbrowser.io/ws?sessionId=<id>` and passes each message to `cb` as a raw **string**. In the async client it calls `asyncio.create_task`. Forward those strings to your FastAPI SSE bus to show the agent's reasoning in the UI. For async REST runs, `get_perform_web_task_status` only returns RUNNING/COMPLETED/FAILED, so subscribe to the WS yourself using the `sessionId` (it's present while RUNNING). Note: `COMPLETED` can still contain a failed answer, so check `result`.
- `human_intervention=True`, together with `agent.get_requested_human_intervention` and `respond_to_human_intervention`, gives a human-in-the-loop path.

## 5. Recordings and screenshots (QA evidence)

Recording is **on by default** and produces an MP4.
```python
recs = c.recordings.list_recordings(sid)
mp4 = c.recordings.fetch_primary_recording(sid)  # GET /v1/sessions/{id}/recordings/primary/fetch
with open(f"qa-{sid}.mp4","wb") as f:
    for ch in mp4.iter_bytes(8192): f.write(ch)
png = c.sessions.get_session_screenshot(sid).read()   # mid-run evidence, no session end needed
```
The recording is available only after the session ends. Subscribe to the `session.recording.ready` webhook (it includes duration and size) instead of polling. Recordings can be paused and resumed (`recordings/pause|resume`). Fetching is limited to 2,000 per hour per team, and the Free plan keeps recordings for 7 days. For a step-by-step QA report, take a screenshot after each assertion with Playwright's `page.screenshot()` (instant) and attach the MP4 link when it's ready.

## 6. Credits and plans

- The pricing table says the Free plan gives $5/mo, **5 concurrent browsers**, and 5 creates per minute. **No CAPTCHA solving, no geolocation proxy, no authenticated browsers (identities).** Extra stealth needs **Growth**. Code execution (`tools.execute_code`) also needs **Growth**.
- I couldn't find anything public about `ANCHOR_HACKSPRINT_10_16_26`. It most likely adds $200 of credit **but leaves you on the Free plan**. Check in the dashboard (Billing) whether it raises the tier. CAPTCHA solving also requires an active proxy (`session.proxy.active`), which is a Starter feature.
- Village doesn't need CAPTCHA solving or stealth: the NYC .gov pages, ConEd, and DailyMed aren't bot-walled. If one is, Web Unlocker works on any plan. At $5 per 1k fetches and about $0.30 per agent task, $200 easily covers the hackathon.

## 7. Hosted MCP

- **Anchor** at `https://api.anchorbrowser.io/v1/mcp`: `perform_web_task`, `get_web_task_status`, `search_action_index`, `get_action_index`, `execute_action_index`, `list_tasks`, `get_task`, `run_task`, `get_execution`, `create_identity`, `create_identity_link`, `create_reauth_link`, `reauthenticate_identity`, `get_identity`, `create_session`, `get_session`, `end_session`, `search_docs`, `read_doc`, `list_endpoints`, `get_endpoint`, `call_endpoint_read`, `call_endpoint_write`. `/v1/mcp/all` exposes every route as its own tool.
- **Anchor Browser** at `/v1/mcp/browser`: `anchor_*` tools for navigate, snapshot (accessibility refs, no vision), click, type, screenshot, console and network logs, and **Playwright codegen**.
- **Anchor Actions** at `/v1/mcp/actions/{domain}`: verified deterministic recipes per site, exposed as typed tools.
- Dev time: `claude mcp add --transport http anchor-browser https://api.anchorbrowser.io/v1/mcp/browser --header "anchor-api-key: $KEY"`. Use it to write the QA script against a real preview URL; codegen gives you Playwright code directly.
- Agent use: Claude's Messages API MCP connector, or the Python `mcp` streamable-http client, with the `anchor-api-key` header.

## 8. What would impress a "Best Use of Anchor" judge

1. **The browser QAs the AI-generated app before release.** For every generated role app, a phone-viewport Anchor session taps Mom's button, and your Core sees the event round-trip. The dashboard shows the **live view iframe** (`show_cursor=1`), then a ✅ badge with screenshot and MP4. This is a strong pitch: "no generated UI ships to Grandma until a real browser has tapped it."
2. **Automation Tasks with self-healing.** Generate a reusable "verify-village-app" task via `POST /v2/tasks/generate` with `taskPrompt` and `{{preview_url}}`/`{{button_label}}` inputs, then run it each release with `tasks.run_task(id, input_params=..., sync=True)`. When the agent changes the UI (SymptomLog added), the deterministic step breaks, **AI fallback** completes the run, and the `task.healed` webhook delivers a new version. That gives you a visible self-healing moment on stage. Risk: generation is async and took minutes in reports, so create the task tonight.
3. **Webhooks to your Core:** `task.completed` (includes `recording_url`, `duration_ms`, `cost`), `session.recording.ready`, `task.healed`. Show a cost-per-QA-run tile.
4. **Rumor checker with provenance.** Use Web Unlocker for official SPAs and screenshots as evidence, and an `agent.task` with `output_schema {claim, verdict, source_url, quote}` only when it has to click. Stream steps over the WS so the coordinator sees "Checking Con Edison outage map…".
5. Profiles (`browser.profile: {name, persist:true}`) and Identities/OmniConnect fit poorly here because there are no logins. Mention them only as roadmap, e.g. a caregiver connecting the pharmacy portal through OmniConnect.

---

## Recommended decisions for Village

- Use `anchorbrowser>=1.0.1` and `AsyncAnchorbrowser` in FastAPI. Set the env var `ANCHORBROWSER_API_KEY`.
- **QA:** create one pre-warmed headful session per release with viewport 390×844, recording on, `max_duration` 15. Drive it with **deterministic Playwright** (role selectors from your component kit's `aria-label`s), not `agent.task`: it's faster, effectively free, and repeatable. Embed `live_view_url` with `pointer-events:none`. Store a PNG per assertion and the MP4 on `session.recording.ready`.
- **Reading:** use DailyMed REST and NWS JSON directly. Use Web Unlocker HTML → markdownify → Claude extraction for finder.nyc.gov, ConEd, and NYC EM. Use `agent.task` (Haiku 4.5 or BYOK, `max_steps` ≤10, `output_schema`) for at most one "interactive" rumor check, with steps relayed to SSE.
- Optional stretch: one Automation Task "verify-village-app" with self-healing for judge appeal.
- Always call `delete_session` in `finally`. Free-plan concurrency is 5.

## Open risks to test tonight (≈30 min)

1. Redeem the code and check the plan, concurrency, and whether CAPTCHA, proxy, and identities unlock.
2. Time `create_session`, `connect_over_cdp`, `goto` on a Daytona preview URL, and `delete_session` (10 runs). Pre-warming is needed if create takes more than 3 s.
3. **Can an Anchor browser reach the Daytona signed preview URL?** Check token or auth headers and whether Daytona shows an interstitial/warning page. If it does, pass the header with `page.set_extra_http_headers` or use the token query parameter.
4. Iframe the live view from a `localhost` dashboard. Check headful vs headless chrome and find the "fullscreen" URL variant.
5. `fetch_webpage` on finder.nyc.gov/coolingcenters: does the rendered HTML contain center list data, or do you need clicks or a ZIP? Measure latency.
6. `agent.task` with `on_agent_step`: confirm the WS message format and that it works from the async client. Measure s/step for haiku-4-5 vs sonnet-4-6. Check whether BYOK `extra_body={"key_slug":…}` is accepted.
7. Check that the recording is fetchable within 30–60 s after `delete_session`.
8. Check that SSE from FastAPI reaches the Anchor-hosted page (the QA browser needs the live update to arrive, and some proxies buffer `text/event-stream`).
