#!/usr/bin/env bash
# acceptance/run.sh V<n> [--lane <lane>]: runs acceptance/v<n>.sh (lanes add their hooks there). Exits non-zero on failure.
set -euo pipefail
V="${1:?version, e.g. V0}"; shift || true
f="acceptance/$(echo "$V" | tr 'V' 'v').sh"
[ -x "$f" ] || { echo "no $f yet"; exit 1; }
exec bash "$f" "$@"
