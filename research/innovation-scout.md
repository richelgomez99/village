# Innovation scout: newest sponsor features → Village ideas (Oct 15 2026)

Scope: features each sponsor **shipped or announced Jul–Oct 2026**, and how Village could use them. This file does not repeat the per-sponsor deep dives in `daytona.md`, `elevenlabs.md`, `anchor.md`, `surrealdb.md` and `generative-ui.md`, which cover setup, gotchas and core wiring. Sources are listed at the end. "Fit" runs from 1 (ignore) to 5 (build it).

---

## 1. What's new, per sponsor

### Daytona (changelog, v0.193 → v0.224)
| Date | Feature | Village use | Fit |
|---|---|---|---|
| Jul 29 | **Sandbox fork + snapshot-from-sandbox now stable** | Fork the live family-app sandbox to try a proposed UI change. The original keeps serving the phones; promote or discard the fork. | **5** |
| Jul 16 | **WebSocket sandbox event subscriptions** in SDKs | Stream sandbox lifecycle (creating → started → forked) into the "build log" panel with no dashboard webhooks. | 4 |
| Jul 17 / Jul 14 | **Sandbox TTL**; historical metrics; auto-pause interval | Hygiene: give each village a TTL, and show a CPU/mem sparkline per village in the coordinator view. | 3 |
| Jul 27 | **Pre-signed file upload/download URLs**, typed errors | Anchor's QA screenshots/MP4 or the generated `spec.json` handed to the browser without proxying bytes through Core. | 3 |
| Jul 2 / Oct 7 | **Computer-use as MCP tools**; mouse/keyboard *hold* endpoints | A Claude agent drives a desktop sandbox. This overlaps with Anchor, so use it only if you want a "Daytona-native QA" talking point. | 2 |
| Aug 18 | **Warm pools API**, spot GPUs, **per-sandbox OTel override** | Warm pool gives an instant village on stage (support-gated). The OTel override sends sandbox spans straight to Arize with the village id. | 3 |
| Aug 11 | Snapshot ops by name; **outbound proxy on create** | Pin egress so the generated app can only reach Core. Good for the safety story. | 2 |
| Sep 26 | KVM sandbox param | Not needed. | 1 |
| Oct 12 | Per-call region on create | Not needed. | 1 |

### Arize AX (release notes)
| Date | Feature | Village use | Fit |
|---|---|---|---|
| Jul 29 | **Signal GA**: scans traces on a schedule, groups failures into ranked *issues* with evidence and proposed fixes. Repo PRs are Enterprise-only. | Signal finds "Mom-line misreads 'la azul' when the caller code-switches", and that issue seeds the self-improvement loop. Minimum cadence is **3 h**, so seed traces tonight. | **5** |
| Sep 2 | **Agent-as-a-Judge on all plans**; **Alyx can analyze Signal issues** | A judge that *reads the whole call trajectory plus the Memory writes* to grade "did the gate decision match the facts?" | **5** |
| Jul 1 | 7 new session/trajectory templates: **Session Frustration**, Goal Completion, Path Efficiency, Session Resolution… | Session Frustration on Mom's calls is the elder-UX metric. Goal Completion covers "dose logged". | **5** |
| Aug 12 | **Audio and images render in traces/datasets/queues**; **image LLM-as-judge**; space-scoped experiments via CLI; `x-project-name` routing | Mom's call audio inline in the trace. Anchor screenshots judged for elder accessibility. One project each for `mom-line`, `builder` and `rumor`. | **5** |
| Sep 8 | Session/trace-level annotation queues; remote evaluator runs emit traces | Sibling thumbs-down on a summary lands in a queue as a whole session. | 3 |
| Oct 7 | **Webhooks for `PROMPT_VERSION_LABELED`/`CREATED`, `EVALUATOR_VERSION_CREATED`** (HMAC) | Labeling a prompt `production` in Prompt Hub fires a webhook, and Core pushes it to the ElevenLabs agent branch. This closes the loop. | **5** |
| Sep 29 | **Alyx builds dashboards** | Ask Alyx live: "dashboard of gate BLOCKs by caller language". | 4 |
| Sep 17 | Alyx long-term memory | Talking point only. | 2 |
| Sep 26 | Jev-as-a-Judge (typed bool/choice structured evals) | Cheap high-volume `gate_correct: bool` over 50 simulated calls. | 3 |
| Skills/MCP (docs) | `ax` skills + Arize MCP | Claude Code builds evaluators and datasets via the skills during the build. That's process, not product. | 2 |

