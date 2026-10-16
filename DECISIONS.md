# Village: architecture decisions

These decisions come from the architecting phase: all research read in full, local tests run, and the design canvas built. **Where this file disagrees with SPEC.md, this file wins.** Each decision gives its evidence.

Design canvas (storyboard + every screen): https://claude.ai/artifact/VVRJmDt6e4WDy2gnMHcwZz. A copy of the artboard sources is in `design/`.

---

## D1. Demo arc: Generate → Protect → Evolve → Anyone
*Why:* the first design made the generative part invisible; the screens read as a hand-built caregiving app. Generation is only visible when (a) you watch words become structure, (b) the same engine makes visibly different apps per person, and (c) the app changes because life changed.

| Act | t | Moment the room feels | Must work |
|---|---|---|---|
| Generate | 0:00–1:05 | Ana's sentence becomes a **village blueprint** (people, channels, rules), then **three different apps** (Carmen / Ana / Marco) | builder, blueprint view, per-role render, Daytona build, Anchor QA, QR join |
| Protect | 1:05–1:50 | Blue-lid **sticker scan** turns every phone green, then Carmen's **confused call** is blocked word for word and the **judge-as-Marco's phone rings** | lid scan → gate → live; voice tool → gate → verbatim say; outbound call |
| Evolve | 1:50–2:20 | Carmen mentions dizziness → Village remembers Tuesday's call → **proposes a change** → Ana approves → **every phone grows a new card** | memory recall with provenance, patch proposal, rebuild + QA, live patch |
| Anyone | 2:20–2:50 | A judge says a few sentences about their real family → **their own app on their phone** | fast builder path (≤45 s), catalog-only safety; backup = prepared blackout block |
| Close | 2:50–3:00 | "It takes a village. Now every group can have one." (autonomy line: "The agent acts on its own; code draws the lines it can't cross.") | Arize trace/eval ready for Q&A |

Evolve is **core**, not stretch: it reuses the build pipeline. Anyone needs a fast path (D9).

## D2. Hero medication: a blood thinner
Carmen takes **apixaban 5 mg twice daily**: yellow lid in the morning, blue lid in the evening. Blood thinners are on ISMP's high-alert list, so the double-dose block matters. Lisinopril 5→10 mg stays for supersession. Evening blue lid = apixaban + metformin + atorvastatin. (`data/villages/reyes_family.json` is updated to match.)

## D3. Input channels are chosen per person by the village (and generated)
The builder assigns each member channels from: `app` (role view), `lid_qr` (printable sticker per organizer slot), `phone_line` (ElevenLabs inbound), `outbound_calls` (consented), `fridge_card` (printable).
- **Lid QR sticker (primary for Carmen):** each sticker encodes `https://<host>/s/<slot_token>`, a per-slot signed token. One scan opens a one-tap "Anotado 8:02" page (no login: the token is the identity). It goes through the same gate (R-DOUBLE: a second scan in the window → report-only "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco." + notify (see D13)). It's deterministic, with no LLM in the path.
- **Phone line:** for questions and confusion ("¿ya me la tomé?"), where voice wins.
- **Printables** (stickers + fridge card with Village number, family word, 911 line) are generated per family. They're shown on stage as a printed card.
- NFC lid tags: roadmap. Photo of the organizer: evidence only, never decides. Screenshot-folder watching: impossible in a web app.

## D4. Realtime transport: WebSockets, not SSE
*Evidence (tested tonight, `research/public-url.md` + local tests):* through cloudflared quick tunnels, SSE and NDJSON are **fully buffered until the stream ends** (8 s for 8 events). WebSockets pass in about 10–20 ms. Phones and the Control Room use **one WebSocket per client** to Core (`/ws?village=…&m=<token>`). Messages: `snapshot`, `patch` (RFC 6902 on the view spec), `event` (ledger rows), `control` (reasoning, build log, QA, gate decisions). Reconnect with backoff; send a fresh snapshot on reconnect (rev gap).

## D5. Data plane: SurrealDB Cloud is the operational store; Core fans out
- SurrealDB Cloud (free instance) holds `village, member, view, event, dose_window, decision, consent, spec_rev`. Agent Memory holds facts with provenance (supersession, uncertainty, scopes).
- **Core subscribes with LIVE SELECT** (Python async SDK) and fans changes out over its WebSocket hub. Phones never connect to SurrealDB directly: one origin, no browser DB auth, no second domain for venue Wi-Fi to block.
- *Tested locally on SurrealDB 3.3.4:* the SPEC §4.1 schema applies (incl. `DEFINE ACCESS … TYPE RECORD`), LIVE notify p50 is 1.3 ms, `view` updates arrive as live UPDATEs, and **CAS works**: `UPDATE dose_window SET … WHERE version=$v` returns `[]` when stale (the query result is a list per statement; check the inner list).
- Safety path (gate, ledger, dose windows) reads only the operational store, never Agent Memory or LLM output.
- Fallback: `surreal start memory` locally (live queries work; embedded `mem://` does NOT support live queries).

## D6. Public URL: Tailscale Funnel (stable, free), Worker fallback
`https://richel-macbook.tail8feae0.ts.net` → Core :8787. No warning page, WebSockets fine. Enable tonight (admin click; DNS can take about 10 min). Fallback: a Cloudflare Worker on `*.workers.dev` proxying to a quick tunnel (`infra/worker-frontdoor/`, `set-target.sh`). ElevenLabs tool URLs use one env var (`system_env__core_host`), so switching hosts is one edit. Venue DNS may filter `ts.net`/`workers.dev`; test on arrival.

