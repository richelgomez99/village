#!/usr/bin/env bash
# V4 evolve acceptance: boots Core on a scratch port (default 8793) and drives acceptance/v4_flow.py.
#   acceptance/v4.sh            fake release ports (FakeDaytona/FakeAnchor/FakeEvals)
#   acceptance/v4.sh --real     real pipeline (Daytona/Anchor/evals from the environment / ENV_FILE)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${V4_PORT:-8793}"
MODE="fake"
while [ $# -gt 0 ]; do case "$1" in --real) MODE="real"; shift;; --port) PORT="$2"; shift 2;; *) shift;; esac; done
SET="evals/sets/v_reyes.jsonl"; cp "$SET" "/tmp/v4_set_backup.jsonl" 2>/dev/null || true
if [ "$MODE" = "real" ]; then
  if [ -n "${ENV_FILE:-}" ]; then set -a; . "$ENV_FILE"; set +a; fi
  export VILLAGE_EVOLVE_RELEASE=auto TUNNEL_URL= RELEASE_LOCAL_BASE="http://127.0.0.1:$PORT"
else
  export VILLAGE_EVOLVE_RELEASE=fake
fi
VILLAGE_EVOLVE_AUTO=on VILLAGE_DIALER=fake VILLAGE_MEMORY=off SURREAL_DB_URL= \
  uv run uvicorn core.app:app --host 127.0.0.1 --port "$PORT" --log-level warning &
PID=$!
trap 'kill $PID 2>/dev/null || true; cp /tmp/v4_set_backup.jsonl "$SET" 2>/dev/null || true' EXIT
for _ in $(seq 1 80); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.25; done
uv run python acceptance/v4_flow.py --url "http://127.0.0.1:$PORT" --timeout "${V4_TIMEOUT:-120}"
