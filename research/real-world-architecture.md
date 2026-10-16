# Village: what it takes to really work (architecture memo, Oct 15 2026)

Scope: the parts that turn the demo into a product: proactive jobs, identity, hosting cost, reliability, app evolution and data. Each section ends with what to **build tomorrow (5.5 h, solo)** and what to **explain**. This memo builds on `research/{elevenlabs,daytona,generative-ui,anchor}.md`. **[VERIFY]** marks anything that hasn't been tested yet.

**Design rule that runs through all of it:** *the safety path is deterministic and never reads LLM output.* The dose ledger, the escalation state machine and the policy gate run on an operational store. Agent Memory and Claude make things richer (context, suggestions, UI), but nothing safety-critical depends on them.

---

## 0. Component diagram

```
                 Caregiver (web, setup agent)        Members' phones (PWA via QR)
                          │ WebRTC                          │ HTTPS + SSE
                          ▼                                 ▼
 Mom ──PSTN──► Twilio ──► ElevenLabs agents ──webhook──► cloudflared ──► CORE (FastAPI, laptop)
 Marco ◄─PSTN─ Twilio ◄── (mom-line, village-caller)        │      ┌───────────────────────────────┐
                 ▲  SMS fallback                              │      │ auth (JWT invites, caller-ID) │
                 └────────────────────────────────────────────┤      │ policy gate (pure functions)  │
                                                              │      │ dose-window state machine     │
                                                              │      │ scheduler tick + Clock (warp) │
                                                              │      │ outbox → memory/arize writers │
                                                              │      │ spec store (rev + JSON Patch) │
                                                              │      │ SSE hub · static/proxy /v/{id}│
                                                              │      └──────────────┬────────────────┘
                                                              │                     │ SQLite (ops store:
                                                              │                     │ ledger, members,
          ┌──────────────────┬──────────────────┬─────────────┴──────┐              │ consent, specs, idem)
          ▼                  ▼                  ▼                    ▼
   AWS Bedrock (Claude)  Daytona sandbox     SurrealDB Agent     Anchor Browser
   spec gen, extraction  build+vitest; Core  Memory (scoped      DailyMed read;
   (Haiku), proposals    PULLS logs/dist     facts, provenance)  phone-viewport QA
          │                  │ (egress allowlist: no calls back to Core)
          ▼                  ▼
   [prod] S3+CloudFront (published app bundles)  ·  EventBridge Scheduler → Lambda → Core /tick
   Arize (OTLP traces + evals) ◄── Core SDK spans, ElevenLabs post-call webhooks
```

---

## 1. Proactive behaviour: the dose-window state machine

### State machine

Every scheduled dose creates one `dose_window` row: `(id, village_id, med_id, due_at, state, attempts, next_check_at, version)`. All the times below are relative to `due_at` and configurable per village.

```
 SCHEDULED ──(now ≥ due−30m)──► OPEN ──log_dose──────────────────────────► TAKEN ■
                                 │                                          ▲
                        (now ≥ due+30m) / call Mom (reminder)               │ log_dose / Mom says yes
                                 ▼                                          │
                             REMINDING ──────────────────────────────► TAKEN_LATE ■
                                 │ Mom: "skip"/declines ─► REPORTED_SKIP ■ (SMS on-duty, no call)
                        (now ≥ due+60m) / call on-duty sibling
                                 ▼
                             ESCALATING ──ack (voice data_collection / SMS "1" / app tap)──► ACKED ■
                                 │ call_initiation_failure(no-answer|busy) / SMS + next in rota (+10m)
                        (now ≥ due+120m, nobody acked)
                                 ▼
                             UNRESOLVED ── SMS all members, red card on coordinator view
 Any open state ──(now ≥ cutoff = min(due+4h, next_due−2h))──► CLOSED_MISSED ■
 Gate overlay: log_dose when state ∈ {TAKEN, TAKEN_LATE} → BLOCK_DOUBLE_DOSE (say fixed script, notify).
              log_dose after CLOSED_MISSED → ASK_FAMILY (late dose may collide with next dose).
 Independent:  report_symptom with red-flag rule → REFER_911 script ("cuelgue y marque 911") + notify all.
               We never auto-dial 911.
```

The transition function is pure: `step(window, event, now) -> (window', actions[])`. Actions (`CALL_MOM`, `CALL_MEMBER(id)`, `SMS(id)`, `EMIT_SSE`) run afterwards. Each transition is a compare-and-set on `version`, so a webhook racing the tick loop can't dial Marco twice.

