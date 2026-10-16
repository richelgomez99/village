# Demo notes: full site walkthrough (orchestrator, 12:50) and the beats for stage + video

Walked at 1920×1080 (Control Room) and 390×844 (phones) against the live Core on 8790. The platform is the project; Reyes and West 147th are the two stories we tell it through (D30). Each beat below names the **tech that solves it**, which is what judges score.

## What I saw, screen by screen

| Screen | Good | Fix (owner) |
|---|---|---|
| Carmen's phone | Exactly D22: identity chip, "Esta noche cuida Marco", three big buttons, 911, read aloud; Spanish only; real `tel:` links | none |
| Marco's phone | "Is it my turn? Yes. Tonight until 9:30." + refill checklist with the struck-through 5 mg and its source; Call Mamá | chat shows the raw id `m_marco` instead of "Marco"; the proposal message in chat is a wall of text (kit); seed line said "scanned her morning lid" (fixed: D22) |
| Ana's phone | Proposal card with Approve; refill card; rota; timeline with sources; chat with Approve | rule ids (P-MA-01, R-MONEY-VERIFY…) on a family phone → plain words, ids only on the Control Room (kit); "1/2 lids today" → pills wording (kit); proposal chat text ≤ 2 lines (kit) |
| Control Room, founding | (before V2e) a static dashboard, everything stamped 13:58, meter 10/10 mid-way | rebuilt as a paced scene (V2e merged): transcript → heard/knows/doing/will-build → village + phone mirrors growing card by card. Verify live after merge |
| Control Room, scam | ring, captions, phones | ok |
| Village switch | pills per village, regions clear | ok after V2b |
| Join page | member pick + consent | ok |

## The stage run (3:00), platform first, two stories as evidence

Props: your phone (Carmen, later the scammer), the judge's phone (Marco), the projector on `control.html` (live), a second tab with the fake sequences as fallback. No printed props.

| t | Beat | You do | Screen | Tech that makes it work (say it in one clause) |
|---|---|---|---|---|
| 0:00 | Open | PITCH.md open, verbatim; no names | Control Room, "Village", empty state "No village yet. Describe your people." | the platform face: one site, any village |
| 0:30 | Build | Resume the Reyes intake at 8/10; read A10, A11, A12 as Ana | left transcript fills; middle "heard → knows → doing → will build"; right: meter 8→10, cards; phone mirrors gain cards | Sonnet 5.5 extracts per answer; DailyMed checked; consent call placed; catalog-only render; rules as spec params |
| 1:10 | Run | Judge opens Marco's link; you call the line as Carmen (English); judge taps "That wasn't me" | Live panel, captions es/en, Marco's phone mirrored, gate decision row | ElevenLabs tools → pure gate → SurrealDB LIVE → every phone; safe default on timeout |
| 1:55 | Rebuild | Ana (your laptop) taps Approve | proposal → six-stage receipt (build, floor tests, phone-size QA, evals) → toast on every phone | the Watcher weighed 3 options; Daytona build + generated floor tests; Anchor at 390×844; Arize evals; blue/green rev |
| 2:25 | Receptionist | You call again as the scammer | Luz screens, verifies with Marco, refuses; captions | `screen_caller` → gate → verification with the real person |
| 2:40 | Anyone | Click the West 147th pill | the room refills: Tanya's board, Darnell's card, the deli line | same code; D30 grep is empty; built in 13.4 s |
| 2:50 | Under the hood | numbers once | What Village knows (fact history, as-of), decisions log with modes | SurrealDB Agent Memory, Arize experiment 30/30 · 0/20, tests model-off |
| 3:00 | Close | "It takes a village. Village builds it." | | |

Rehearse twice with a stopwatch after the freeze. Reset between runs with `scripts/reset_demo.sh` (it must also clear proposals; D34).

## The video (≤ 2 min, Devpost round one), recorded this afternoon
Shot list = the same beats, but Build uses the **block** founding with the recorded call audio (`?fake=control&seq=founding&village=v_w147&audio=1`, 73 s, cut to ~35 s) so the video shows "a leader on a call → the page changes" and the stage shows "Ana typing". Then Run/Rebuild/Receptionist from the live Reyes run (screen-record the projector + phone), then the switch to Reyes/West 147th, then the numbers card. Voice-over = the open + one line per beat. Hero GIF = the receptionist refusing the scammer with captions.

## Open fixes before freeze (in order)
1. Verify the paced founding scene live and with `?resume=8` (orchestrator). 2. Phone copy: names not ids in chat, no rule ids on family phones, short proposal message (kit). 3. `reset_demo.sh` clears proposals and re-seeds both villages (pitch/core). 4. Approve → patch on three real phones (operator test). 5. Receptionist live call (operator test).
