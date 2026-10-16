#!/usr/bin/env bash
# scripts/reset_demo.sh: put the demo back to a known state. Safe to run any number of times.
#
# Steps (DECISIONS D17), in order:
#   1. Core is up              GET  /health
#   2. Clear today's state     POST /admin/reset  (X-Admin-Key: $ADMIN_KEY)
#   3. Reload fixtures         uv run python -m core.tools.seed
#   4. Pre-warm                uv run python -m core.tools.warm
#   5. Set the demo clock      POST /clock/warp   {"to": $DEMO_CLOCK}
#
# Reads ADMIN_KEY, DEMO_CLOCK and CORE_URL from the environment, then from .env.
# Never prints key values. Exits non-zero on the first failed step.
#
# Usage: scripts/reset_demo.sh [--dry-run]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# Read one KEY=value from .env without sourcing the file (values may contain shell characters).
env_from_file() {
  local key="$1"
  [ -f "$ROOT/.env" ] || return 0
  grep -E "^[[:space:]]*${key}=" "$ROOT/.env" | tail -n 1 | cut -d= -f2- \
    | sed -e 's/[[:space:]]#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

ADMIN_KEY="${ADMIN_KEY:-$(env_from_file ADMIN_KEY)}"
DEMO_CLOCK="${DEMO_CLOCK:-$(env_from_file DEMO_CLOCK)}"
CORE_URL="${CORE_URL:-$(env_from_file CORE_URL)}"
CORE_URL="${CORE_URL:-http://127.0.0.1:8790}"  # D27
DEMO_CLOCK="${DEMO_CLOCK:-2026-10-16T20:50:00-04:00}"
SCOPES='["events_today","verifications","proposals","tokens","counters"]'

DONE=()
fail() {
  echo
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" >&2
  echo "RESET FAILED at step: $1" >&2
  echo "Reason: $2" >&2
  [ -n "${3:-}" ] && echo "Manual command: $3" >&2
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" >&2
  print_checklist
  exit 1
}
ok() { DONE+=("[x] $1"); echo "  ok  $1"; }
print_checklist() {
  echo
  echo "Reset checklist ($(date '+%H:%M:%S'))"
  for line in "${DONE[@]+"${DONE[@]}"}"; do echo "  $line"; done
}

[ -n "$ADMIN_KEY" ] || fail "config" "ADMIN_KEY is not set (environment or .env)" "echo 'ADMIN_KEY=...' >> .env"
command -v curl >/dev/null || fail "config" "curl not found"
command -v uv >/dev/null || fail "config" "uv not found"

echo "Resetting Village demo at $CORE_URL (clock target $DEMO_CLOCK)"
if [ "$DRY_RUN" = 1 ]; then
  echo "dry run: would call GET /health, POST /admin/reset $SCOPES, core.tools.seed, core.tools.warm, POST /clock/warp"
  exit 0
fi

# 1. Core is up
curl -fsS --max-time 5 "$CORE_URL/health" >/dev/null \
  || fail "health" "Core is not answering at $CORE_URL/health" "uv run uvicorn core.app:app --port 8787"
ok "Core answering at $CORE_URL"

# 2. Clear today's state
tmpbody=$(mktemp)
code=$(curl -sS --max-time 30 -o "$tmpbody" -w '%{http_code}' -X POST \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  --data "{\"scopes\":$SCOPES}" \
  "$CORE_URL/admin/reset") || code="000"
body=$(cat "$tmpbody" 2>/dev/null || true); rm -f "$tmpbody"
[ "$code" = "200" ] || fail "admin reset" "HTTP $code: $body" \
  "curl -X POST -H 'X-Admin-Key: \$ADMIN_KEY' -H 'Content-Type: application/json' --data '{\"scopes\":$SCOPES}' $CORE_URL/admin/reset"
ok "admin reset (scopes: events_today, verifications, proposals, tokens, counters)"

# 3. Reload fixtures
uv run python -m core.tools.seed >/dev/null || fail "seed" "core.tools.seed exited non-zero" "uv run python -m core.tools.seed"
ok "fixtures seeded (Reyes village, events, prescriptions, member tokens)"

# 4. Pre-warm
warm_out=$(uv run python -m core.tools.warm) || fail "warm" "core.tools.warm exited non-zero" "uv run python -m core.tools.warm"
if echo "$warm_out" | grep -qiE "stub|absent|\"failed\""; then
  ok "warm ran but did NOT pre-warm (sandbox/Anchor cold; first release will be slow): $(echo "$warm_out" | tail -n 1)"
else
  ok "warm: $(echo "$warm_out" | tail -n 1)"
fi

# 5. Set the demo clock
warp=$(curl -fsS --max-time 10 -X POST -H "Content-Type: application/json" \
  --data "{\"to\":\"$DEMO_CLOCK\"}" "$CORE_URL/clock/warp") \
  || fail "clock warp" "POST /clock/warp failed" "curl -X POST -H 'Content-Type: application/json' --data '{\"to\":\"$DEMO_CLOCK\"}' $CORE_URL/clock/warp"
ok "clock set: $warp"

print_checklist
echo "Demo reset complete."
