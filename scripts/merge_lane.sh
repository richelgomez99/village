#!/usr/bin/env bash
# merge_lane.sh <branch> [<branch>...]: merge lane branches into main (no-ff), then run the checks every merge must pass.
# Usage: from ~/village on main:  bash scripts/merge_lane.sh lane/gate 001-core-spine-gate
set -euo pipefail
[ "$(git branch --show-current)" = main ] || { echo "run on main"; exit 1; }
for b in "$@"; do
  echo "== merging $b"; git merge --no-ff -q -m "Merge $b into main" "$b"
done
echo "== contracts"; uv run --with jsonschema --with pyyaml python contracts/validate.py
echo "== tests"; uv sync -q && uv run pytest -q 2>&1 | tail -3
echo "== done: $(git log --oneline -1)"
