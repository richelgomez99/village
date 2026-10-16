# The block village: same platform, a different group (Oct 16 2026, lane/block)

West 147th Block — Heat & Blackout (`v_w147`) is the second village Village built. It proves the platform claim in D30: the same intake → spec → catalog render → gate → release → live-patch pipeline, with no Reyes and no West 147th in `core/`, produces a different piece of software for a different group. The family is four people carrying one person's week; the block is eight neighbors and a corner deli carrying an afternoon with no power at 97 °F.

## For what → feature → number

| For what | Feature | Measured |
|---|---|---|
| A different group, same code | Both villages load from `data/villages/index.json` (spec, data, events, messages); `grep -rn -e w147 -e reyes core/ \| grep -v /tests/` | 25 hits before and after this lane (all in `core/watcher/fixtures` and `core/voice/*` recordings), 0 added |
| Different jobs → different apps | 3 views (coordinator, volunteer, resident) + the block line for 3 phone-only neighbors; tabs derive from the block's own 4 life areas | Coordinator tabs: Home · Health · Rumors · Cooling · Stairs · Chat; volunteer: Home · Health · Cooling · Stairs · Chat; resident: Home · Rumors · Cooling · Stairs · Chat |
| A village that already lived an afternoon | Seeded ledger + chat at Reyes quality: oxygen need matched to a generator by medical priority, an ice run, two rumor checks against the named official source, a pending ask, the real release receipt | 9 ledger events, 16 chat rows (8 by Village as a participant, 4 labeled demo actors, 1 pending ask), 6 Agent Memory facts derived from them (2 consents × 2 scopes, the shift, the published rev) |
| Different hard rules | 911 first, medical-priority matching (P-MP-01: oxygen > insulin > infant > mobility), rumors never repeated as fact (P-RU-01..04), no apartment numbers beyond the matched volunteer (P-PR-01/02) | 12 policy rows in `block_spec.json`; the chat's rumor answers cite "NYC DEP — Drinking Water, checked 12:36" and "NYC Cooling Center Finder, checked 1:41" |
| The receipt is real | `rel_w147_r2` in the seed is the block release measured in RESULTS.md | released in 13 409 ms, 33 floor tests passing |
| Who's on this shift | PlanBoard `plan:shift_today` from the village data (core fallback in `bindings_v3.plan`, village-agnostic) | 6 items: 2 done (generator, ice), 4 open |
| Contracts hold for every village | `contracts/validate.py` now checks every `events_*_seed.json` / `messages_*_seed.json` | 9 fixtures validated, 0 errors; `uv run pytest -q`: 408 passed |

## What makes the block different from the family (one paragraph for the pitch)

The Reyes village is about one person: its life areas are pills, money and people, its hard rule is "no money in a family member's name without that person's yes", and its receipts are about Carmen's phone. The block village is about a place and an afternoon: its life areas are power-dependent health, rumors, cooling and stairs; its rules are 911 first, oxygen before insulin before the newborn before the wheelchair, no rumor repeated until the named official source is read, and no apartment number beyond the matched volunteer. Village reads those from the spec and the data file, not from code: the coordinator gets a needs board, a shift plan and a rumor check; a volunteer gets who-needs-help-first and the same plan; a resident with an app gets "Are you OK?" and checked facts; a resident with a landline gets the block line in Spanish. Same chat, same Village voice, different village.

## Honest notes

- Check-ins: the seed marks Mrs. Alvarez (1:02, by phone) and Mr. Chen (1:25, in app) as checked after their needs were met; their needs stay "Urgent · open" on the board because priority ≤ 2 never auto-closes on a check-in.
- The event schema has no rumor incident type; rumor checks live in the chat (`answer` rows with the official source and time) and in the data file's rumor rows (`finding`, `checked_at`), not as invented ledger events.
- The volunteer "Is it my shift?" headline was cut: `HelperAnswer`/`rota_me` are worded for nights ("Tonight until 9:30 · Swap my night"); a block needs shift wording. The shift itself is seeded (`ev_1016_1226_shift_1016`: Darnell on, Priya backup) and is a memory fact.
- Kit vitest in a fresh `npm ci` worktree fails 20/137 with a duplicate-React `useMemo` error before and after this lane's changes; `npm run build` passes. Treat the kit test result as environment, not regression, until verified in the main checkout.

## BLOCK-VOICE: Village calls the places on the official list (fixture mode shipped; live path specified, not built)

The user's ask: "Village can spin off some phone calls to whatever institutions are needed to confirm whether they can take us in, whether they have power… and log it into our system."

What landed (commit 66196e8, `core/voice/institution_calls.py`, village-agnostic):
- **Trigger**: a coordinator message in the block chat that names a place (cooling center, hospital, shelter, library) and asks about power / open / taking people → new chat intent `call_out` (only when the village data has `institutions`); Village answers as a participant: "I'll call the places on the block's official list now: … One line per place as they answer." Also `POST /villages/{id}/calls/institutions` (control or coordinator token).
- **Places** (`institutions` in `data/villages/block_blackout.json`, real public names and URLs only, no phone numbers, no capacity numbers): NYC Cooling Center Finder (nearest listed site), Harlem Hospital Center, Hamilton Grange Library (NYPL).
- **Result → memory → apps**: per place three facts (`has_power`, `open_until`, `takes_oxygen`) with source `{kind: call, ref: demo:<id>}` and `demo=true` labels, visible in `GET /villages/{id}/facts` (Control Room "What Village knows"), plus one `[demo]`-tagged chat line per place: "Harlem Hospital Center: power yes · open until 24 hours · takes oxygen: yes (called 2:36 PM) · demo". Idempotent on (village, institution, run id).
- **Measured**: fixture run for 3 places 2.26 s wall; a second POST with the same run id added 0 rows; 411 tests pass (408 + 3 new).
- **Not live**: no outbound call was placed. The frozen ElevenLabs Caller agent only carries the verification script; the live branch (`DEMO_INSTITUTION_NUMBER` + dialer live mode, with the unanswered-call timeout → "No answer at <Place> (2:43 PM). I'll try again in 20 minutes.") needs the prompt change below, which is for the orchestrator to approve; nothing was pushed to any agent.
- **Proposed Caller prompt addition** (dynamic variables `purpose`, `place_name`, `questions`, `language` via conversation_initiation_client_data): "If `{{purpose}}` is `institution_check`: you are Village, calling `{{place_name}}` for a neighborhood group during a power outage. Say so in one sentence, then ask, one at a time: `{{questions}}`. Reply in `{{language}}`. Record each answer as yes, no or unknown, plus a closing time if given. Don't share residents' names or medical details. Don't promise anything. Thank them and hang up. Call `report_institution_status` with {village_id, place_name, has_power, open_until, takes_oxygen}." The tool would hit a webhook that calls the same results code as the fixture path.
- **"Nearest hospitals and routes"**: answered from data only (names + official URLs above); no addresses were added because none could be confirmed in time, so no maps link and no travel times. Nothing is presented as live-verified.
