# Stable public HTTPS URL for the laptop-hosted Core (demo Oct 16 2026)

Researched and tested 2026-10-15 (evening, US Eastern) from the Linux box (`omarchy`). The test server was FastAPI on :8799, serving `/` HTML, `POST /api/echo` and a `/ws` echo. The probe (`scratchpad/pub/probe.py`) sends an **iPhone Safari User-Agent** with `Accept: text/html`, which makes the services show their phone-visitor warning pages if they have one.

## Verdict

- **Primary: Tailscale Funnel.** The URL is `https://richel-macbook.tail8feae0.ts.net`. It is free, the hostname never changes, there is no interstitial, WebSockets and streaming pass through unbuffered, and it needs no domain or new account. Tailscale is already installed on the Mac and logged into this tailnet.
- **Fallback: a Cloudflare Worker on `village.<you>.workers.dev` that proxies to a cloudflared quick tunnel.** The workers.dev name stays the same. When the tunnel URL changes, one `wrangler deploy --var` call (about 10 s) repoints it. The code is ready in `infra/worker-frontdoor/` and was tested locally against a live quick tunnel. It needs a free Cloudflare account.

## Live test results (2026-10-15/16 UTC)

| Path | iOS-UA GET `/` | POST median | WS handshake / echo RTT | Stable name (free)? |
|---|---|---|---|---|
| localhost (baseline) | 200 page | 1 ms | 31 ms / 0 ms | n/a |
| cloudflared quick tunnel | **200, no interstitial** | 49 ms | 213 ms / **19 ms** | **No**, random each start |
| Worker front door (`wrangler dev`, workerd) → quick tunnel | **200, no interstitial** | 59 ms | 192 ms / **20 ms** | Yes, once deployed to workers.dev |
| Tailscale serve (same tailscaled proxy that Funnel uses) | 200 | 1 ms* | 19 ms / 0 ms* | Yes (`*.ts.net`) |
| localhost.run (no key) | 200, no interstitial | 38 ms | 127 ms / 38 ms | **No** (`<random>.lhr.life`) |
| pinggy free | **interstitial** (`pinggy.web.debugger/screen.html`) | 138 ms | **WS fails** (gets the warning HTML) | No, and 60-minute limit |
| loca.lt (`--subdomain`) | **511 "Tunnel website ahead!"** | 133 ms | 6.5 s / 79 ms | Subdomain can be requested but isn't reserved |
| serveo (no key) | **"Serveo - Warning"** page | 237 ms | 599 ms / 231 ms | No |

\*Tailnet-local path, so this shows only that the proxy is correct (no interstitial, WS works, unbuffered streaming). It is not Funnel's internet latency. NDJSON through `tailscale serve` arrived one line per second with about 15 ms delay, so **streams were not buffered**, unlike quick tunnels. I couldn't test Funnel itself because it's switched off on the tailnet: `tailscale funnel` printed *"Funnel is not enabled on your tailnet. To enable, visit: https://login.tailscale.com/f/funnel?node=…"*. Turning it on takes an admin click by the user.

## A. Worker front door on `*.workers.dev`

