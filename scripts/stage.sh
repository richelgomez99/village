#!/usr/bin/env bash
# stage.sh: the exact calls the presenter (or the orchestrator) runs between beats. Core on $CORE_URL (default http://127.0.0.1:8790).
# Usage: scripts/stage.sh reset | founding | proposal | caller elder|unknown | status
set -euo pipefail
H="${CORE_URL:-http://127.0.0.1:8790}"; CT="${CONTROL_TOKEN:-control}"; V="${DEMO_VILLAGE_ID:-v_reyes}"
j() { curl -sS -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' "$@"; }
case "${1:-status}" in
  reset)     bash scripts/reset_demo.sh ;;
  founding)  # Build beat: resume the Reyes intake at 8 of 10 into the demo village; the final draft is the rev 5 fixture (mode fixture), so later beats keep their cards.
             DESC=$(jq -r .demo_spoken_description data/villages/reyes_family.json)
             j -X POST "$H/villages" -d "$(jq -cn --arg d "$DESC" --arg v "$V" '{description:$d, language:"en", mode:"fixture", resume:8, village_id:$v, pace:3.0}')" ; echo
             echo "Now Ana types A10, A11, A12 in the Control Room box (or: scripts/stage.sh answer \"<text>\")." ;;
  caller)    # presenter's one phone: elder = the care recipient (Run beat); unknown = an unknown caller (Receptionist beat)
             j -X POST "$H/admin/demo-caller" -d "$(jq -cn --arg r "${2:?elder|unknown}" '{role:$r}')"; echo ;;
  answer)    j -X POST "$H/villages/$V/answers" -d "$(jq -cn --arg t "${2:?text}" '{text:$t}')"; echo ;;
  proposal)  j -X POST "$H/villages/$V/evolve/trigger" -d '{}' | jq -c '{id:.proposal.id,status:.proposal.status}' ;;
  status)    curl -s "$H/health" | jq -c '{ok,contract_version,llm:.deps.llm_model}'; j "$H/villages/$V/proposals" | jq -c '[.[]? // .proposals[]? | {id,status}]' 2>/dev/null; j "$H/villages/$V/releases" | jq -c '{live_rev}' ;;
  *) echo "usage: $0 reset|founding|answer <text>|proposal|caller elder|unknown|status"; exit 1 ;;
esac