### Where the timer lives

| Option | Durability | Laptop-friendly | Verdict |
|---|---|---|---|
| APScheduler / `asyncio` jobs in Core | Jobs are lost on restart unless you configure a jobstore. Another dependency to debug. | yes | No |
| **Deadline table + 5 s tick loop in Core** (`SELECT … WHERE next_check_at <= clock.now()`) | Durable (rows in SQLite). Survives restarts and catches up on boot. | yes | **Tomorrow** |
| EventBridge Scheduler one-time `at(yyyy-mm-ddThh:mm:ss)` per deadline, with an IANA timezone | Durable and managed. 60 s precision. Completed one-time schedules still count against quota until deleted. | API destination via the tunnel | Prod option A |
| **EventBridge `rate(1 minute)` → Lambda → Core `/internal/tick`**, deadlines stay in the DB | Durable; the heartbeat lives outside the host. About 43k invocations/mo, inside the 14M free tier ($1/M after). | yes | **Prod default** |
| SQS delay queue | Max delay is 15 min. Can't express "9:00 pm". | | No |

Source: https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html, https://aws.amazon.com/eventbridge/pricing/. In prod, add a **dead-man's switch**: if `/tick` hasn't run for 5 min, alert the operator. A missed tick is the real way this product fails.

### Time-warp and model-off tests

- Core reads time only through `Clock.now() = real_now + offset`.
- `POST /admin/clock {"advance_min": 30}` moves the offset and runs a tick right away. The coordinator view gets a demo-clock chip ("20:31 ▸ +30m").
- On stage: confirm nothing at 20:00. Warp to 20:30 and Mom's phone rings. Warp to 21:00 and Marco's phone rings.
- **Tests run with no model:** pytest with `FakeClock` and a `FakeDialer`/`FakeSMS` that record actions. Table-driven cases cover:
  - the happy path and late dose
  - a double dose within the same window
  - a duplicate webhook
  - a no-answer that rolls over to the next sibling and then SMS
  - a restart in the middle of ESCALATING (rebuild state from the DB, no double dial)
  - the cutoff
- ElevenLabs is mocked at the HTTP boundary. The voice layer gets its own tests: ElevenLabs agent tests with `tool_mock_overrides` (see elevenlabs.md §9).

---

## 2. Identity and onboarding

### Model

```
Village(id, name, tz, plan, data_key_id)
Member(id, village_id, name, role ∈ {care_recipient, coordinator, caregiver, viewer},
       phones[E.164], lang, pin_hash(argon2)?, rota_rank, quiet_hours)
Consent(member_id, kind ∈ {ai_voice_outbound, sms, call_recording, health_view},
        granted_at, method ∈ {web_checkbox, verbal(conversation_id)}, text_version, revoked_at)
Invite/Device token: JWT HS256 {sub: member_id, vid, role, scp[], jti, exp}
Fact visibility label: logistics | health_private | recipient_only
```

**Permissions.** These are enforced in Core when it serves `/api/data`, never in the generated UI:

| Fact label | care_recipient | coordinator | caregiver | viewer |
|---|---|---|---|---|
| logistics | yes | yes | yes | yes |
| health_private | yes | yes | only with the recipient's `health_view` consent | no |
| recipient_only | yes | no | no | no |

The spec (the UI) holds no data. Data comes from role-filtered endpoints, so a hallucinated component can't leak a fact.

**Invites.**
1. Each member gets a QR with `https://core/v/{vid}/#t=<jwt>`. The token sits in the URL fragment, so it never reaches server logs or Referer headers.
2. On first load, the PWA POSTs it to `/auth/redeem`. That marks the `jti` used and sets an httpOnly cookie on the Core origin. Because Core proxies the app, it's one origin.
3. Revoke by adding the `jti` to a denylist. Invite TTL is 72 h; device tokens last 90 days.

**Inbound callers.**
1. The ElevenLabs conversation-initiation webhook receives `caller_id`.
2. Core looks it up in `Member.phones` and returns `village_id`, `member_id` and the schedule as dynamic variables.
3. Every tool body also carries `system__caller_id`, and Core re-checks it server-side.

