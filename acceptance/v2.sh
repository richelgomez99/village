#!/usr/bin/env bash
# V2 acceptance, core part (specs/003-founding-generation/tasks.md A2-1..A2-11): boots Core on a scratch
# port (default 8795) with the model off and the FakeDialer, drives founding -> draft -> activate -> redeem
# -> ask -> chat over real HTTP/WS (acceptance/v2_flow.py). `--url` runs against an already running Core.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${V2_PORT:-8795}"; URL=""
while [ $# -gt 0 ]; do case "$1" in --url) URL="$2"; shift 2;; --lane) shift 2;; *) shift;; esac; done
if [ -z "$URL" ]; then
  VILLAGE_LLM=off VILLAGE_DIALER=fake VILLAGE_MEMORY=off SURREAL_DB_URL= FOUNDER_LIVE_CALLS=0 \
    uv run uvicorn core.app:app --host 127.0.0.1 --port "$PORT" --log-level warning &
  PID=$!
  trap 'kill $PID 2>/dev/null || true' EXIT
  for _ in $(seq 1 80); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.25; done
  URL="http://127.0.0.1:$PORT"
fi
VILLAGE_LLM=off uv run python acceptance/v2_flow.py --url "$URL" --token "${CONTROL_TOKEN:-control}"