- **Feasibility:** confirmed. `src/index.js` forwards the request to `env.TARGET`. When it sees `Upgrade: websocket` it returns `fetch(...)`'s 101 response directly, so the socket is passed through without a Durable Object. It also rewrites `Location` headers. `GET /__frontdoor` shows the current target. All of this was verified through `wrangler dev` 4.151.0 against a real trycloudflare URL: the page loaded, POST worked and the WS echo ran at 20 ms.
- **Free limits** ([Workers limits](https://developers.cloudflare.com/workers/platform/limits/), fetched 2026-10-15):
  - 100,000 requests/day, resetting at 00:00 UTC. Going over gives error 1027.
  - 10 ms of CPU per request. `fetch()` wait time is not counted, so a proxy uses well under 1 ms.
  - "No hard limit on duration … as long as the client remains connected".
  - 50 subrequests per invocation.
  - A WS connection counts as one request.
- **Updating the target in about 10 s:** `./set-target.sh auto /path/cloudflared.log`, which runs `wrangler deploy --var TARGET:<url>`. A plain var was chosen instead of KV on purpose: KV writes can take up to 60 s to propagate.
- **Latency:** about +5–10 ms over the bare tunnel, because the Worker runs in the same Cloudflare PoP.
- **Caveats:**
  - It inherits the quick tunnel's weaknesses: SSE/NDJSON are buffered ([TryCloudflare docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/): "Quick Tunnels do not support Server-Sent Events", "200 in-flight requests", "no uptime guarantee", "hostname changes each time").
  - cloudflared needs outbound port **7844** (QUIC/UDP, or TCP with `--protocol http2`), and strict venue firewalls sometimes block it.

## B. Tailscale Funnel

From the [Funnel KB](https://tailscale.com/kb/1223/funnel), updated 2026-01-20:
- "Available for all plans" (beta).
- Requires MagicDNS, HTTPS certificates and the `funnel` nodeAttr.
- Only ports 443, 8443 and 10000.
- "Non-configurable bandwidth limits". That's fine for JSON, WS and small static files, but don't serve video.
- Public DNS "can take up to 10 minutes", so **enable it tonight**.
- On macOS, port sharing needs the App Store or Standalone app.

Our tailnet already has HTTPS enabled (cert issued for `omarchy.tail8feae0.ts.net` by Let's Encrypt YE2). Funnel works as a TCP proxy, and TLS is terminated by tailscaled on the Mac, so the request path has no third-party HTTP buffering and no interstitial. The tailscaled side was verified above.

**Network risk:** the Mac reaches the Funnel ingress through DERP over TCP 443 if UDP is blocked, so it is robust on venue Wi-Fi.

## C. ngrok free static domain

Every free account gets one static dev domain (`*.ngrok-free.app`/`.dev`) ([free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)). However, ngrok "injects an interstitial page in front of all HTML browser traffic on the free tier". After you click "Visit", a cookie keeps it away for that domain for 7 days ([ERR_NGROK_6024](https://ngrok.com/docs/errors/err_ngrok_6024/)).

The only bypasses are the `ngrok-skip-browser-warning` header or a non-browser User-Agent. A judge's phone can send neither. API/webhook traffic from ElevenLabs is not affected. **There is no free workaround for QR visitors, so this is rejected.**

## D. Other tunnels

- **localhost.run:** clean (no interstitial, WS OK, 38 ms). Without an account the name is random per session. Its "forever free" page tells you to register a key for "a longer lasting domain name" (its docs host refused our TLS fetch). Custom/stable names are paid. **Rejected:** not stable.
- **pinggy, loca.lt, serveo:** all show a browser warning page (tested above). **Rejected.**
- **zrok.io free:** shows an interstitial to `Mozilla/5.0` UAs, reset weekly ([zrok docs](https://netfoundry.io/docs/zrok/self-hosting/interstitial-page)). **Rejected.**
- **Expose free:** random URLs, a time limit and an EU-only server. Reserved subdomains cost $79/mo. **Rejected.**

## E. Quick tunnel with "stable" tricks, plus the ElevenLabs env var

There's no free way to pin a quick-tunnel hostname. Confirmed: "The hostname changes each time". Named tunnels require a zone (a domain) on Cloudflare.

ElevenLabs **environment variables** ([docs](https://elevenlabs.io/docs/eleven-agents/integrate/environment-variables)) let a server tool URL be `https://{{system_env__core_host}}/tools/...`:
- The URL must start with literal `https://`.
- Set the value under *Developers → Environment Variables*.
- If no `environment` is passed, it defaults to `production`.

That makes it a one-place host update for webhooks even on bare quick tunnels. Recommended **either way**, so that switching between primary and fallback means editing one value.

A redirector (GitHub Pages meta-refresh, or a workers.dev 302) fixes only the QR code. ElevenLabs tools and WS clients would still need the real host. The Worker *proxy* (A) fixes both.

## F. Deploy Core to a host instead

- **Render free:** spins down after 15 min idle (WS messages count since 2026-02-24), with about a 1-minute cold start ([render.com/docs/free](https://render.com/docs/free)). That's risky for a judge scanning at a random time.
- **Fly.io:** no free tier for new signups (trial of 2 h of machine runtime or 7 days, card required).
- **Railway:** $5 one-time trial, then $1/mo.
- **AWS lab account (App Runner/EC2):** works, and it is the best place for Bedrock calls. The catch is that the URL is `*.awsapprunner.com` or a raw EC2 IP without TLS, and lab accounts often expire or tear down.

Core would also need its secrets for SurrealDB Cloud, ElevenLabs, Daytona, Anchor, Arize and Bedrock copied to the host, plus any local files and Mac-only tools. Re-plumbing all of that the night before is the bigger risk. **Not recommended** unless the Mac dies; even then, Render + `system_env__core_host` is the emergency path.

## Setup: PRIMARY, Tailscale Funnel (about 10 min, do it tonight)

```bash
# On the Mac (Tailscale already logged in as richel-macbook)
TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale   # or `tailscale` if the CLI is installed
$TS funnel --bg 8787          # first run prints https://login.tailscale.com/f/funnel?node=... -> open it, click Enable
$TS funnel --bg 8787          # re-run after enabling; persists across reboots/restarts
$TS funnel status             # shows https://richel-macbook.tail8feae0.ts.net (Funnel on)
curl -sI https://richel-macbook.tail8feae0.ts.net/   # from phone on cellular too (DNS may take up to 10 min)
caffeinate -dimsu &           # keep the Mac awake during the demo; also disable sleep on lid close if docked
```

Then:
1. Set the ElevenLabs env var `core_host = richel-macbook.tail8feae0.ts.net`.
2. Use `https://{{system_env__core_host}}/...` in every server tool.
3. Print the QR for `https://richel-macbook.tail8feae0.ts.net/`.

Port 8787 is Core's port per CLAUDE.md (`uvicorn core.app:app --port 8787`). Funnel proxies to `127.0.0.1:<port>`, so Core can stay bound to localhost.

**Risks:**
- Funnel is beta.
- Bandwidth caps (unpublished).
- The judge's network DNS-filtering `ts.net`. Cellular is unaffected; test on the venue Wi-Fi when you arrive.
- Renaming the Mac in Tailscale changes the URL, so don't.

## Setup: FALLBACK, Worker front door + quick tunnel (about 15 min with Cloudflare signup)

```bash
brew install cloudflared
cd ~/Projects/village-prep/infra/worker-frontdoor
npx wrangler login                                   # free Cloudflare account; pick a workers.dev subdomain once
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8787 2>&1 | tee /tmp/cf.log &
sleep 8 && ./set-target.sh auto /tmp/cf.log          # deploys; prints https://village.<you>.workers.dev
curl -s https://village.<you>.workers.dev/__frontdoor # confirm target
# if 7844 is blocked: cloudflared tunnel --protocol http2 --url ...
```

Repeat the last two lines whenever cloudflared restarts.

**Optional:** you can also run `./set-target.sh https://richel-macbook.tail8feae0.ts.net` and print the QR with the **workers.dev** name. The printed code then stays valid whichever backend is live. The cost is a Cloudflare dependency and about 10 ms.

**Risks:**
- workers.dev or trycloudflare.com may be categorized by corporate filters.
- No SSE (realtime already uses WS).
- The 100k requests/day limit is irrelevant at demo scale.

Files: `infra/worker-frontdoor/{wrangler.toml,src/index.js,set-target.sh}`.
