// Stable front door on <name>.<account>.workers.dev -> current cloudflared quick-tunnel URL.
// Target lives in the TARGET var; change it with:  ./set-target.sh https://xxxx.trycloudflare.com
// Proxies plain HTTP (webhooks, static, API) and WebSocket upgrades (pass-through, no Durable Object needed).
export default {
  async fetch(request, env) {
    const inUrl = new URL(request.url);
    const target = (env.TARGET || "").trim();
    if (inUrl.pathname === "/__frontdoor") {
      return Response.json({ target, ok: !!target, now: new Date().toISOString() },
        { headers: { "cache-control": "no-store" } });
    }
    if (!target) return new Response("Front door has no TARGET configured", { status: 503 });

    const t = new URL(target);
    const outUrl = new URL(inUrl.pathname + inUrl.search, t.origin);

    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", inUrl.host);
    headers.set("X-Forwarded-Proto", "https");
    const ip = request.headers.get("cf-connecting-ip");
    if (ip) headers.set("X-Forwarded-For", ip);

    // WebSocket: forwarding the Upgrade request via fetch() returns a 101 with .webSocket,
    // which Workers splices through to the client unchanged.
    if ((request.headers.get("Upgrade") || "").toLowerCase() === "websocket") {
      return fetch(outUrl.toString(), { method: "GET", headers });
    }

    const resp = await fetch(outUrl.toString(), {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
    });

    // Rewrite absolute redirects that point at the tunnel back to the stable host.
    const loc = resp.headers.get("Location");
    if (loc && loc.startsWith(t.origin)) {
      const h = new Headers(resp.headers);
      h.set("Location", inUrl.origin + loc.slice(t.origin.length));
      return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: h });
    }
    return resp;
  },
};