Trust levels:
- **Known number:** allowed to make low-risk writes (`log_dose`, `report_symptom`) because every write keeps provenance.
- **Spoken PIN:** required for sensitive reads or changes (med list, adding a member). Caller ID can be spoofed.
- **Unknown number:** "I don't recognise this number; I'll let the family know." Nothing is disclosed.

For Mom, we accept known-number-only access to her own schedule and skip the PIN friction.

**Consent and disclosure.** The FCC's Feb 8 2024 declaratory ruling puts AI-generated voices under the TCPA's "artificial or prerecorded voice" rules: you need prior express consent, and the call must identify the caller (https://huntonak.com/privacy-and-information-security-law/fcc-issues-declaratory-ruling-that-tcpa-applies-to-ai-generated-voice-calls).
- The outbound dialer **refuses to dial without `Consent.ai_voice_outbound`**. Marco grants it when he redeems his invite, through a checkbox with versioned text.
- He can revoke it by saying "stop calling me" (an `opt_out` tool) or by texting STOP.
- ElevenLabs also requires telling users they are talking to AI and that the call is recorded (https://elevenlabs.io/docs/eleven-agents/legal/disclosure-requirement.md). The fix is the first message: *"Hi Marco, this is Village, an automated AI assistant for the Rivera family. This call is recorded."* Mom's line opens the same way, in Spanish.

**Tomorrow:** seed the members, the phones→member map in the initiation webhook, JWT invites in the QR, and a consent check in the dialer. A consent checkbox on the invite page is about 30 lines. PIN and the denylist: explain only.

---

## 3. Hosting and cost per family

**Don't keep a sandbox running 24/7.** At Daytona rates ($0.0504/vCPU-h and $0.0162/GiB-h), a 1 vCPU / 1 GiB sandbox costs about **$49/mo** and a 2/2 sandbox about **$97/mo**. That alone is more than the price point.

The real artifact per family is a **VillageSpec JSON plus a shared, versioned renderer bundle**. Daytona is the **build-and-test** step: vite build, vitest, then an Anchor QA tap. It's needed when the spec changes, or when Claude writes a custom component. After that:
- Core pulls `dist/` with `sb.fs.download_file`, because egress rules stop the sandbox from calling Core.
- It publishes to **S3 + CloudFront** at `/{vid}/r{rev}/`.
- The sandbox is then stopped. Set `auto_stop_interval=15` and `auto_archive_interval` to 1 day, so it doesn't keep holding disk quota.

Core keeps the APIs and SSE. This gives AWS a real role: Bedrock, S3/CloudFront and EventBridge.

**Monthly cost per family.** "Typical" assumes Mom calls twice a day for 2 min (120 min), plus reminder calls (15 min) and escalations (6 min), for a total of **about 141 agent-minutes**.

| Item | Rate (source) | Typical | Heavy (Mom 3×4 min/day ≈ 400 min) |
|---|---|---|---|
| ElevenLabs agent minutes | $0.08/min. Creator $22/275 min, Business $990/12,375 min: the same effective rate, overage $0.08 (elevenlabs.io/pricing/agents) | $11.28 | $32.00 |
| ElevenLabs LLM pass-through (Haiku 4.5) | billed separately **[VERIFY in UI]**; est. $0.005/min | $0.70 | $2.00 |
| Twilio voice | inbound $0.0085/min, outbound $0.014/min (twilio.com/voice/pricing/us) | $1.31 | $3.70 |
| Twilio number | $1.15/mo. Can be shared across villages via caller-ID routing | $1.15 | $1.15 |
| Twilio SMS | $0.0083 + ~$0.004 carrier per segment, ~40/mo. A2P 10DLC registration fees are extra (twilio.com/sms/pricing/us) | $0.50 | $1.00 |
| Bedrock Haiku 4.5 extraction | $1 in / $5 out per MTok (AWS model card). ~80 calls × (4k in, 0.5k out) | $0.52 | $1.50 |
| Bedrock Sonnet: nightly pattern review + about 4 spec edits | ~$3/$15 per MTok **[VERIFY]** | $1.50 | $3.00 |
| Daytona builds | ~10 × 5 min at 2 vCPU/4 GiB ($0.166/h) | $0.14 | $0.30 |
| S3 + CloudFront, EventBridge, Lambda | under free tiers or a few cents | $0.05 | $0.10 |
| SurrealDB Agent Memory, Arize | per-tenant share **[VERIFY pricing]** | ~$1.00 | ~$2.00 |
| **Total** | | **≈ $18** | **≈ $47** |

**What this means for pricing.** At $15/mo we lose money on voice. At **$29/mo with 200 included voice-minutes** we keep a roughly 35% margin on typical families, and charge heavy users through an overage or a tier.

Voice minutes are about 70% of the cost. The levers:
1. **Reminder calls don't need a conversational agent.** Use Twilio `<Play>` of pre-rendered ElevenLabs TTS plus `<Gather>` ("press 1 or say yes"). That's about $0.014/min, not $0.094/min.
2. Prefer an SMS or app ack for siblings, and call only on UNRESOLVED.
3. Silences over 10 s are billed at a 95% discount, which helps slow speakers.
4. Negotiate volume rates beyond Business.

---

## 4. Reliability

- **Core down during a call.** Set tool `response_timeout_secs: 5`. In the deterministic procedure, a tool error branches to a fixed `say`: *"No pude anotarlo ahora. No tome otra pastilla; voy a avisar a su familia."* The guardrail is "never confirm a dose the tool didn't confirm". Afterwards, the post-call webhook (HMAC, keyed on `conversation_id`) reconciles: an "unlogged dose claim" becomes a **pending item for a human to confirm**. It is never auto-logged. In prod, Core runs on ECS/Fargate behind a health check, and the laptop is gone.
- **Idempotency.** Every tool request stores `(idem_key → response)` for 24 h. The key is `conversation_id + tool + dose_window_id`, so a duplicate webhook gets the cached reply.
  - The gate separates *redelivery* (same conversation and window: "ya lo anoté") from a *real second dose* (a new conversation or an explicit second claim: BLOCK). Without this, a retried webhook would wrongly raise a double-dose alarm.
  - App writes carry client UUIDs.
  - Escalations dial only on a CAS state transition.
- **SMS fallback.** `call_initiation_failure` (no-answer/busy), or a call that ends without `acknowledged=true` in data_collection, triggers SMS with an ack link (`/ack/{esc}?t=jwt`) and a "reply 1" keyword through Twilio's inbound SMS webhook. After 10 min it moves to the next sibling in the rota. US A2P 10DLC registration takes days to weeks, so the demo uses a verified number.
- **Offline PWA** (key for the blackout demo).
  - The service worker caches the app shell, the last spec and the last data snapshot (in IndexedDB). It shows an **"Offline: as of 20:42"** banner.
  - Writes go into an outbox and replay with their UUIDs on reconnect.
  - Safety actions show **"Not confirmed yet"** while queued. They never turn green optimistically.
  - SSE/API are never cached, which is already in the workbox denylist.
- **SurrealDB and Anchor.** Use an **outbox**: the dose event commits to SQLite first. A worker then writes to Agent Memory with tenacity backoff (0.5→8 s, with jitter) and an idempotency key, and treats a 409 as success. The voice tool never waits on memory. For Anchor, use a circuit breaker. Cache DailyMed by SPL set id and version, since labels change rarely.
- **Generated app fails tests.** Run blue/green on the `published_rev` pointer. It moves only after build, vitest and the Anchor tap all pass. On failure, Claude gets the error as `tool_result is_error`. It has at most 2 repair attempts, then we keep the last good rev and tell the coordinator.

---

## 5. App evolution

- **Versions.** Table `spec_rev(village_id, rev, parent, ops[RFC 6902], author ∈ {setup, agent, human}, rationale, evidence_fact_ids[], status ∈ {proposed, approved, built, published, rejected, reverted}, test_report_url)`, with a full snapshot every 10 revs.
  - It lives in the **ops store**, not git-in-sandbox, because sandboxes are ephemeral and archived. Published bundles are mirrored to versioned S3.
  - A **rollback** is a new rev that applies the inverse patch, or simply moves `published_rev` back. History stays append-only.
- **Agent proposals.**
  1. A nightly job, or one triggered after each post-call, asks Agent Memory (`/reflect` or `/query` over the last 14 days) for recurring patterns.
  2. Claude may call only `propose_patch(ops, rationale, evidence)`.
  3. Core validates the ops against the catalog.
  4. The coordinator sees a card: *"Village suggests an Evening Routine card. Why: Mom called confused 4 of the last 5 evenings [links to the call moments]."* The choices are Approve, Preview or Reject.
  5. Approve runs the build → test → publish pipeline.
- **Capability boundary.** The spec is UI only. Proposals can't change policy-gate thresholds, the med schedule or the rota. Those are data changes that need coordinator confirmation, and med changes also need a source (prescription or DailyMed).

---

## 6. Data and privacy

| Lives in | What | Why |
|---|---|---|
| **Ops store** (SQLite → Postgres/RDS) | villages, members, consent, invites, med schedule, **append-only dose ledger**, escalations, spec revs, idem keys | deterministic. The gate reads only this. |
| **Agent Memory** | experiential facts from calls (symptoms, mood, preferences such as "prefers Marco in the evening"), with valid time, supersession, uncertainty and provenance `(conversation_id, turn, t_in_call)` | richer context and proposals. **Never on the safety path.** |
| ElevenLabs / Twilio | transcripts, audio, call records | set retention, and turn off Twilio recording |
| Arize | traces | no raw PHI in span attributes: hash member ids and redact utterances |

- **Isolation.**
  - Scopes are per village: `village/{vid}/shared`, `village/{vid}/private/{recipient_id}`, `village/{vid}/member/{mid}`.
  - **Each village gets a key bound to a principal** whose grants cover only `village/{vid}/**`. Member keys can only be attenuated (`POST /keys`).
  - Core picks the key by `village_id`, so a Core bug can't read across villages. Labels and lens filter but never widen access (`docs/surreal-agent-memory-agents.md`).
  - A **separate Context per village** is the stronger option for enterprise or regulated tenants. For now: one context, a scope per village, a key per village.
- **Forget.**
  - A member can say "forget that" or the coordinator can delete. This runs Agent Memory `POST /forget` with `dryRun:true`, shows the preview, then applies. The docs say forget *expires* records, so hard-purge semantics are **[VERIFY]**.
  - Deleting a village cascades through the ops store, S3 prefixes, Daytona sandboxes (by label), ElevenLabs conversations (`DELETE /v1/convai/conversations/{id}`) and Arize retention.
  - **Crypto-shredding:** each village has a KMS data key that encrypts phone numbers, PIN hashes and health fields. Destroying the key makes the backups unreadable too.
- **Encryption and compliance.** TLS everywhere; SSE-KMS on S3 and RDS. As a direct-to-family app, Village is likely not a HIPAA covered entity, but the FTC Health Breach Notification Rule does apply. For B2B (home-care agencies) we'd need BAAs: Bedrock is HIPAA-eligible, and ElevenLabs HIPAA requires Zero Retention Mode (which rules out batch calls).

---

## Tomorrow: implement vs mock vs explain

| Area | Implement (core of the demo) | Mock / shortcut | Explain on a slide |
|---|---|---|---|
| Proactive | dose_window table, pure `step()`, 5 s tick, Clock + `/admin/clock` warp, CAS transitions, real outbound calls to Mom and Marco | SMS fallback = one Twilio API call, no inbound keyword | EventBridge rate(1m) → Lambda heartbeat, dead-man's switch |
| Tests | pytest table for the state machine and gate (FakeClock/FakeDialer); 1 ElevenLabs tool test | | ElevenLabs simulation tests in CI |
| Identity | caller_id → member in the initiation webhook; JWT in the QR fragment → cookie; role-filtered `/api/data`; consent check before dialing; AI disclosure in first messages | seeded members/phones; consent checkbox prefilled | PIN, jti denylist, rota editing, opt-out tool |
| Hosting | Daytona build + vitest; Core proxies `/v/{vid}`; publish dist to Core static (S3 upload if AWS creds work: ~20 min) | | CloudFront, auto-archive, cost table |
| Reliability | idempotency table; fixed "couldn't log" script on tool error; keep last good rev on failed tests | offline banner + cached spec (workbox already set up) | outbox replay, circuit breakers, post-call reconciliation |
| Evolution | spec_rev with JSON Patch + rationale; one agent proposal card with Approve → SSE patch; rollback button | proposal triggered by a button, not a nightly job | pattern mining over memory, capability boundary |
| Data | Agent Memory writes with scope `village/{vid}/…`, provenance from conversation_id | single context and key | per-village keys/contexts, forget + crypto-shredding, BAAs |

**Build order for the proactive core (~75 min):** Clock → `step()` + tests → tick loop → dialer adapter (ElevenLabs outbound) → SSE events → warp chip in the coordinator UI.
