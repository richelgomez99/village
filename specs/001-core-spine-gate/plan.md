# Implementation Plan: FS-1 Core spine & safety gate

## Technical context
Python 3.13, `uv`, FastAPI + uvicorn (native WebSocket), pydantic v2 + pydantic-settings, httpx<1, `surrealdb>=3.0.0b1` (`AsyncSurreal`, ws/wss only: embedded `mem://` has no LIVE), pytest + `jsonschema` (validate Decisions, drafts and frames against `contracts/schemas`). Store: SurrealDB Cloud ns `village` db `main`; fallback `surreal start -u root -p root memory`. Baseline: `smoke/10_spine_local.py` (webhook → gate → CREATE → LIVE → 12 clients, p50 2.3 ms).

## Architecture
```
 phones / scan page / tests ──HTTP+WS──► core.app
   routes: health scan actions verifications messages clock decisions ws
                 └────────────────► core/services.py (seam)
        ┌──────────────┼──────────────────┐
  core/gate/ (pure)  core/db.py (CAS,   core/ws_hub.py (routing, snapshot, bindings)
  decide / step_*    RecordID map)             ▲ on_row
                          └──► SurrealDB ──► core/live.py (LIVE SELECT, reconnect)
                                  ▲
                   core/scheduler.py (5 s tick) + core/clock.py (warp)
```
**LIVE → hub.** `live.py` owns one subscriber connection with `LIVE SELECT` on `event`, `view`, `verification`, `message`. Each notification is mapped back to contract ids and passed to `ws_hub.on_row(table, action, row)`. `event` → `event{event, data}` with per-role bindings; `verification` → `prompt` open/close for the claimed member; `view` → `patch` or snapshot on rev gap; `message` → `chat{message}` to member and control sockets (not elder). The writer connection never fans out directly, so seeds and restarts behave like live writes.

**RecordID mapping** (`core/ids.py`): `v_reyes ↔ village:reyes` (strip `v_`); all other ids keep the full contract id as key (`member:m_marco`, `event:ev_…`, `verification:ver_…`, `decision:dc_…`, `message:msg_…`). `to_rid`/`to_cid` are bijective and unit-tested; only `db.py` calls them.

**Gate interface** (`core/gate/__init__.py`, pure):
```python
def decide(inp: GateInput) -> Decision
def step_verification(v, ev: VerEvent, now) -> tuple[Verification, list[Emit]]
def step_dose_window(w, ev: WindowEvent, now) -> tuple[DoseWindow, list[Action]]
def say(key, **vars) -> Say
```
`VerEvent = created | answer(value, via, member_id) | await_returned | tick | call_failed`; `Emit = event_draft | notify | prompt_close | cancel_call`. `WindowEvent = tick | dose(event_id, taken_at, confidence) | skip_ack | call_result`; `Action = CALL | NOTIFY | EMIT`. Rule order: `R-KILL → R-911 → R-MONEY-NEVER → R-MONEY-UNKNOWN → R-MONEY-VERIFY(+VERIFY-CONSENT, PATTERN) → R-MONEY-DEFAULT → R-DOUBLE → R-DOSE-ADVICE → R-CONSENT → R-MISSED → R-WINDOW → R-SPEC/R-AUTONOMY → R-NOOP`; `advise_911` is never downgraded.

## Project structure
```
core/
  app.py settings.py clock.py ids.py db.py schema.surql live.py ws_hub.py bindings.py
  services.py scheduler.py fixtures.py dialer.py
  routes/ health.py scan.py actions.py verifications.py messages.py clock.py decisions.py ws.py
  templates/scan.html   tools/wsclient.py
  gate/ __init__.py models.py say.py sm_verification.py sm_dose_window.py
        rules/ kill.py emergency.py money.py dose.py consent.py autonomy.py noop.py
        tests/ conftest.py test_policy_cases.py test_sm_verification.py test_sm_dose_window.py test_schema_roundtrip.py
  tests/ test_ids.py test_bindings.py test_scan.py test_hub.py test_messages.py
acceptance/ run.sh v0.sh v1.sh
```

## Dependencies on contracts
`common`, `event`, `gate`, `verification`, `lid_scan`, `ws_messages`, `voice_tools` (`tool_call_id`, `verification_answer_request`, `data_*`), `openapi.yaml` (`/health /s /v/{id}/actions /verifications/{vid}/answer /clock/warp /ws`); fixtures `reyes_spec`, `events_reyes_seed`, `lid_scan_sequence`, `ws_sequence_scam`, `scam_call_tool_requests`. D16 needs a contract bump (`chat` frame, `message` schema, `POST /villages/{id}/messages`); until then Core validates them against a local pydantic model mirrored in `contracts/README.md` here.

## Risks + mitigations
| Risk | Mitigation |
|---|---|
| Cloud free tier latency (0.25 vCPU) | smoke 06b at 09:45; one env var switches to local surreal, same DDL |
| Cloud signin shape | try `{namespace, database, username, password}` then root |
| LIVE subscriber dies silently | 10 s heartbeat query; reconnect with backoff; `resync`; `/health deps.live` |
| CAS result shape (`[]` inside list) | `cas_update()` inspects the inner list, tested locally |
| `record<…>` rejecting strings | mapping only in `db.py`; a test inserts every fixture row |
| Gate drift from contracts | `test_schema_roundtrip` validates every Decision/draft |
| Warp timing | tick runs synchronously inside `/clock/warp` |
| Two lanes in `core/` | gate owns `core/gate/**` only; core imports only `core.gate` public names |

## Version mapping
| Version | Lands |
|---|---|
| **V0 11:00** | app, settings, health, DDL, ids, fixtures, LIVE subscriber, hub (hello/snapshot/event/control/error/ping), bindings (dose day, rota me), scan route, actions `log_dose/check_in_ok/need_help`, real `decide/record_event`, clock + warp, decisions log, all gate rules + both SMs + tests, `acceptance/v0.sh` |
| **V1 12:15** | verification persistence + CAS, `idem`, tick loop, `prompt/result`, `/verifications/{vid}/answer`, actions `answer_verification/start_verification/ack_incident`, `await_verification` long-poll, incident upsert, alert/prompt/incident bindings, restart recovery, `acceptance/v1.sh` |
| **V2 13:00** | `message` table, `chat` fan-out, `POST /villages/{id}/messages`, system messages on incident/proposal/receipt/nudge, `@Village` → ask routing |

## Fallback
`brew install surrealdb/tap/surreal && surreal start -u root -p root memory`; `SURREAL_DB_URL=ws://localhost:8000`, user/pass `root`. Same code path, live queries work.
