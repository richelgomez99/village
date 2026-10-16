# Checkpoints (orchestrator fills one block at each time)

Rules: write what was seen on real phones, not what a test says. Every number is copied from `RESULTS.md` / `LANE-REPORT.md` or written `[MEASURE: what]`. A cut is a decision: give it a D-number in `DECISIONS.md` if it changes the pitch.

Run before filling: `scripts/acceptance_summary.sh` (checks + tags) and `scripts/reset_demo.sh` (proves the reset still works).

## 11:00 · V0 cutoff (slipped to ~11:15 per D25)
### 11:00 → written 11:30 (V0-green tagged 10:50)
- **Works on real phones:** `https://richel-macbook.tail8feae0.ts.net/` serves the kit via Tailscale Funnel (verified from Anchor's browser and the operator's phone). Core (port 8790) → SurrealDB Cloud → every connected phone in ~100 ms on `POST /tools/log_dose`. Three role views render from the Reyes rev 5 fixture. 158 tests green offline (core 16+, gate 110, voice 31). Mom line "Luz · Línea de Mamá" deployed on +1 848 257 9221 with tools pointed at the Funnel; outbound call to the operator's phone PASSED. Agent Memory supersession PASSED (p50 query ~3.8 s). Arize exporter PASSED.
- **Mocked / not yet:** verification loop end to end (core V1 in progress), founding (builder V2), Control Room regions (kit V2), release receipts (V3), rounds + proposals (V4), scam number (evals running).
- **Risks:** OpenAI rate limit cuts Codex turns; Bedrock lab account only has Haiku 4.5 (Anthropic key needs a workspace); tool endpoints accept calls without a shared secret today; Daytona snapshots denied (image sandbox fallback 16 s).
- **Cuts so far:** none of the version scope; `/s/{token}` scan page (D22) and lid stickers were already out.

Target: V0 tag: gate tests model-off, spine to 3 phones, refill card 5→10 mg

| | |
|---|---|
| Filled at | |
| Acceptance (`scripts/acceptance_summary.sh`) | V0 _ · V1 _ · V2 _ · V3 _ · V4 _ |
| Tags present | |
| Version we would pitch right now | |

**Works on real phones** (who held which phone, what they saw):
- 

**Mocked or faked** (what, and how the pitch words it honestly):
- 

**Measured since last checkpoint** (copy into `RESULTS.md` first):
- 

**Risks** (what breaks the next version, and the fallback):
- 

