#!/usr/bin/env bash
# Kit V0 acceptance (T011): install, unit tests, build, headless render of the three fixture roles.
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci --no-audit --no-fund
npm test
npm run build
for f in index.html join.html control.html; do
  test -f "dist/$f" || { echo "missing dist/$f"; exit 1; }
done
# headless render (jsdom) of carmen / ana / marco through the fake Core: unknown-types=0, invalid-props=0,
# carmen 3 BigButtons + 911, ana/marco every fixture element present, refill card, scam replay updates all clients
npx vitest run tests/roles.fixture.test.tsx tests/scam.replay.test.tsx tests/elder.floor.smoke.test.tsx
echo "KIT V0 ACCEPTANCE: PASS"
