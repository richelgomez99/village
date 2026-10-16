#!/usr/bin/env bash
# kit-members acceptance: tabs from life areas (Reyes + block), chat kinds + composer, refill-day rule,
# Marco's headline / since-last-turn / swap, Lucía without prompts, names not ids, view-as "view only"; contracts still validate.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d node_modules ] || npm ci --no-audit --no-fund
npm test
npm run build
npx vitest run tests/members.test.tsx tests/roles.fixture.test.tsx tests/scam.replay.test.tsx tests/phone.copy.test.tsx
(cd .. && uv run -q --with jsonschema --with pyyaml python contracts/validate.py)
if grep -rni "carmen\|reyes\|lucía\|lucia\|marco" src/app/tabs.ts src/app/TabbedApp.tsx; then echo "village names in the generic shell"; exit 1; fi
echo "Manual: npm run dev → /?fake=ana | /?fake=marco | /?fake=lucia | /?fake=carmen (&start=0 plays the scam + chat)"
echo "KIT-MEMBERS ACCEPTANCE: PASS"