**Cuts** (what's dropped, LAYERS.md cut order, D-number):
- 

**Devpost section current:** V_ · `[MEASURE]` left: _ · `[PENDING]` left: _

---

## 12:15 · V1 cutoff

Target: V1 tag: real call → verification → Marco prompt + call → spoken outcome; timeout safe default; record the 30 s clip now

Filled by the pitch lane at 11:59 from `RESULTS.md`, `LANE-REPORT.md` and `scripts/acceptance_summary.sh` (run with SurrealDB URL empty, model off). The orchestrator corrects "works on real phones" from what was actually held.

| | |
|---|---|
| Filled at | 11:59 (pitch lane, from documents; orchestrator to confirm) |
| Acceptance (`scripts/acceptance_summary.sh`) | V0 PASS · V1 PASS · V2 absent · V3 absent · V4 absent |
| Tags present | V0-green (10:50), V1-green (11:49); lane tags gate-v0, spine-v0, voice-v1, kit-v0, kit-v2, release-v3, memory-v4, evals-v4, core-v2 |
| Version we would pitch right now | V1 (V0 page if the real call isn't confirmed on phones) |

**Works on real phones** (who held which phone, what they saw):
- Carmen's view opens on the operator's phone through the public Funnel URL; `/health` answers from Anchor's browser outside the Mac (RESULTS "Public URL").
- **First live call, 12:23** (orchestrator): a real call to Carmen's line (+1 848 257 9221). Init webhook 200 → `report_money_request` → verification opened → `await_verification` → **denied** by Marco's tap on his phone → the refusal spoken word for word. The Watcher proposed the receptionist 7 s later.
  - Gap found: the agent called `ask_family` (Carmen asked for Marco to call tonight) and Core returned 404, so nobody got the message. Fixed since (D31 rule 4: every tool the agent can call has a Core handler).
  - Also from the call (D31): usted throughout, AI disclosure first, and the ElevenLabs prompt guardrail must never block Village's own "No mande dinero" lines.

**Mocked or faked** (what, and how the pitch words it honestly):
- Outbound call to Marco: fake dialer; Twilio geo permissions block live calls. Pitch: "Marco's phone gets the check in the app; the call is the second channel."
- ElevenLabs agent, tool and procedure pushes: dry-run. TTS is live.
- Founding intake (D29): not in main; Control Room has a recorded founding sequence offline.
- Anchor: static view checks only (no scam/scan taps); reached the build via Daytona's signed preview, not Core's URL.
- Rounds: seeded data.

**Measured since last checkpoint** (copy into `RESULTS.md` first):
- Scam eval set: 30/30 caught, 0/20 false alarms (model on, Bedrock Haiku 4.5); 28/30, 0/20 rules only; Arize experiment `scam-model-20261016T153959Z`.
- Release: Reyes warm 14957 ms, warm with caught failure 19908 ms, cold with caught failure 29731 ms; West 147th 13409 ms, 33 floor tests.
- Caught-and-fixed build: contrast 4.1:1 → #4C80B4 to #2D5A8C → released.
- Agent Memory: write p50 630 ms, history p50 248 ms, recall 3.7 s.
- Nightly round: 3 alone · 1 asked · 1 refused ("Blocked by code: Carmen's rule, no calls after 9:30 PM").
- Tests: 245 Python (110 gate), 57 kit.

**Risks** (what breaks the next version, and the fallback):
- Live outbound call (Twilio geo permissions). Fallback: in-app prompt is primary (ARCHITECTURE-VALIDATION §4).
- Anthropic API key 400 without workspace id. Fallback: Bedrock Haiku 4.5 (all measured runs used it).
- Founding intake not merged; V2 cutoff at 13:00. Fallback: recorded replay (D29 `--replay`) on the Control Room.
- Release router not mounted on the live Core at the release run; Anchor via tunnel not exercised end to end.
- Platform sweep (D30): Reyes-specific strings in core/kit outside `data/` still being removed.

**Cuts** (what's dropped, LAYERS.md cut order, D-number):
- Daytona snapshot (denied): one warm sandbox from the default image instead (release T003).
- `acceptance/v3.sh` not written; release smoke output is the evidence (release T024).

**Devpost section current:** V0 ready; V1 pending phone confirmation · `[MEASURE]` left: 6 (report→prompt, intake time, Reyes floor count, live rebuild, cost, phones joined) · `[PENDING]` left: draft URL, V1 clip, platform sweep, V1–V4 confirmations, receptionist GIF

---

## 13:00 · V2 cutoff

Target: V2 tag: conversation → three apps → QR join; Ask Village why

| | |
|---|---|
| Filled at | |
| Acceptance (`scripts/acceptance_summary.sh`) | V0 _ · V1 _ · V2 _ · V3 _ · V4 _ |
| Tags present | |
| Version we would pitch right now | |

**Works on real phones** (who held which phone, what they saw):
- 

**Mocked or faked** (what, and how the pitch words it honestly):
- 

**Measured since last checkpoint** (copy into `RESULTS.md` first):
- 

**Risks** (what breaks the next version, and the fallback):
- 

**Cuts** (what's dropped, LAYERS.md cut order, D-number):
- 

**Devpost section current:** V_ · `[MEASURE]` left: _ · `[PENDING]` left: _

---

## 13:40 · V3 cutoff

Target: V3 tag: Daytona build+tests, Anchor run, Arize evals, caught failure, blackout block; record the draft video now

| | |
|---|---|
| Filled at | |
| Acceptance (`scripts/acceptance_summary.sh`) | V0 _ · V1 _ · V2 _ · V3 _ · V4 _ |
| Tags present | |
| Version we would pitch right now | |

**Works on real phones** (who held which phone, what they saw):
- 

**Mocked or faked** (what, and how the pitch words it honestly):
- 

**Measured since last checkpoint** (copy into `RESULTS.md` first):
- 

**Risks** (what breaks the next version, and the fallback):
- 

**Cuts** (what's dropped, LAYERS.md cut order, D-number):
- 

**Devpost section current:** V_ · `[MEASURE]` left: _ · `[PENDING]` left: _

---

## 14:15 · V4 cutoff

Target: V4 tag: rounds counts, rebuild to every phone, receptionist live, scam eval number

| | |
|---|---|
| Filled at | |
| Acceptance (`scripts/acceptance_summary.sh`) | V0 _ · V1 _ · V2 _ · V3 _ · V4 _ |
| Tags present | |
| Version we would pitch right now | |

**Works on real phones** (who held which phone, what they saw):
- 

**Mocked or faked** (what, and how the pitch words it honestly):
- 

**Measured since last checkpoint** (copy into `RESULTS.md` first):
- 

**Risks** (what breaks the next version, and the fallback):
- 

**Cuts** (what's dropped, LAYERS.md cut order, D-number):
- 

**Devpost section current:** V_ · `[MEASURE]` left: _ · `[PENDING]` left: _

---

## 14:20 · Freeze

Target: Nothing new merges. Pick the version we pitch. Final video 14:20–14:50; submit by 15:10

| | |
|---|---|
| Filled at | |
| Acceptance (`scripts/acceptance_summary.sh`) | V0 _ · V1 _ · V2 _ · V3 _ · V4 _ |
| Tags present | |
| Version we would pitch right now | |

**Works on real phones** (who held which phone, what they saw):
- 

**Mocked or faked** (what, and how the pitch words it honestly):
- 

**Measured since last checkpoint** (copy into `RESULTS.md` first):
- 

**Risks** (what breaks the next version, and the fallback):
- 

**Cuts** (what's dropped, LAYERS.md cut order, D-number):
- 

**Devpost section current:** V_ · `[MEASURE]` left: _ · `[PENDING]` left: _

---
