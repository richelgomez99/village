# RECONCILE.md: contract/data gaps reported by the spec agents (to apply before 10:00)
Collected from specs/00N research/contracts READMEs. Orchestrator applies these, bumps `contracts/VERSION` to 1.1.0, re-runs `contracts/validate.py`, and pushes.

## Already fixed (Oct 16 ~2:50am)
- Rota on demo day: Marco on duty Fri Oct 16 (data, seed events, ws fixture, policy T10 + shared state) ✔
- `ws_sequence_scam.json` Marco snapshot text now matches `is_my_turn: true` ✔
- Rule-id alias table added to `policy_cases.md` (R-* ↔ P-*) ✔

## Applied in contracts 1.1.0 (validated, pushed)
- FS-1: `verification_pending.channels` must allow `[]` for `unreachable` (no consent → app prompt only may also be empty if no app session); gate `Decision.escalate` must not require an event id the pure gate can't know (`related_event_id` → optional, filled by Core)
- FS-2: add `say` key `money_core_down` (fixed script when Core is unreachable); add `GET /voice/token` (conversation token for the web setup agent); add event kind `call_failed`
- FS-3: `village.status: draft|active`; endpoints `POST /villages/{id}/activate`, `/ask`, `/answers`, `/draft` (PATCH ops), `/messages` (+GET); `decision.schema.json` + `GET /villages/{id}/decisions`; event kinds `village_activated`, `invite_redeemed`; `invite_id/token` defs; `VillageChat` component props + `chat:village` data bind; WS `chat` message; optional `control{kind: blueprint}`; 409 on QR/activate while draft
- D16: `message.schema.json` (author member|village|system; kind chat|incident|proposal|receipt|nudge|answer; refs[]); WS `chat` frame
- (pending) FS-4/7 and FS-5/6 reports
