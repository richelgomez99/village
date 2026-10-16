#!/usr/bin/env bash
# V1 acceptance. `acceptance/run.sh V1 --lane core` runs the core lane: boots Core on a scratch port
# with the FakeDialer, drives the scam flow over real sockets (acceptance/v1_flow.py), then pytest.
set -euo pipefail
cd "$(dirname "$0")/.."
LANE="all"
while [ $# -gt 0 ]; do case "$1" in --lane) LANE="$2"; shift 2;; *) shift;; esac; done
PORT="${V1_PORT:-8792}"

core_v1() {
  VILLAGE_DIALER=fake VILLAGE_MEMORY=off SURREAL_DB_URL= uv run uvicorn core.app:app --host 127.0.0.1 --port "$PORT" --log-level warning &
  PID=$!
  trap 'kill $PID 2>/dev/null || true' EXIT
  for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.25; done
  uv run python acceptance/v1_flow.py --url "http://127.0.0.1:$PORT"
  kill $PID 2>/dev/null || true
  trap - EXIT
  uv run pytest -q
}

case "$LANE" in
  core|all) core_v1 ;;
  *) echo "no V1 hooks for lane $LANE"; exit 1 ;;
esac
