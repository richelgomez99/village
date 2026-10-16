# Generative UI for Village — landscape and build plan (researched 2026-10-15)

## TL;DR
Write **our own minimal schema shaped like A2UI v0.9 / json-render**: a flat adjacency list of components drawn from a fixed catalog. Claude emits it through a **tool call**, Core validates it with pydantic/zod, and the phone renders it with a roughly 60-line React renderer. Live changes go out as **RFC 6902 JSON Patch over SSE**. Don't take a dependency on any framework's runtime. Keep the wire format close enough to A2UI that "we speak A2UI" stays true in the pitch, and a real renderer could be swapped in later.

## Landscape

**Google A2UI** (https://a2ui.org, https://github.com/google/A2UI). Apache-2.0. v0.8 is legacy, **v0.9.1 is the current stable version** (blog post 2026-04-17: https://developers.googleblog.com/a2ui-v0-9-generative-ui/), and the repo lists v1.0 as a release candidate. Renderers exist for Lit, Angular, **React** and Flutter (GenUI SDK). It has four server-to-client messages: `createSurface`, `updateComponents` (a flat list of components where `children` are ID references), `updateDataModel` (a JSON Pointer path plus a value) and `deleteSurface`. The "Basic" catalog has Row, Column, List, Card, Tabs, Modal, Text, Image, Icon, Video, AudioPlayer, Divider, TextField, CheckBox, ChoicePicker, Slider, DateTimeInput and Button. Custom catalogs come through `catalogId`. It is transport-agnostic and runs over AG-UI, MCP, WS or REST. Fit: the flat list is easy for an LLM to emit and easy to patch, and it was designed for "pre-approved components only". For 5.5 hours, though, its data-binding and surface lifecycle are more than we need, and the React renderer's maturity is unverified.

**Vercel json-render** (https://github.com/vercel-labs/json-render, https://json-render.dev). Apache-2.0, about 18.7k stars. Packages: `@json-render/core`, `react`, `vue`, `svelte`, `solid`, `shadcn` (36 components) and React Native. You define a catalog with zod (`defineCatalog(schema,{components:{Card:{props:z.object({title:z.string()}),description}}})`), and `catalog.prompt()` **generates the system prompt** from it. The spec is `{root, elements:{id:{type,props,children}}}`. Streaming is "SpecStream": **JSONL lines of RFC 6902 ops** (`{"op":"add","path":"/elements/root","value":{...}}`), consumed by `useUIStream` and `<Renderer spec registry>`. It is backend-agnostic and works in plain Vite. Fit: this is the closest match to Village. It would be a reasonable choice if we want zod plus prompt generation for free. The risk is an API learning curve in a 5.5-hour build. The exact current npm version is unverified.

**Vercel AI SDK generative UI.** `ai` 6.x (6.0.26x patch releases in 2026). **RSC `streamUI` is still "experimental; use AI SDK UI for production"** (https://ai-sdk.dev/docs/ai-sdk-rsc/overview). The current pattern is tool calls rendered from `message.parts` in `useChat`. It is chat-centric and assumes a JS/Next server, so it is a poor fit for a FastAPI Core and a persistent app per role.

**CopilotKit AG-UI** (https://docs.ag-ui.com). MIT. AG-UI is an event protocol between agent and frontend over SSE: `RUN_STARTED`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `STATE_SNAPSHOT`, and **`STATE_DELTA` (an RFC 6902 patch, applied in the reference client with fast-json-patch)**. It is the transport and A2UI is the payload. CopilotKit ships `@copilotkit/a2ui-renderer`. It has a Python SDK (`ag-ui-protocol`), so it can work with FastAPI. Fit: the ideas are right (snapshot plus delta over SSE), but CopilotKit's runtime and React provider are heavy. **Borrow the event names**: `STATE_SNAPSHOT` / `STATE_DELTA`.

**MCP Apps / MCP-UI / OpenAI Apps SDK.** SEP-1865 has been the **first official MCP extension since 2026-01-26** (`io.modelcontextprotocol/ui`). A tool links to a `ui://` HTML resource, the host renders it in a sandboxed iframe, and the iframe talks over JSON-RPC `ui/*`. Hosts are Claude, ChatGPT, Goose and VS Code. The OpenAI Apps SDK added MCP Apps compatibility in Feb 2026, and `window.openai.*` is now only for ChatGPT-specific extras (https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt). MCP-UI (`@mcp-ui/client`, Shopify-originated remote-dom) is the predecessor. Fit: **wrong shape**. These UIs live inside a chat host, not a standalone phone PWA. One possible stretch goal is to expose the Village coordinator view as an MCP App inside Claude (unverified that this fits the time budget).

**Thesys C1** (https://docs.thesys.dev). A proprietary hosted API: an OpenAI-compatible endpoint that returns a UI DSL, rendered by `@thesysai/genui-sdk` / `<C1Component>`, with streaming. The licence is commercial or freemium. Fit: no. It's a vendor dependency, you don't control the catalog, and it is not Claude-native. It would also weaken the "we built it" story.

**Others.** LangGraph Generative UI (`push_ui_message` plus `useStream`/`LoadExternalComponent`) needs the LangGraph server. Google's Flutter GenUI SDK is A2UI on Flutter. Llama Stack has no notable gen-UI layer (unverified).

| | License | Plain React/Vite w/o their backend | Catalog approach | Incremental updates | Village fit |
|---|---|---|---|---|---|
| A2UI v0.9.1 | Apache-2.0 | Yes (React renderer, maturity unverified) | Basic catalog + custom catalogs | updateComponents / updateDataModel | Good wire model, heavy spec |
| json-render | Apache-2.0 | Yes | zod catalog, `catalog.prompt()` | JSONL RFC 6902 | **Closest** |
| AI SDK 6 | Apache-2.0 | Partly (chat-centric) | Tool → component | Tool parts stream | Weak |
| AG-UI/CopilotKit | MIT | Needs runtime | Via A2UI | STATE_DELTA (6902) | Borrow events |
| MCP Apps | open spec | No (needs an MCP host) | Arbitrary HTML iframe | JSON-RPC | Wrong surface |
| Thesys C1 | Commercial | SDK yes, API required | Theirs | Streaming DSL | No |

## Recommendation: our own A2UI-flavoured schema
Why: there are no runtime dependencies to debug at 2am. The FastAPI Core keeps the canonical spec per role, so patches are trivial, and safety comes from a fixed catalog, because unknown `type` values render nothing. Claude structured outputs **do not support recursive schemas** (https://platform.claude.com/docs/en/build-with-claude/structured-outputs), and the flat adjacency list (from A2UI and json-render) avoids recursion entirely. Strict mode limits are 20 strict tools, 24 optional params and 16 union params per request. The first call on a new schema also pays a grammar-compile cost, which is then cached for 24h, so warm it up before the demo.

Catalog (v1): `Screen, Stack, Header, BigButton, Text, Alert, ContactCard, TaskList, StatusGrid, SymptomLog, MedSchedule, MapPin`. Every prop is a primitive or a list of primitives.

```json
{ "role":"elder","lang":"es","dir":"ltr","theme":"high-contrast","root":"s",
  "elements":{
   "s":{"type":"Screen","props":{"title":"Hola, Rosa"},"children":["b1","b2","b3"]},
   "b1":{"type":"BigButton","props":{"label":"Necesito ayuda","icon":"sos","tone":"danger","action":"alert_family","confirm":true,"speak":"Llamando a tu familia"}},
   "b2":{"type":"BigButton","props":{"label":"Tomé mi pastilla","icon":"pill","tone":"ok","action":"log_med"}},
   "b3":{"type":"BigButton","props":{"label":"Llamar a Ana","icon":"phone","tone":"info","action":"call:+15551234"}}}}
```
```json
{ "role":"coordinator","lang":"en","root":"s",
  "elements":{
   "s":{"type":"Screen","props":{"title":"Mom's care — today"},"children":["st","al","tl","ms"]},
   "st":{"type":"StatusGrid","props":{"items":[{"k":"Last check-in","v":"09:40"},{"k":"Meds","v":"2/3"},{"k":"Mood","v":"ok"}]}},
   "al":{"type":"Alert","props":{"tone":"warn","text":"Evening dose not logged"}},
   "tl":{"type":"TaskList","props":{"source":"/data/tasks","assignable":true}},
   "ms":{"type":"MedSchedule","props":{"source":"/data/meds"}}}}
```

**Live patch over SSE.** Core keeps `spec[role]`. When the agent decides "add SymptomLog for everyone", Core runs one patch per role and fans it out on `GET /events?role=elder`:
```
event: snapshot
data: {"rev":1,"spec":{...}}

event: patch
data: {"rev":2,"ops":[
 {"op":"add","path":"/elements/sym","value":{"type":"SymptomLog","props":{"title":"¿Cómo te sientes?","options":["Bien","Mareada","Dolor"],"big":true}}},
 {"op":"add","path":"/elements/s/children/1","value":"sym"}]}
```
On the Python side, use `jsonpatch.apply_patch(spec, ops)` to keep the canonical copy. Include `rev`, and if the client sees a gap it reconnects and gets a fresh `snapshot`. `EventSource` auto-reconnects. Send `retry: 2000` and a heartbeat comment `: ping` every 15s so proxies don't drop the stream. The Daytona preview proxy has not been verified for SSE buffering, so test it early.

```tsx
import { applyPatch } from "fast-json-patch";
import { useEffect, useState } from "react";
import { CATALOG } from "./catalog"; // { BigButton, Text, SymptomLog, ... }

export function useSpec(role: string) {
  const [spec, setSpec] = useState<any>(null);
  useEffect(() => {
    const es = new EventSource(`${CORE}/events?role=${role}`);
    es.addEventListener("snapshot", e => setSpec(JSON.parse(e.data).spec));
    es.addEventListener("patch", e => setSpec((s: any) =>
      applyPatch(structuredClone(s), JSON.parse(e.data).ops, false, false).newDocument));
    return () => es.close();
  }, [role]);
  return spec;
}
function Node({ id, spec }: { id: string; spec: any }) {
  const el = spec.elements[id]; const C = el && CATALOG[el.type];
  if (!C) return null;                       // unknown type = safe no-op
  return <C {...el.props}>{el.children?.map((c: string) =>
    <Node key={c} id={c} spec={spec} />)}</C>;
}
export const App = ({ role }: { role: string }) => {
  const spec = useSpec(role);
  if (!spec) return <p>Loading…</p>;
  document.documentElement.lang = spec.lang; document.documentElement.dir = spec.dir ?? "ltr";
  return <Node id={spec.root} spec={spec} />;
};
```
Wrap each catalog component in a small "new" highlight animation (respect reduced motion) so the audience *sees* SymptomLog arrive.

## Prompting Claude to emit it
- Give it **two tools**: `render_app(spec)` for the first build of each role, and `patch_app(roles[], ops[])` for live changes. Use the Anthropic Messages API with `tools=[...]`. Put `strict: true` on them only if the schema fits within the limits above. Otherwise use non-strict tool use plus validation. The system prompt should contain the catalog: one line per component with its props, an a11y rule set ("elder: at most 3 BigButtons, labels of 3 words or fewer, native language, confirm on danger") and the two worked examples above. A prompt-generation trick borrowed from json-render: generate the catalog section of the prompt from the same zod/pydantic definitions with `z.toJSONSchema()` (zod 4) or `Model.model_json_schema()`.
- **Validation.** Core validates with pydantic, using a discriminated union on `type`, and checks that every child ID exists and the graph is acyclic. The client validates again with zod `safeParse` before applying anything. On failure, send the validator error back as the `tool_result` with `is_error: true` and retry once. Fallback: a hand-written template spec per role, so the demo never shows a blank screen. For patches, apply them to a copy server-side first and only broadcast if validation passes.
- Generate the views for different roles **in parallel** (one call per role) to cut latency. Keep the model's job small: choose and fill components, never write CSS or code.

## PWA in Vite
```ts
// vite.config.ts  (vite-plugin-pwa 1.x)
import { VitePWA } from "vite-plugin-pwa";
VitePWA({ registerType: "autoUpdate",
  workbox: { globPatterns: ["**/*.{js,css,html,svg,png}"], navigateFallbackDenylist: [/^\/events/, /^\/api/] },
  manifest: { name: "Village", short_name: "Village", id: "/", start_url: "/?source=pwa",
    scope: "/", display: "standalone", orientation: "portrait",
    background_color: "#000000", theme_color: "#000000", lang: "es", dir: "ltr",
    icons: [{ src: "/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" }] } })
```
- **Never cache SSE or API** (the denylist above). The service worker needs HTTPS, which Daytona preview URLs provide. One caveat: Daytona previews may show a warning or auth interstitial on first load, so check that phones can open the URL without logging in (unverified).
- **iOS:** there is no install prompt. Users must go to Share → "Add to Home Screen", so show a one-line hint. Add `<link rel="apple-touch-icon" href="/apple-touch-icon.png">` (180×180) and `<meta name="apple-mobile-web-app-capable" content="yes">` and `<meta name="apple-mobile-web-app-status-bar-style" content="black">`. A home-screen PWA gets its own storage, separate from Safari. Web Push only works after installation (iOS 16.4+). `navigator.vibrate` is **not supported on iOS Safari**. For the demo, the QR code → browser tab path is enough, and installing is optional.
- Encode the role and member in the URL (`/?m=<token>`) so the QR code carries the identity.

## QR codes
Client side: `qrcode.react` → `<QRCodeSVG value={url} size={256} level="M" marginSize={4}/>` on the coordinator/projector screen. Server side (FastAPI): `segno.make(url, error='m').save(buf, kind='svg', scale=8)`, or `qrcode[pil]`. Generate one QR code per member.

## Accessibility for elderly users (elder theme)
- **Text:** body 22–24px, buttons 28–32px bold, line-height 1.5, no text under 18px. Use `rem` so the system font scale (Dynamic Type / Android font size) is honoured.
- **Contrast:** aim for **WCAG 1.4.6 AAA 7:1** (AA is 4.5:1 for text and 3:1 for UI components under 1.4.11). Use solid colours and never rely on colour alone: every tone also gets an icon and a word.
- **Targets:** WCAG 2.2 **2.5.8 (AA) requires a minimum of 24×24 CSS px**, **2.5.5 (AAA) 44×44**, and Material recommends 48dp. For elders, use full-width buttons of at least 88px height with 16px+ spacing.
- **Input:** no swipes, long-presses or multi-finger gestures (2.5.1), and only a single tap. Any destructive or alarming action asks for confirmation through a second large Yes/No screen, with undo where possible.
- **Feedback:** give a visual state change plus `navigator.vibrate(50)` (Android only) plus a short audio cue. **TTS:** `speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance(text),{lang:spec.lang}))`. iOS requires the call to come from a user gesture, so speak on tap and not when a patch arrives. A "read aloud" button on each screen helps.
- **Motion and language:** honour `@media (prefers-reduced-motion: reduce)`. Set `<html lang dir>` from the spec (RTL for Arabic/Hebrew, using CSS logical properties such as `margin-inline-start`). Avoid timeouts, keep a single column with nothing hidden in menus, and keep wording plain.
- Use `<button>` elements with real labels, `aria-live="polite"` for newly arrived components, and visible focus outlines.

## Sources
- A2UI: https://github.com/google/A2UI · https://a2ui.org/specification/v0.9-a2ui/ · https://developers.googleblog.com/a2ui-v0-9-generative-ui/
- json-render: https://github.com/vercel-labs/json-render · https://json-render.dev/docs/streaming
- AI SDK RSC status: https://ai-sdk.dev/docs/ai-sdk-rsc/overview
- AG-UI state: https://docs.ag-ui.com/concepts/state
- MCP Apps: https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp · https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt
- Thesys: https://docs.thesys.dev
- Claude structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
