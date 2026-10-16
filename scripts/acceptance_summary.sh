#!/usr/bin/env bash
# scripts/acceptance_summary.sh: which acceptance checks exist, whether they pass, and which version tags exist.
# Usage: scripts/acceptance_summary.sh [--list]   (--list: don't run the checks, only list them)
# Exit code: 0 if every existing check passed (or --list), 1 otherwise.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN=1; [ "${1:-}" = "--list" ] && RUN=0
LOGDIR="${TMPDIR:-/tmp}"; LOGDIR="${LOGDIR%/}/village-acceptance"; mkdir -p "$LOGDIR"

echo "Acceptance checks ($(date '+%H:%M:%S'), $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD))"
failed=0; found=0
for v in 0 1 2 3 4; do
  f="acceptance/v$v.sh"
  if [ ! -f "$f" ]; then
    printf "  V%s  %-6s %s\n" "$v" "absent" "$f"
    continue
  fi
  found=$((found + 1))
  if [ "$RUN" = 0 ]; then
    printf "  V%s  %-6s %s\n" "$v" "exists" "$f"
    continue
  fi
  log="$LOGDIR/v$v.log"
  start=$(date +%s)
  if bash "$f" >"$log" 2>&1; then status="PASS"; else status="FAIL"; failed=$((failed + 1)); fi
  printf "  V%s  %-6s %s (%ss, log %s)\n" "$v" "$status" "$f" "$(( $(date +%s) - start ))" "$log"
  [ "$status" = "FAIL" ] && tail -n 5 "$log" | sed 's/^/        /'
done

echo
echo "Version tags"
tags=$(git tag --list | grep -E -- '(-v[0-4]$|^V[0-4]($|-))' | sort -t- -k2 || true)
if [ -n "$tags" ]; then
  echo "$tags" | while read -r t; do printf "  %-14s %s\n" "$t" "$(git log -1 --format='%h %ad %s' --date=format:'%H:%M' "$t")"; done
else
  echo "  none"
fi
for want in V0-green V1-green V2-green V3-green V4-green; do
  git rev-parse -q --verify "refs/tags/$want" >/dev/null || printf "  %-14s %s\n" "$want" "not tagged"
done

echo
[ "$RUN" = 1 ] && echo "Summary: $found checks found, $failed failed."
[ "$RUN" = 1 ] && [ "$failed" -gt 0 ] && exit 1
exit 0