## D7. App delivery: Daytona builds + tests + serves; Core proxies
- The per-village build pack is: theme tokens (village layer), i18n strings, PWA manifest, the generated custom component(s) (e.g. `PillOrganizer` with this family's lid colors), and **generated tests** (floor tests: contrast, sizes, safety colors, actions → `/actions`; render tests per role).
- `vite build && vitest` in the sandbox (snapshot `village-kit`), then `vite preview :4173`. Core reverse-proxies `/v/{id}/*` with `X-Daytona-Preview-Token` + `X-Daytona-Skip-Preview-Warning: true`. The sandbox never calls out to Core.
- The runtime spec is live-patched from Core over the WebSocket. The build adds the identity, the custom code and the tests. Releases are blue/green on `published_rev`: if tests or Anchor QA fail, the last good rev stays live (max 2 repair attempts).
- Prod story (explain): publish `dist/` to S3 + CloudFront, then stop sandboxes (a 24/7 sandbox costs ≈ $49–97/mo).

## D8. Design system: fixed floor + village layer
- **Floor (locked, enforced by generated vitest in Daytona):** safety colors and words (Stopped/needs help `#A8331A`, Recorded `#2E6F42`, Needs a person amber), elder text ≥ 28px, elder buttons ≥ 88px, contrast ≥ 7:1 elder / 4.5:1 others, tap targets ≥ 48px, never color alone, read-aloud on every screen, catalog-only components, safety lines pre-written.
- **Village layer (generated):** accent from an approved range, relationship words ("Mamá", "王伯伯"), density per person, language/script/direction per person, real-world objects (lid colors), printables.
- **Type:** Fraunces (display), Atkinson Hyperlegible (body, Latin, made for low vision), Noto Sans fallback per script (SC, Arabic, Ethiopic…), JetBrains Mono (logs). Ground `#FBF6EE`, ink `#26211C`, sage `#2F6B57`.
- **i18n:** any language. Safety lines in a new language are translated at build time, **back-translated and checked (Arize eval)**, and fall back to simpler reviewed text if the check fails. Plan against NYC Local Law 30's 10 languages; demo es + zh + ar (RTL). Logical CSS properties; `Intl` for dates and numbers.

## D9. Builder: three speeds
1. **Blueprint first (≤8 s, streamed):** extract people, relationships, channels, needs and rules; this drives the blueprint view while the rest builds.
2. **Per-role views in parallel** (`render_app`, catalog-only, pydantic-validated, template fallback).
3. **Build pack** (custom component + tests) → Daytona. For **Anyone** (a judge's family), skip custom components: catalog-only views render via the already-built kit (no rebuild), so the app appears in about 20–40 s. The Daytona build + QA continue in the background and are shown as "verified" when done.
- Builder prompt v1 (Prompt Hub label `production`) deliberately omits on-duty escalation contacts; v2 fixes it (Arize improve loop, Q&A material).

## D10. VillageSpec additions (beyond SPEC §4.3)
```jsonc
"blueprint": {"people":[{"id","name","relation","lang","notes"}], "edges":[{"from","to","label"}],
              "needs":[{"id","text","source_span"}], "rules":["double_dose_guard", ...]},
"channels": {"m_carmen": ["lid_qr","phone_line","app:elder"], "m_marco": ["app:helper","outbound_calls"]},
"printables": [{"kind":"lid_sticker","slot":"evening","color":"#2F5FA7","label_es":"NOCHE"},
               {"kind":"fridge_card","lang":"es"}],
"custom_components": [{"name":"PillOrganizer","props":{"slots":["morning","evening"],"lid_colors":{...}}}]
```
New catalog entries: `PillOrganizer` (generated custom component for the hero), `HelperAnswer` (Marco's "is it my turn?" view), `Proposal` (evolve card with Approve).

## D11. Judge as Marco (consent on stage)
The judge scans "Be Marco" → **Join** screen (first name, mobile, AI-call consent checkbox) → consent row written → becomes the on-duty sibling. Outbound calls need **an upgraded Twilio account** (trial accounts can only call verified numbers). Escalation is **both** a phone call and an in-app "Village is calling you" banner (WebSocket), so it still lands if basement cell fails.

## D12. Everything else stands as in SPEC
LLM via `AnthropicBedrockMantle` → Anthropic fallback (no Converse); ElevenLabs native Claude for voice and structured procedures for verbatim safety lines; Anchor QA with deterministic Playwright at 390×844 + live view iframe; Arize tracing with GUARDRAIL spans and the improve loop; scheduler with the dose-window state machine + time-warp (`research/real-world-architecture.md` §1).

---

## Build tiers (replaces SPEC §9 table rows T1–T4)
| By | Gate | Contents |
|---|---|---|
| 12:00 | **G1 Protect core** | gate + tests (model off); lid-scan route → event → WS → two browser tabs update; double scan blocked |
| 13:15 | **G2 Generate** | builder (blueprint + per-role views) → kit renders elder/family/helper; Daytona build + proxy + QR join + consent; voice tool on the real number with verbatim say; outbound call to the consented judge |
| 14:00 | **G3 Evolve** | memory recall with provenance → proposal → approve → rebuild + Anchor QA → live patch on all phones |
| 14:20 | **G4 Anyone** | fast path for a new family; blackout block prebuilt as backup. **Freeze 14:20.** |

---

# D13. Fraud spotlight on an adaptable platform (locked Oct 15, late; supersedes D1/D2 where they differ)
*Evidence:* the four independent reviews in `review/` (A field analysis, B blind ideation, C judge simulation, D red team). All four agree: keep Village, lead with fraud, cut scope, and win the Devpost round with a measured number.

**Positioning.** *Village is the platform; the scam call is the moment.* "Describe your people; Village builds what each of them needs. When someone calls Mom asking for money in her son's name, it checks with the real son before she sends a dollar, and it learns from every attempt." (tagline superseded by D14) For finance judges: banks and brokers already ask seniors for a *trusted contact* (FINRA Rule 4512); Village makes the trusted contact active. Elder fraud was $7.75B in 2025 (+59%); quote the 2025 figure, not 2024's.

**What still proves the platform:** (1) Ana's one sentence spans health, money and people, so the blueprint shows three life areas, each with generated modules, plus three different per-person apps; (2) Evolve: the family hits a new problem and the software grows; (3) a second family generated earlier in the day by the same pipeline (the blackout block, `data/villages/block_blackout.json`), revealed in about 15 s with its build time and trace. The live "judge's family" act is CUT.

**Ana's sentence (new):** "Mom's seventy-eight and alone in Queens. She mixes up her pills, she almost wired money to someone pretending to be Marco last week, and last Thursday nobody went to see her because Marco and I each thought the other was going."

## The scam flow (headline, Protect act)
1. Carmen calls the Mom line: "Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares."
2. The voice agent calls the tool `report_money_request{claimed_member, amount, method, urgency, utterance, conversation_id, call_secs}` → Core → gate **R-MONEY-VERIFY** → creates `verification{id, claimed_member, status: pending, deadline: now+45s}`. The agent says, word for word: "Voy a confirmar con Marco ahora mismo. No mande dinero todavía."
3. **Out-of-band check** with the claimed member (consented): (a) an in-app prompt over WebSocket, "Did you just call Mamá asking for $2,000? [That was me] [That wasn't me]", and (b) an outbound ElevenLabs call with the same question. Either answer counts. A countdown shows on the projector and in Carmen's view.
4. The voice agent calls the blocking tool `await_verification{verification_id}` (waits up to 30 s; tool timeout 35 s) and speaks the returned `say` word for word:
   - `denied` → "Ese no era Marco. No mande dinero. Ana ya lo sabe."
   - `timeout` / no answer → **safe default**: "No pude confirmar con Marco. No mande dinero. Le aviso a Ana."
   - `confirmed` → "Marco dice que sí fue él. Village nunca envía dinero; hable con Ana antes de hacer algo."
5. An incident card goes to Ana; events `money_request`, `verification_*` and `incident` go to the ledger; Agent Memory records the fact with provenance (call + seconds); Arize gets GUARDRAIL + TOOL spans.

**New gate rules** (pure, model-off tests): **R-MONEY-NEVER** Village never moves money, buys gift cards or crypto, or shares account details; **R-MONEY-VERIFY** any money/gift-card/crypto/account request attributed to a family member is verified with that member through a known channel; **R-MONEY-DEFAULT** unconfirmed means "don't send" and notify the coordinator; **R-MONEY-UNKNOWN** a claimed identity not in the village is treated as unverified; **R-VERIFY-CONSENT** outbound verification calls only go to members with consent (otherwise app prompt only).

**Pills become a quick beat:** a lid scan turns every phone green. A second scan only **reports**: "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco." (no advice wording). The double-dose rule stays in the gate and its tests.

**Evolve (in Arize's loop words: detect → investigate → fix → verify → human approves):** an Arize session eval labels Carmen's calls `possible_fraud` (one seeded Oct 9 call + tonight's) → the agent queries its own traces (Arize SDK) plus SurrealDB facts with sources → proposes an `ScamCheck` "¿Es de verdad?" button for Carmen + a "Scam alerts" card for the family + a fridge card that puts the family word first → verify (Daytona build+tests, Anchor phone-size run, Arize evals) → Ana approves → live patch on every phone.

**Measured number:** a scam eval set (30 scam scripts across voice, text and "bank" variants + 20 benign family calls asking for money/help) run as an Arize experiment against the money gate + extraction prompt → "N/30 caught, M/20 false alarms". Built by the evals lane from 11:00.

**Release receipts instead of live builds on stage:** builds run during the day; the Control Room shows receipts (Daytona build + tests, Anchor run video, Arize eval scores), including **one deliberately failing build that was caught, fixed and released**, traced end to end.

**Prize focus:** Arize, SurrealDB, Daytona, AWS deep; ElevenLabs and Anchor honest. On stage, name three sponsors; the rest go on Devpost.

**Cut:** the live judge's-family act; all of L6 (voice design, live Medicare task, rota negotiation); live Daytona builds on stage; Chinese/Arabic (Spanish + English only; the i18n architecture stays). Stretch only if V4 is green by 14:00: Anchor checks the caller's story on public sites (e.g. NYC inmate lookup) and safely opens a texted link inside a sandbox.

**Backup idea (only if tonight's phone-loop spike fails):** "Callback": the same verify-by-calling-back loop for vendor bank-detail changes (B2B payment fraud); it reuses about 70% of the build.


# D14. Positioning is general (Oct 15, late; refines D13)
Village builds and runs software for **any specific group of people**; the Reyes family is the *demo group*. No "safety net" wording. **Tagline: "Describe your people. Village builds what each of them needs."** **Opening: "Apps are built for millions. Village builds one for your people."** Closing: "It takes a village. Now every group can have one." The blueprint shows the detected group type; the blackout-block reveal proves generality. See EXPERIENCE.md.

# D15. The hero is the self-building software (Oct 16, ~1am; supersedes D13/D14 positioning, keeps their mechanics)
**Identity:** *Village: software that builds itself around your people.* Supporting: *Describe your people; it builds what each of them needs, runs it, and rebuilds itself as life changes, without ever acting alone.* Close: *It takes a village. Now every group can have one.*
**Why:** the scam-call headline made the product feel small and blurry; the genuinely new part is the engine: software generated per person and per group that safely rewrites itself live (agent reads its own traces → writes the change → Daytona tests → Anchor clicks → Arize scores → a human approves → every phone changes). It also matches the judges' own theses (Daytona generate→test→fix, Arize detect→fix→verify, Anchor browser QA, SurrealDB shared memory).
**Arc: Build → Run → Rebuild (climax) → Anyone.** The scam call stays as the **life event** that triggers the rebuild (and still shows verification + safe default), but it's compressed; the rebuild gets the most stage time and is shown **live** (pre-warmed sandbox; the change adds an already-cataloged component so the build+tests take about 20 s; the pipeline is narrated on screen). Receipts remain as the fallback.
**Priority shift:** V3 (release pipeline) + V4 (Evolve) are now the heart, not polish. Protect their time: keep V1 lean (the in-app prompt is required; the outbound call is required but simple), no extras before V4.

## D15 addendum: conversation, not a form, plus guardrails
**Village is built and improved through ongoing conversation, not one sentence.** Founding is a short dialogue (Ana talks; Village asks 1–2 follow-ups: "Anyone else who helps?", "What does she like to be called?"). After that, every conversation refines the village: Carmen's calls, Ana's updates ("Marco switched to day shifts" → rota rebuild), Marco's answers. Line: *"Talk to Village about your people. It builds what each of them needs, and gets better every time anyone talks to it."*
**The Rebuild trigger is conversational + self-detected:** Arize session evals + SurrealDB facts surface the pattern → Village raises it with Ana ("Mom's had two of these calls. Want me to change her app?") → Ana says yes (voice or tap) → generate → Daytona test → Anchor click → Arize score → live on every phone.
**Guardrails for D15:** (1) human stakes in the first 20 s (Carmen, the $2,000 call, $7.75B) and the fraud/trusted-contact line in the close; (2) V3+V4 get protected time; the rebuild is a small catalog-based change with a pre-warmed sandbox, and recorded receipts are the fallback; (3) say the industry once: "caregiving and consumer fraud protection today; any group tomorrow."

# D16. Village chat (Oct 16, ~2:30am)
Every village (except its center, whose chat is the phone line) has a **group chat with Village as a participant**. Village posts incidents, proposals (Approve/Not now inline), release receipts and rota nudges; members talk to each other and to Village (`@Village …`). "@Village" messages route to: ask-why (read-only answer with sources), or a change request → proposal → leader approval → rebuild. Data: `message{village, author (member|village|system), text, kind: chat|incident|proposal|receipt|nudge|answer, refs[], at}`; WS message type `chat`. The chat replaces separate incident/proposal/decisions cards in member apps (they remain components for the Control Room). V2 for the feed + Village posts; `@Village` change requests V4.

# D17. Orchestrator answers to spec open questions (Oct 16 ~3am)
- **Elder text floor (refines D8):** actionable text (BigButton labels, status headline) ≥ 28 px; nothing on the elder view under 22 px; contrast ≥ 7:1. FS-5's generated floor test asserts exactly this split.
- **Control Room palette:** Direction A (dark) tokens from `design/ControlRoom.dc.html` / `Rebuild.dc.html` / `Founding.dc.html`. `Main.dc.html` (paper) is superseded. If the JFK27 projector washes out dark, the fallback is the same layout on paper tokens (one CSS variable set), decided at the 9:30 projector test.
- **Demo clock:** pinned to **Friday 2026-10-16 20:50 ET** (Marco on duty; the scam call at 20:52). `DEMO_CLOCK=2026-10-16T20:50:00-04:00` in `.env.example`; `reset_demo.sh` warps to it. All fixtures/policy already use Friday.
- **Reset helpers (names fixed now):** `POST /admin/reset` with body `{scopes: ["events_today","verifications","proposals","tokens","counters"]}` (requires `X-Admin-Key`); `uv run python -m core.tools.seed` (fixtures → SurrealDB), `uv run python -m core.tools.warm` (pre-warm Daytona sandbox + Anchor session + model grammar). `scripts/reset_demo.sh` calls these in order.
- **Round-1 clip at 12:15:** the pitch lane records it (10 min with the Marco phone + speaker); the orchestrator keeps merging.

# D18. Stage language and copy rules (Oct 16 ~3:20am)
- **Bilingual on stage, monolingual on the device.** Carmen's phone and voice line stay Spanish. Everything the *room* sees carries English: every Spanish line on the projector (Control Room, Founding, Rebuild, scam moment, chat mirror) gets an English caption directly beneath it in muted type; the live call on speaker is captioned in both languages in real time on the Control Room (ElevenLabs transcript → Claude translation, ≤1 s). The judge playing Marco only ever sees English. Pitch line: "Carmen hears Spanish; you're reading the captions."
- **Concrete, not abstract.** No vague verbs on screen ("reads its traces", "writes the change", "what could go wrong"). Every panel states the specific thing: *"Found the pattern: 2 calls in 7 days claiming to be Marco"*, *"Added a button for Mamá: ¿Es de verdad? (Is this real?)"*, *"16 of 16 tests passed · contrast 7.4:1"*. Numbers and names over adjectives. No "AI-speak" (agentic, seamless, intelligent, leverage, empower).
- **One idea per screen region.** If a judge can't repeat a panel's point after one glance, it's too much.

# D19. The rebuild proposes a receptionist, not a button (Oct 16 ~3:45am; refines D15/D16)
**Why:** an "Is this real?" button relies on Carmen remembering to press it under pressure. Generic call screeners filter by number reputation, which a spoofed/voice-cloned "Marco" defeats. The only thing that works is checking with the real person through a channel the scammer doesn't control, and the stronger software change is to run that check *before the call reaches her*.
**The change Village proposes after the 2nd attempt:** *"Let me answer unknown callers for Mamá."* Carmen's line gets a **receptionist mode**: unknown/unrecognized callers are answered by Village first ("Carmen's phone, this is Village. Who's calling?"); known family (caller-id match + family word) passes through; a caller who claims to be family or asks for money is held while Village verifies with the real member **on their own device** (app prompt + outbound call to the number on file; never a callback to the incoming number). Not confirmed → "Marco says this isn't him. I won't put you through." Carmen is told afterward (voice, Spanish) and the family chat gets the incident.
**Demo:** Act 2 (Run) = the first attempt reaches Carmen directly; she calls Village; hold + verify (existing). Act 3 (Rebuild, climax) = Village proposes the receptionist; Ana approves; pipeline runs (voice-line behavior + a "Village answers unknown calls first" card for the family + the fridge card line); then **live**: the presenter plays the scammer from a second phone calling Carmen's line; Village screens, the judge-Marco taps "That wasn't me", the scammer is refused; captions in English. Carmen's app keeps a plain "Llamar a Village" button; the "¿Es de verdad?" button is dropped.
**Production note:** one conditional-forwarding code on her real phone (no-answer/unknown → Village number); in the demo her line *is* the Twilio number. Still never a dialing or money action by Village.
**Honest market line for Q&A:** carrier blocking, Google Call Screen and Nomorobo filter numbers; bank trusted-contact programs act after a transfer attempt. Village verifies with the family *before* the call gets through, and it's woven into everything else the family already coordinates.

# D20. The agent, defined (Oct 16 ~4:20am)
See AGENT.md. One hand-written tool-use loop over Claude (Bedrock Mantle) with five roles (Founder, Watcher, Verifier, Builder, Explainer); every effectful tool call is a proposal intercepted by the pure gate; three memory layers (operational store, Agent Memory, working context); every run = a decision record + an Arize trace. Quality levers adopted: **capabilities catalog** (needs → capabilities → components, scored per person with reasons), **plan → critique → commit**, **consider_options before proposing** (2–3 candidates with tradeoffs; shown on the Rebuild screen), evals as triggers and feedback. **Custom components** are allowed through `create_component` + the release gate + a component contract; a village catalog grows per family, and a shared catalog (roadmap) promotes components with provenance. Hero: PillOrganizer already takes this path. Build/explain split in AGENT.md §6.

# D21. One site, one person at a time: how recognition and per-person software are shown (Oct 16 ~4:30am)
**Mechanics.** One URL per village (`/v/reyes/`). Identity rides in the invite: the QR/link carries a signed member token in the URL fragment → redeemed once → an httpOnly cookie on Core's origin. The same site then serves *that person's view*: Core looks up the member → role + profile → the `view` row generated for them (components, language, theme, read-aloud) and streams it over the WebSocket. Carmen is recognized differently: by caller ID on the phone line and by the per-slot token on each lid sticker. So one bundle, one URL, N different pieces of software.
**What differs is structural, not cosmetic:** Carmen: 3 big buttons, Spanish, read-aloud, no chat, light high-contrast theme; Ana: dashboard + chat + approvals + Ask Village; Marco: one question ("Is it my turn?") + verification prompts; Lucía: app-only, no calls. Each difference traces to a profile fact and a capability choice (AGENT.md §4), so "why does Marco get a different screen?" has an answer.
**How we show it on stage (and in the product):**
1. The three-apps screen prints **the same URL above all three phones**: "village.app/v/reyes · one site · three people".
2. **"View as" on the Control Room:** tapping Carmen / Ana / Marco morphs the live app on the projector (same URL, same session; Core re-issues the view for that member). The room watches the software change because the *person* changed.
3. **A small identity chip** on every member app: "You're Marco · Reyes village". Judges who scanned the family QR see "You're family".
4. **Ask Village:** "Why does Marco's screen differ from Ana's?" → the Explainer cites the profile facts and the capability choice.
5. Pitch line: *"Same address. Different software, because it's a different person."*

# D22. Pills: the organizer is the tool; Village guides refills and carries the state (Oct 16 ~4:45am; supersedes D3's lid stickers)
**Why:** a weekly pill organizer already answers "did I take it?" (the compartment is empty) better than any app, and a sticker to scan adds a task. The real problems are: (1) the organizer's state doesn't reach the family; (2) **refills** are where errors happen (a dose change like lisinopril 5→10 mg is missed and repeated seven times); (3) double doses come from the bottle, not the organizer.
**Decisions:** no lid stickers, no "I took it" button for Carmen. Health capability = **prescription record with history + sources** (supersession shown where it prevents a real error), a **refill checklist** for whoever is on duty on refill day ("lisinopril is 10 mg now, changed Oct 3 by Dr. Lee; was 5"), an **optional evening check-in call** (Village asks; Carmen looks at the organizer; the family sees the answer; she can decline), and the voice-path rule "already recorded, I won't advise on doses; I'll tell Marco" when she asks about another one. Print kit = fridge card only. The elder view keeps 3 buttons: Llamar a Village · Llamar a Ana · Necesito ayuda.
**Demo:** pills are a 10 s beat: Marco's refill card with the superseded dose (SurrealDB history, concrete). Live-sync proof = judges joining. `/s/{token}` stays in FS-1 as an optional generic check-in scan, not on the demo path. `lid_qr` leaves the channel list; `refill_day` and `check_in_call` join the capabilities catalog.

## D22 addendum: how Village beats the organizer, and the refill photo check
Village owns what the organizer is blind to: dose **changes** (refill checklist shows "10 mg now, was 5"), **conflicting sources** (uncertainty for a human), **coordination** (refill task with an owner, nudge, visible result), **patterns** (missed slots, symptoms after a slot), and **verification with people**. New capability (V4+ stretch): **refill photo check**: after refilling, the on-duty member photographs the organizer; a vision pass counts pills per compartment against the current schedule and reports mismatches as an *assist* with uncertainty ("Thursday evening: I count 2, expected 3; please check"), never a verdict; the result is an event with the photo as its source. Line: "The tray tells her whether she took it. Village makes sure the tray was filled right."

# D23. Make the agency visible (Oct 16 ~5:10am)
First-round judges read the Devpost page and the video only. Village must *read* as an autonomous, technically deep, scalable system. Adopted, ranked by impact per hour:
1. **Village's rounds (V4, ~45 min):** a nightly autonomous Watcher run on the clock with an action budget: evening check-in call (if enabled), "you're on tomorrow" nudge, refill-due reminder, open uncertainties, re-run of the scam eval set, pattern detection → proposals. Control Room and Devpost show: "Tonight Village did N things on its own and asked you about M." Scale story: rounds run per village on a schedule (EventBridge in prod).
2. **The agent fixes its own failing build (V3, ~30 min):** the Builder reads the failing floor test (contrast 4.1:1), patches the theme token, re-runs, ships; the trace (AGENT → TOOL daytona_build ✗ → LLM → TOOL daytona_build ✓) is a Devpost screenshot. Daytona's generate → test → fix with the agent in the loop.
3. **Autonomy ledger (V2, ~15 min):** every decision record tagged `mode: acted_alone | asked_human | refused`; counts per day on the Control Room, the family chat ("Village's week") and Devpost.
4. **Founder does work (V2, ~30 min):** during founding Village checks the listed medications against DailyMed (REST) for interactions and places the consent/availability call to Marco before showing the draft ("Marco confirmed Tue/Thu/Fri/Sat and agreed to calls").
5. **Devpost + video rebuilt around autonomy (tonight):** hero GIF = receptionist refusing the scammer; architecture diagram = five roles, the loop, the gate, the release gate, three memory layers, sponsors in place; autonomy counts; the measured scam number; a four-line scale section; the chat positioned as "the agent as a participant; joins your WhatsApp next".
Role names (Founder, Watcher, Verifier, Builder, Explainer) appear on screen and on the page: they are real, and judges should see a multi-role agent, not a chatbot.

## D24: "It takes a village" features, sized so scope stays flat (Oct 16)
Fourteen features raised after the screen pass (needs/offers, carer load, handoffs, modes, Carmen's own rules, the charter, outward calls, guest notes, weekly digest, "what Village knows about me", incident→test, village types, governance escalation, consent per affected person). Plan: `docs/VILLAGE-FEATURES.md`. **Today:** #5 Carmen's rules (data + copy, V2), #11 every incident becomes a test (V4, 30 min, 006 T035), #2 carer-load check in the nightly round (V4, 20 min, 006 T036). **P2** (designed; build only if V4 green by 14:00): handoff message, weekly digest, consent per affected person. **P3:** boards + Devpost sentences only. No new tables or contract changes today; no new stage time. **Why:** the demo proves the center is protected; the village is the people carrying weight together, and the page must show that shape without moving today's cut lines.


# D25. Orchestration on the day (Oct 16, 10:25; orchestrator)
- The orchestrator is a Claude session (Fable) in c11; **implementation lanes are Codex sessions** (`codex --yolo`, gpt-5.5), one per git worktree, launched as delegates of the orchestrator. Claude architects, briefs, merges, tests and tags; Codex implements against each branch's `tasks.md`. Lane briefs live outside the repo; each lane keeps `LANE-REPORT.md` in its worktree and signals `READY FOR MERGE Vn`.
- Lanes at 10:25: core (`001-core-spine-gate`), gate (`lane/gate`, `core/gate/**` only), kit (`004-kit-control-room`), voice (`002-verification-loop`), builder (`003-founding-generation`). Release/evals/memory start when Daytona/Arize/SurrealDB keys are in. Core and gate are split onto two branches so both can commit without conflicts; `services.py` stays core-owned.
- Hacking started late (bundle cloned at 09:55, bootstrap 10:15): V0 target slips to ~11:15; later cutoffs stand, cut lines per LAYERS.md apply.
- SurrealDB Cloud is not provisioned yet: Core must boot against a local `surreal start memory` or an in-process store with the same interface when `SURREAL_DB_URL` is empty; the cloud is wired in when the credentials land. D5's "phones never talk to SurrealDB" stands.
- Tailscale on this Mac is the Homebrew userspace daemon (`tailscale --socket ~/.tailscale/tailscaled.sock`), not the app; the Funnel URL is unchanged (`https://richel-macbook.tail8feae0.ts.net`).
- spec-kit CLI on the Mac is 0.8.x (`--non-interactive` removed); `bootstrap_speckit.sh` was patched to drop the flag. `/speckit-*` commands are not used; `tasks.md` is the source of truth.

# D26. Rate limit: kit lane moves to Claude (Oct 16, 10:30)
Five Codex (gpt-5.5) lanes share one OpenAI org limit of 1M tokens/min; every lane lost turns to `stream disconnected: rate limit` and the kit lane had zero commits after 20 minutes. Decision: Codex keeps **core** and **gate** (critical path, two sessions fit the limit); **kit** is implemented by a Claude Opus subagent in the same worktree/branch; voice and builder are paused at their V0/V2 checkpoints and resume one at a time. Codex config gained `stream_max_retries`/`request_max_retries` so later turns retry instead of dropping.
- D26 addendum (10:40): the **release** lane (005) also runs on a Claude Opus subagent, started early because the live rebuild is the heart of the pitch (D15) and the most integration-heavy; Codex keeps core, gate and voice (three sessions). Merged lanes are tagged (`gate-v0`, `spine-v0`); `LANE-REPORT.md` merges by union (`.gitattributes`).

# D27. Core port is 8790 (Oct 16, 10:50)
Port 8787 on this Mac is held by an unrelated local Python 3.9 process running since Tuesday (not killed: not ours). Core runs on **8790** (`CORE_PORT`/`CORE_URL` in `.env`); Tailscale Funnel maps `https://richel-macbook.tail8feae0.ts.net` (443) → 127.0.0.1:8790. Nothing else changes: ElevenLabs tool URLs use the Funnel host; lanes use `CORE_URL` for local checks.

# D28. Builder lane moves to Claude; Codex keeps one session (Oct 16, 11:30)
Even with `stream_max_retries`, two Codex sessions on the shared 1M tokens/min org limit lose most turns. Codex also loses the single core session (each agent round-trip resends ~150k tokens); core V1 is finished by a Claude Opus subagent from the Codex commits; builder V2 continues on a Claude Opus subagent from the Codex commits; kit V2, release V3, evals and memory are Claude subagents (Max plan). Codex remains the implementer of record for core and the earlier gate/voice/contracts work.

# D29. Founding is a full discovery conversation (Oct 16, 11:55; operator)
The one-sentence opener is not enough. Founding is a real intake dialogue (8–12 Village turns, one question at a time, reflecting back what it heard, skipping what it already knows) that ends with the whole village understood: every person and role (incl. outsiders: neighbor, aide, pharmacy, doctor), how each may be reached, health, money/impersonation exposure, coordination, **household needs** (groceries/meals, bills/insurance, appointments/transport, home safety, keys, loneliness), the center person's own rules and consent. From that the Founder derives what to build per person (capabilities with reasons), what Village watches, what it may do alone and what it must ask. Two modes: `--replay` full transcript (product video, Devpost) and `--fast` condensed path (opener + 2 questions) for the 30-second live stage beat; both produce valid specs that differ in captured needs. The ElevenLabs "Village Setup" agent follows the same turn policy (`prompts/setup_agent.md`).

# D30. The platform is the project; Reyes and West 147th St are two villages it built (Oct 16, 12:05; operator)
Framing rule for every lane from now on, enforced in code and on screen:
1. **Village id keys everything**: every record, span, LIVE query, WS frame, fake sequence, ledger row and Control Room region. `grep -ri carmen core kit --exclude-dir=tests` outside `data/` must return nothing (at 12:05 it returned 265 hits in 30 core files; a platform sweep fixes them).
2. **Founding creates a village from the intake loop**; fixtures are replay only. The block village is recorded through the same path so both come from conversations.
3. **Rules are parameters, not code**: quiet hours, verifiers, the family word, escalation order come from the village spec and are read by the pure gate. One gate test runs the same rule (P-QH-01, R-MONEY-DEFAULT) against both village specs with different params.
4. **One renderer, many apps**: the same catalog and renderer draw every village's views; the Anyone beat proves it only if the village switch is clean (every region re-keys and clears).
5. **Platform face**: Control Room header "Village" + village switcher + "New village"; the empty state is the founding. Navigation = platform → pick or start a village → watch it work.
6. **The pipeline is village-agnostic**: the release lane built the block in 13.4 s; that number sits next to the Reyes number in README/Devpost under "How Village builds any group": intake → spec → catalog render per role → gate → release pipeline → live patch.
Pitch line after the block reveal: "Same code, no Reyes anywhere in it. Describe your group and it builds yours." Table demo if the intake loop is live: a judge describes their own group for 30 seconds and watches the cards appear. (The operator numbered this D26; D26 was taken, so it is D30.)

# D31. Voice line rules from the first live call (Oct 16, 12:45; operator review)
1. **Usted, always.** Carmen is 78; the whole call is formal. Prompt rule at the top; the gate's `say` lines are already usted.
2. **AI disclosure first.** Inbound greeting: "Hola, soy Luz, la línea de la familia Reyes. Soy un programa, no una persona. ¿Cómo está?" Outbound (Village Caller) adds the family word after the disclosure. Spanish only on the phone; the projector captions carry English; language detection answers English callers in English (the presenter does not speak Spanish).
3. **Guardrails must never touch the refusal.** The ElevenLabs prompt guardrail fired three times on Village's own "No mande dinero" lines (passed this time). Scope: block only offers to send/buy or requests for numbers; never block "don't send" or any `say` returned by a tool.
4. **Every tool the agent can call has a Core handler** (`ask_family` returned 404 on the first live call: Carmen asked Marco to call tonight and nobody got the message).
5. **The live agent is frozen**: no config push without the orchestrator's OK; every referenced dynamic variable has a default; Core's init webhook returns every variable.

# D32. Prize focus for the rest of the day (Oct 16, 12:50; operator)
Cash on the table: 1st $3,000 / 2nd $1,000 / 3rd $500; Best Use of Daytona $1,000, Arize $500, Anchor $500, SurrealDB $500 (partners judge Best Use across all teams from the page); ElevenLabs = Scale-tier subscription, AWS = 20 × $75 credits. Order of work: (1) **the rebuild beat live** (Daytona, Anchor, Arize and placement all score off the same 50 seconds); (2) **Devpost sponsor table**: for each of Daytona, SurrealDB, Arize, Anchor, ElevenLabs, AWS: three unmistakable bullets, code paths, one measured number; (3) **SurrealDB visible on screen**: a fact-history card (lisinopril 5 → 10 mg, source, as-of) in the demo and the hero screenshots, wording matched to their brief: typed, time-aware, supersedes rather than overwrites, traced to source, shared across agents; (4) the scam eval number from the Arize experiment in RESULTS.md and the pitch (done: 30/30, 0/20); (5) nothing more for Anchor beyond the receipt screenshot and live-view link.

# D33. Founding is a scene, not a dashboard (Oct 16, 13:05; operator + orchestrator screenshot review)
The Control Room founding view showed every row at once (all stamped 13:58), the meter at 10/10 mid-way, no dialogue, no phones, an empty right column: nothing showed that saying one thing made Village think and change something. From now on the founding scene is **cause → effect, paced by the answers**:
- Left: **the conversation** as a transcript (the founder's words, then Village's one-line "now I know" + its question), typed live (Reyes: Ana at the keyboard) or audio-synced (block: a pre-recorded call plays, lines appear as they are spoken).
- Middle: **Village thinking and doing**, one block per answer: Heard → Knows → Doing (ledger rows running → done with real timings) → **Will build** (notes with reasons: "Refill checklist for Marco · he fills the organizer on refill day").
- Right: **the village taking shape**: coverage meter + gap list, people cards appearing one by one; below: **phone mirrors that gain cards as each capability is decided** (progressive patches), each new card sliding in with a NEW tag one second after its "will build" note.
- Nothing appears before its cause; the LIVE call panel collapses when there is no call. Two stage modes: Reyes = Ana types (live model), block = recorded audio + synced transcript (voice2 generates the audio with ElevenLabs voices). `?fake` replays follow the same pacing.

# D34. Reset must clear the whole demo state (Oct 16, 12:55)
`POST /admin/reset` (and `scripts/reset_demo.sh`) clears events today, verifications, **proposals** (in-memory on the evolve lane), tokens, counters, and re-seeds both villages; the demo arc is run twice from a reset before the freeze. Restarting Core also clears proposals: re-trigger with `POST /villages/{id}/evolve/trigger` if a restart happens mid-rehearsal.

# D35. A rebuild changes the right place (Oct 16, 13:05; operator)
After the live rebuild, the patch had added a floating paragraph under "No alerts right now". Rule: a proposal's ops change the *right place* in each person's app, in that app's own structure (a life-area status line, a card inside that area, one line under the person's headline), never a loose text block; every added card has a title, a "new today" tag and a "why"; views stay ≤ 12 elements.

# D36. Same village, new needs: Thanksgiving (Oct 16, 13:10; operator; only if green by 13:50)
Not a third village. The **Reyes village itself** gets a new kind of need: Ana writes in the chat "@Village, we're doing Thanksgiving at Mom's on the 27th, twelve people, Marco brings the turkey, Lucía comes in on the 11:40 train…". Village classifies it as a change request, proposes "Add Thanksgiving to the village" (a new life area with who-brings-what, pickups, the day-of schedule, grandpa's low-salt plate), Ana approves, the release gate runs, and every app grows the right card in the right place (D35): Ana the plan, Marco "you bring the turkey · pick up Lucía at Penn Station 1 PM", Lucía "bring the pie · 11:40 train", Carmen one Spanish line "El jueves vienen todos. Marco trae el pavo." This proves the rebuild is general (not only safety) and that the village is the people carrying a life together, not a care app. Shown as the table demo / Devpost GIF; on stage only if time. Cut line 13:50.

# D37. The receptionist is graduated and it is Carmen's rule, not Ana's (Oct 16, 13:40; operator)
From the first live screened call ("Richard from church" never got through): screening everyone is too much wall. Rule: **known numbers ring straight through**; an **unknown caller** is asked name, relationship and purpose, one question at a time, and hears one honest sentence ("Carmen asked Village to answer unknown numbers first"); a **plausible non-money caller is offered to Carmen** ("Richard, from church, is calling. ¿Quiere hablar con él?") and she decides (today: a message + callback, since one call can't be bridged; production: warm transfer); only **money or family-claim calls are held and verified with the real family member**. Ana is **informed**, never asked who her mother may talk to. The proposal card says so under "What stays the same"; Carmen is told at the evening check-in and can turn it off by saying so. Pitch answer to "isn't that control?": with her consent it is a receptionist; without it, it would be surveillance, which is why Village asks her first.

# D38. Demo actors: AI-played family members in the chat, labeled (Oct 16, 13:45; operator)
For the demo and the table, Lucía and (optionally) Marco are played by small personas (Haiku, persona from the spec) that reply in the family chat when Village addresses them (a swap question, a nudge, a plan item): "Sure, I can take Saturday." Every such message carries a visible **demo** chip and the pitch says it out loud ("Lucía and Marco are played by the system today; Ana is me; Marco's tap is the judge"). The safety moments are never acted: the verification tap and the approve stay human. Env `DEMO_ACTORS=lucia,marco`; off by default outside the demo.
