#!/usr/bin/env bash
set -euo pipefail

uv run python -m core.tools.seed
uv run python -m core.tools.warm
curl -fsS -X POST \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: ${ADMIN_KEY:-change-me-admin-key}" \
  --data '{"scopes":["events_today","verifications","proposals","tokens","counters"]}' \
  "${CORE_URL:-http://127.0.0.1:8787}/admin/reset" >/dev/null || true
