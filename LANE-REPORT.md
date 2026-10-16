T001 · done · `uv run python - <<'PY' ... TestClient(app).get('/health') ... PY` · health deps use stubs; DB/live not wired yet; `uv run pytest core -q` currently collects no tests
T002 · done · `uv run python - <<'PY' ... TestClient(app).post('/tools/log_dose') ... PY` · services seam replays contract examples/fixtures and log-only broadcast/post_message
T003 · done · `uv run pytest core -q` · clock warp broadcasts to in-process WS hub; scheduler tick not wired yet
T004 · done · `uv run python -m core.db --apply`; `uv run pytest core/tests/test_ids.py -q` · `ids.py` done; DB uses SurrealDB Cloud when `SURREAL_DB_URL` is set and keeps the in-process mirror/fallback when URL is empty; CAS-compatible return shape implemented
T005 · done · `uv run python -m core.tools.seed` · fixture seed loads Reyes spec/events and generated member tokens; no hashed slot tokens because D22 cuts lid scans from V0
T006 · partial · `uv run pytest core/tests/test_spine.py -q` · one WebSocket hub and event fan-out work; SurrealDB LIVE subscriber is mocked by direct in-process publish
T007 · partial · `uv run pytest core/tests/test_spine.py -q` · V0 dose-day and rota bindings implemented; fixture-exact lid scan binding not applicable to D22 check-in path
T008 · partial · `uv run pytest core/tests/test_spine.py -q` · decisions are persisted and broadcast; uses `core/gate_fallback.py` until gate lane merges
T009 · cut · not run · `/s/{slot_token}` optional per D22 addendum; not implemented in this increment
T010 · partial · `uv run pytest core/tests/test_spine.py -q` · HTTP action/tool path and decisions endpoint work; WS inbound actions not wired yet
T011 · done · `acceptance/run.sh V0 --lane core` · acceptance covers D22 check-in tool path, prescriptions, clock warp and core tests; gate lane tests not present in this worktree yet
LD-1: D22 addendum makes `/s/{slot_token}` optional for V0; core V0 acceptance will use `POST /tools/log_dose` for check-in → event log stub until T004-T008 replace persistence.
LD-2: Decision `mode` is recorded under `refs` as `{"kind":"mode","id":"acted_alone"}` because the decision schema has no first-class `mode` field.
