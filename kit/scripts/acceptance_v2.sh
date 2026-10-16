#!/usr/bin/env bash
# Kit V2 acceptance (T029): unit tests, build, Control Room regions through the offline fake Core.
#   scene reducer per frame kind · blueprint from reyes_spec + block_spec · captions under every Spanish node ·
#   counter follows frames · phones region renders 3 roles · ask why / QR / view-as / village tab · scam + founding replays
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d node_modules ] || npm ci --no-audit --no-fund
npm test
npm run build
for f in index.html join.html control.html; do
  test -f "dist/$f" || { echo "missing dist/$f"; exit 1; }
done
npx vitest run tests/control.scene.test.ts tests/control.room.test.tsx tests/roles.fixture.test.tsx tests/elder.floor.smoke.test.tsx
echo "Manual: npm run dev → /control.html?fake=control&seq=founding|scam|release|evolve (&tail=denied, &speed=2)"
echo "KIT V2 ACCEPTANCE: PASS"