### ElevenLabs (changelog)
| Date | Feature | Village use | Fit |
|---|---|---|---|
| Sep 28 | **Eleven v4** (more expressive, better cloning across 90+ langs) and **v4 Turbo (~100 ms)** | Mom-line voice on v4 Turbo; the evening brief on v4. Lead with "v4" in the pitch. | **5** |
| Sep 28 | Text to Dialogue continuity; **PVC "instant variant"** | Two-voice evening brief (narrator + Mom's own words quoted). | 3 |
| Aug 24 | **Procedures GA**; **CLI v1.0** (branches); **triage tickets**; realtime `context_usage` | Structured "dose reported" procedure (already planned). Triage tickets can be filed automatically from Arize Signal issues. | 4 |
| Oct 5 / Oct 12 | Procedures compile on save; **merge proposals with approvals**; deployment history; **workflow end-node outcomes**; **strict tool overrides** | The self-improvement loop lands as a *merge proposal* that a human approves. Use the end-node outcome (`logged`/`blocked`/`escalated`) as the Arize label. | **5** |
| Jun 22 → Aug 10 | Tests: success-conditions array, **`repeat_count` up to 50**, **tool mocking + test-specific overrides**, numeric evaluation scoring | "20 simulated Moms" with mocked gate responses, run 50×, pass rate into Arize. | **5** |
| Sep 7 / Sep 14 | **Twilio answering-machine detection**, data-collection value constraints, call queueing, DTMF (Aug 31) | Escalation call to the sibling hits voicemail → AMD → leave a structured message, then try the next sibling. DTMF "press 1 to accept shift". | 4 |
| Jul 13 | **Nested agent transfers** (push/pop), backchannel detection, per-agent sentiment | Mom-line pushes to a "symptom triage" sub-agent and pops back. Backchannel filtering helps elderly "mm-hm" speech. | 3 |
| Jul 27 / Aug 31 | Batch-calling CSV export; batch campaign context metadata | Blackout block: batch "rumor correction" calls, results exported to Arize. | 4 |
| Jul 20 | WhatsApp typing indicators (WhatsApp channel exists) | Blackout: WhatsApp channel for neighbors. SMS channel is **unverified**. | 2 |
| Oct 12 | TTS **audio effects** (reverb, distance, background) | Not useful. Skip. | 1 |
| Sep 11 | **Scribe v2 Medical** | Re-transcribe Mom's calls for drug-name accuracy ("lisinopril" vs "listen a pill") and write provenance spans. | 3 |
| Memory | No agent-memory feature found in changelog | That's fine: SurrealDB owns memory, which is a cleaner sponsor split. | — |

### Anchor Browser (blog + docs; no public dated changelog)
| Date | Feature | Village use | Fit |
|---|---|---|---|
| (docs, current) | **Automation Tasks with deterministic steps + AI fallback + self-healing** (`task.healed`, draft version) | When the UI evolves, the QA task self-heals on stage (see anchor.md §8). | **5** |
| Aug 21 | New AI step pricing (Light/Standard/High) | Show a cost-per-QA-run tile. | 2 |
| Aug 28 | **Cloudflare Web Bot Auth: signed, verified bot traffic** | "Our agent identifies itself honestly to gov/pharma sites." That's an ethics line for the recall and rumor checks. | 3 |
| Sep 8 | "Keyless Entry", the front door for agents (identities/auth) | Roadmap: the caregiver links a pharmacy portal through Identity/OmniConnect (Apr 2026). Do **not** build it. | 2 |
| Aug 24 | Integration with **AgentCore Payments** | Not relevant. | 1 |
| (docs) | Webhooks (`task.completed`, `session.recording.ready`, Slack-shaped receivers) | Feed QA results into the SurrealDB event table, so phones show the "QA passed" badge live. | 4 |

### SurrealDB
| Date | Feature | Village use | Fit |
|---|---|---|---|
| **Oct 14** | **"Introducing SurrealDB Agent Memory"** launch post: entities/attributes/relations/**instructions/uncertainties**, structured provenance, **tri-temporal** ("what did we believe last month?"), hybrid vector+FTS+graph retrieval, hierarchical scopes, MCP, Studio | Launched two days ago, so it's the freshest feature of any sponsor. The "what did Mom know when" timeline and uncertainty resolution are textbook uses. | **5** |
| Oct 14 | Agent memory benchmarks (BEAM 1M: 77.2% mean; weakest is event ordering at 49.7%) | Be honest with Martin: we pin ordering with our own `observed_at` and don't rely on inference. | 3 |
| docs | `/reflect` (on-demand reflection), MCP tools `remember/recall/context/reflect/forget/upload/inspect` | Reflection over a week of facts proposes UI evolution (idea #5). `forget` gives the family a "right to be forgotten" button. | **5** |
| Sep 24 | **SurrealDB 3.3**: Postgres wire protocol, better graph traversal + filtered vector search (bitmap indexes) | Filtered vector search fits blackout need/resource matching ("insulin fridge" within Block 14). | 3 |
| Oct 12 / 13 | SurrealMX in-memory engine; SurrealKV 1.0 replaces RocksDB | Fallback `surreal start memory` story only. | 1 |
| Sep 3 | Mastra integration | Not our stack. | 1 |

### AWS (Bedrock + AgentCore release notes)
| Date | Feature | Village use | Fit |
|---|---|---|---|
| Sep 22 | **Claude Opus 5.5 on Bedrock** (1M ctx, 128k out, adaptive thinking, cheaper cache reads, ZDR by default) | Builder agent on Bedrock Opus 5.5. "Health data, zero data retention" is the AWS SA line. | **5** |
| Sep | **AgentCore Harness lifecycle hooks**: `before_tool_call` → Lambda returns allow/deny | Run the builder/escalation agent on Harness, with the deterministic dose gate as a `before_tool_call` Lambda. That's "policy outside the model". | 4 |
| Jul | **Policy + Bedrock Guardrails**; Harness GA; **Batch Evaluations, A/B Testing, Recommendations GA**; **Failure Insights** preview | Guardrails on generated UI copy (no medical advice). Recommendations overlaps Arize Signal, so pick Arize for the loop. | 3 |
| Aug | Memory: **JSON payload events**, IngestData, flexible namespaces; **Skill evaluators** | Overlaps SurrealDB. Avoid split-brain memory. | 1 |
| Oct | Memory record **TTL** | Overlaps SurrealDB. Skip. | 1 |
| Sep | **Consent Portal** (AgentCore Identity) | A conceptual match for the consented-voice ritual, but heavy (Gateway + JWT IdP). Mention it only. | 2 |
| May (pre-window) | Evaluations **user simulation** | Alternative to ElevenLabs simulations. Don't do both. | 2 |

---

## 2. Ten cross-sponsor ideas

**1. The Gauntlet: 20 simulated Moms → Arize experiment.** *User sees:* a grid of 20 persona cards ("forgets she already took it", "code-switches ES/EN", "hard of hearing, repeats", "scammer pretending to be Dana asking to change the dose", "reports chest pain"), each turning green or red, then an Arize experiment link with pass rates. *Features:* ElevenLabs simulation tests (`repeat_count`, tool mocks forcing BLOCK, success-conditions array) → results posted as a space-scoped Arize experiment → Session Frustration + Goal Completion templates + an agent-as-judge "gate decision matches facts". *Effort:* M. *Wow:* high (adversarial safety, quantified). *Risk:* sim runtime of ~30–60 s per test. Pre-run tonight and re-run 3 live.

**2. Signal → merge proposal self-improvement loop.** *User sees:* "Arize found an issue: 18% of Spanish callers saying 'la pastilla de la presión' weren't mapped to lisinopril. Proposed fix ↗. Approve?" → tap → ElevenLabs merge proposal is created → Gauntlet re-runs → pass rate goes 82% → 100%. *Features:* Arize Signal (or Alyx over traces if Signal hasn't fired) + Prompt Hub label webhook (Oct 7) + ElevenLabs branches/merge proposals (Oct 5) + idea #1. *Effort:* M–L. *Wow:* very high for Fuad. *Risk:* Signal's 3 h minimum cadence. Seed traces tonight; keep an Alyx/manual fallback.

**3. "What did Mom know, and when?" timeline.** *User sees:* a scrubber over the last week. At any instant it shows what Village *believed* (dose 5mg → 10mg), what the Mom-line agent *was told* on that call, the audio clip, and the trace. Selling line: "the 9:40 call said 5mg because the 10mg fact arrived at 10:05". *Features:* Agent Memory tri-temporal `asOf` + provenance + `/history`; Arize audio-in-traces (Aug 12) deep link; ElevenLabs post-call audio. *Effort:* M. *Wow:* high (Martin, Fuad). *Risk:* low. The data you write anyway.

**4. Elder-accessibility vision judge (release gate).** *User sees:* every generated role app gets a scorecard (tap target ≥ 48px, contrast, font ≥ 20px, one primary action) before its QR goes live. A failing component is visibly bounced back to Claude and regenerated. *Features:* Anchor phone-viewport screenshots + recording → Arize **image LLM-as-judge** (Aug 12) + deterministic axe-core check in the Daytona sandbox. *Effort:* S. *Wow:* medium-high, and it's an "AI judging AI UI" story. *Risk:* low.

**5. UI that evolves from memory, tested in a fork.** *User sees:* a card saying "Mom mentioned dizziness after her evening dose 3 times this week. Add a Symptom log to Dana's view?" Approve → a **Daytona fork** builds it, Anchor's self-healing QA task runs on the fork, and the phones hot-swap to the promoted fork. *Features:* Agent Memory `/reflect` → Claude spec patch → Daytona fork (stable Jul 29) + WebSocket events → Anchor task (`task.healed`) → SurrealDB live query pushes the new spec. *Effort:* M (L if forking misbehaves). *Wow:* very high, since it's the "software made for one group" thesis. *Risk:* fork timing on stage. Pre-warm a fork tonight.

**6. Recall Watch for Mom's meds.** *User sees:* "⚠ FDA Class II recall: Lisinopril 10mg, lot 241103 (metal fragment). Is Mom's bottle affected?" plus an uncertainty card. Dana photographs the label and the card resolves to "not affected" with provenance. *Features:* openFDA `drug/enforcement` JSON (call it directly, it's free) + Anchor for the human-readable press release and the DailyMed label page with Web Bot Auth + SurrealDB uncertainty → resolve + escalation call if affected. *Effort:* S–M. *Wow:* medium-high, and it's real: the lisinopril 10mg recall (Nov 2024, terminated Apr 2026) is replayable. *Risk:* Anchor's role is thin when JSON exists. Frame it as "Anchor reads what APIs don't".

**7. Evening Family Brief (voice digest).** *User sees/hears:* at 8pm each sibling gets a 45-second v4 audio brief: "Mom took both doses. She sounded tired at 6 [audio clip]. One open question: Dr. Patel's new dose isn't confirmed. Carlos is on duty tomorrow." *Features:* SurrealDB diff since the last brief (`observed_at` window) + Claude summary + **v4** TTS with audio tags (or Text to Dialogue quoting Mom) + Arize faithfulness eval (every claim must map to a fact id, scored by agent-as-judge). *Effort:* S. *Wow:* medium-high, emotionally strong. *Risk:* low.

**8. Consented family voice (Dana's voice reminders).** Described and evaluated below. *Effort:* S technically, M with the consent ritual. *Wow:* very high. *Risk:* ethics/optics.

**9. Rumor → correction callback (blackout).** *User sees:* "Rumor: 'tap water unsafe on Block 14' → checked against NYC EM + DEP → **debunked** (source, quote, screenshot)". Neighbors who *heard* it (tracked by provenance) get a batch call in their own language. *Features:* Anchor agent.task with `output_schema` → SurrealDB rumor entity + `heard_from` relations (graph) → ElevenLabs batch calling with es/zh dynamic vars + AMD. *Effort:* M. *Wow:* high, and it's the second demo's centerpiece. *Risk:* official pages vary, so pre-cache.

**10. Gate as an AgentCore Harness hook.** *User sees:* the trace shows `before_tool_call → Lambda: DENY (dose 2 of 1 within 20h)` on the builder/escalation agent, with Guardrails blocking generated medical advice copy. *Features:* AgentCore Harness lifecycle hooks (Sep) + Policy/Guardrails (Jul) + Bedrock Opus 5.5. *Effort:* M–L (new infra). *Wow:* high for the AWS SAs. *Risk:* high. It's new infra and duplicates the Core gate. Build it only if AWS Best Use is a priority.

### The consented family voice, evaluated
**Evidence.** It's thin but supportive. Valdivia & Li (17 caregiver–care-recipient dyads, 15 clinicians) found dyads *prefer familiar voices for routine reminders like medication*, while clinicians were mixed. Wolters et al. (JAMIA 2015, n=44, ages 50–80) found reminder recall was fine *regardless of voice* when the reminder named one familiar medication, and repetition helped with multiple meds. So the voice itself isn't the mechanism; short, familiar content is. Commercial recorded-voice reminders (Reminder Rosie pilot: 86% of poor adherers reached ≥80%) are uncontrolled. The dementia literature claims voice recognition outlasts face recognition, but the sources are mostly grey literature. Honest pitch: "preferred by families, plausible for comfort, unproven for adherence. We'd measure it with Arize A/B."

**Risks.** (a) Scam mimicry: AI-voice "family emergency" scams target over-60s, and the FBI cites roughly $38.5k average losses for 60+ victims in 2025. Training Mom to trust "Dana's voice from a machine" could prime her for exactly that scam. (b) Deception and confusion in cognitive decline: she may believe Dana is literally calling. (c) Consent decay: Dana leaves the family rota, or Mom's capacity changes.

**Mitigations (make these visible in the demo).**
- **Consent ritual on stage.** Dana records the clip in-app and reads a consent sentence aloud. The voice is stored as a SurrealDB fact with provenance (`consented_by`, `scope: reminders_only`, `expires`). Revoke is one tap and deletes the ElevenLabs voice.
- **Disclosure every time.** "This is Village, using Dana's voice." The clone never says "I am Dana".
- **Content allowlist.** The cloned voice only speaks templated reminder strings (deterministic `say`), never LLM free text, never money, never "change your dose", never asks for information.
- **Family passphrase.** Mom is taught "Village never asks for money. Real Dana knows our word." Village reinforces the anti-scam message monthly.
- **Outbound-only from the known Village number.** Inbound conversations stay in the neutral Village voice.
- **Mom's consent as well.** Captured on a call, revocable by voice ("use the normal voice").
Verdict: worth showing as a **consent-first** feature (≈20 s of the demo). Skip it if the consent UI can't be built cleanly; a half-done clone looks worse than none.

---

## 3. Top 5 (judge impact × feasibility)

| Rank | Idea | Why | Strengthens |
|---|---|---|---|
| 1 | **#1 Gauntlet** (20 simulated Moms → Arize experiment) | Uses the newest testing features on both sides. It quantifies safety and is mostly prep work you can pre-run tonight. | **Arize** + **ElevenLabs** |
| 2 | **#5 Memory-driven UI evolution in a Daytona fork** | It's the product thesis in one moment, and it touches 4 sponsors with each one doing real work. | **Daytona** (fork), **SurrealDB** (reflect), **Anchor** (self-healing QA) |
| 3 | **#3 "What did Mom know when"** | Agent Memory launched Oct 14, and this is its signature capability. It costs little because the data is already written. | **SurrealDB**, **Arize** (audio traces) |
| 4 | **#4 Elder-accessibility vision judge** | Small effort, and it gives Anchor and Arize a visible quality gate. | **Anchor** + **Arize** |
| 5 | **#7 Evening Family Brief on v4** (+ optional consented-voice reminder, #8) | An emotional close that shows v4, with faithfulness scored in Arize. | **ElevenLabs**, **Arize** |

**Runners-up:** #2 Signal loop (the highest Arize ceiling, but cadence risk, so treat it as stretch layered on #1), #6 Recall Watch, and #9 (mandatory if the blackout demo runs). Only build #10 if you're chasing AWS Best Use; otherwise, for AWS, run the builder on **Bedrock Opus 5.5 with ZDR** and name it.

---

## Sources
- Daytona changelog: https://www.daytona.io/changelog
- Arize AX release notes: https://arize.com/docs/ax/release-notes · Signal: https://arize.com/docs/ax/observe/signal.md
- ElevenLabs changelog: https://elevenlabs.io/docs/changelog · Safety: https://elevenlabs.io/safety
- Anchor: https://anchorbrowser.io/blog · https://anchorbrowser.io/blog/anchor-cloudflare-verified-browser-agents · https://docs.anchorbrowser.io/advanced/cloudflare-web-bot-auth · local `docs/anchor-llms-full.txt` (self-healing, pricing Aug 21)
- SurrealDB: https://surrealdb.com/blog · https://surrealdb.com/blog/introducing-surrealdb-agent-memory · https://surrealdb.com/releases
- AWS: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html · https://aws.amazon.com/blogs/machine-learning/claude-opus-5-5-is-now-available-on-aws/
- Voice familiarity: Valdivia & Li, https://rshare.library.torontomu.ca/articles/thesis/Voice_familiarity_in_an_interactive_voice-reminders_app_for_elderly_care_recipients_and_their_family_caregivers/24488803 · Wolters et al. 2015 JAMIA, https://researchonline.gcu.ac.uk/en/publications/can-older-people-remember-medication-reminders-presented-using-sy/ · Reminder Rosie pilot (via McKnight's) https://www.mcknights.com/?p=63925
- Scam risk: https://www.foxnews.com/tech/grandparents-identity-thefts-biggest-payday · https://guard.io/blog/grandparent-scam-ai-voice-cloning-protect-family
- Lisinopril recall: https://www.hmpgloballearningnetwork.com/site/pln/news/metal-fragment-tablet-prompts-recall · https://ndclist.com/ndc/68645-612/recalls
