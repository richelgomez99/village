#!/usr/bin/env bash
# Usage: ./set-target.sh https://abc-def.trycloudflare.com
#   or:  ./set-target.sh auto /path/to/cloudflared.log   (scrapes the quick-tunnel URL)
set -euo pipefail
cd "$(dirname "$0")"
if [[ "${1:-}" == "auto" ]]; then
  URL=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "${2:?log path}" | tail -1)
else
  URL="${1:?target url}"
fi
echo "Pointing front door at $URL"
npx -y wrangler@latest deploy --var "TARGET:$URL"
