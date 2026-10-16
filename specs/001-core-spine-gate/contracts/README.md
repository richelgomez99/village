# FS-1 contracts

FS-1 adds no schemas to `/contracts` (1.0.0). It builds against `common`, `event`, `gate`, `verification`, `lid_scan`, `ws_messages`, `voice_tools` (`common_fields.tool_call_id`, `verification_answer_request`, `data_report_money_request`, `data_await_verification`) and `openapi.yaml` paths `/health`, `/s/{slot_token}`, `/v/{id}/actions/{name}`, `/verifications/{vid}/answer`, `/clock/warp`, `/ws`. Oracles: `reyes_spec`, `events_reyes_seed`, `lid_scan_sequence`, `ws_sequence_scam`, `scam_call_tool_requests`. Contract questions: `../research.md` Q5–Q12.

## Requested contract bump (D16, orchestrator only)
`ws_messages`: server message `chat{type: "chat", message}`. New `message.schema.json`: `{id: msg_*, village, author: member_id | "village" | "system", kind: chat|incident|proposal|receipt|nudge|answer, text ≤ 2000, refs: [event_id | fact key | trace_id | proposal_id], source, at}`. `openapi.yaml`: `POST /villages/{id}/messages {text}` (member token) → `message`; `GET /villages/{id}/messages?after=` (member/control). Until bumped, Core uses a pydantic mirror of this shape and the hub sends `chat` only when `VILLAGE_LAYERS >= 2`.

## `core/services.py` (the seam)
```python
async def now() -> datetime
async def decide(village_id, candidate: Candidate, *, idempotency_key=None, actor_token=None) -> tuple[Decision, list[Event]]
    # load VillageState → mint alloc → core.gate.decide → persist decision → execute writes[] → notify/escalate → return
async def record_event(village_id, draft: EventDraft, *, actor, source, decision_id=None) -> Event   # ungated ledger write
async def start_verification(village_id, candidate, *, idempotency_key) -> StartResult
    # {decision, verification_id|None, status: pending|unverifiable|denied_request, channels, deadline, incident_id|None}
async def answer_verification(verification_id, answer: "yes|no|unsure", *, via, member_id, quote=None, call_sid=None) -> Verification
async def await_verification(verification_id, *, max_wait_s=30) -> AwaitResult
    # {decision, say_key, status, state, answered_via, answered_at_secs, incident_id}; 30 s → default_spoken
async def broadcast(village_id, msg: ServerMessage, *, to: "all|control|<member_id>" = "all") -> None
async def control(village_id, kind, payload) -> None
async def post_message(village_id, *, author, kind, text, refs=(), source) -> Message   # D16; fan-out via LIVE
```
Stub (10:00): `decide` returns the matching `gate.schema.json` example; `start_verification`/`await_verification` replay `scam_call_tool_requests.json` variant `timeout`; `broadcast`, `post_message` log.

## Hub routing (`core/ws_hub.py`)
| Message | Route |
|---|---|
| `hello` | check `contract_version`; token → `(village, member_id, role)` or control; reply `snapshot`; bad token → `error{bad_token}` + close |
| `event` | all sockets of the village; `data` per role via `bindings.changed(event, role, member_id)` |
| `prompt` | sockets of `claimed_member_id` only; `closed: true` on terminal/deadline |
| `result` | the socket that sent the `action`/`ack` (`req_id`) |
| `control` | role `control` only |
| `patch` | sockets of that role with `rev == base_rev`; others get `snapshot` |
| `chat` | member sockets except role `elder`, plus control |
| `ping`/`pong` | 20 s; two missed pongs → drop |
| `error` | before close for `bad_token`, `contract_mismatch`; without close for `bad_message`, `not_allowed`, `rate_limited` |
