# Quickstart: FS-1 locally

## 1. Prerequisites
```bash
brew install surrealdb/tap/surreal          # or curl -sSf https://install.surrealdb.com | sh
cp .env.example .env                         # CONTROL_TOKEN, SLOT_TOKEN_SECRET, SURREAL_* below
surreal start -u root -p root memory         # ws://localhost:8000; embedded mem:// has no LIVE
export SURREAL_DB_URL=ws://localhost:8000 SURREAL_DB_NS=village SURREAL_DB_DB=main SURREAL_DB_USER=root SURREAL_DB_PASS=root
```

## 2. Schema and seed
```bash
uv run python -m core.db --apply                  # core/schema.surql, idempotent → "schema OK (13 tables)"
uv run python -m core.fixtures --reset v_reyes     # reyes_spec rev 4 + events_reyes_seed; prints member + lid tokens
```

## 3. Run Core
```bash
VILLAGE_LAYERS=0 VILLAGE_LLM=off uv run uvicorn core.app:app --reload --port 8787
curl -s localhost:8787/health | jq '.ok, .deps'    # true, {"surreal":"ok","live":"ok","llm":"off"}
```

## 4. Gate tests (model off, no network)
```bash
uv run pytest core/gate -q
uv run pytest core/gate -q -k "T28 or T29 or T31 or T45 or T49 or T50"
```

## 5. Spine test
`uv run acceptance/v0.sh` (applies, seeds, starts Core, three WS clients, scan ×2, warp, scan, checks frames, runs gate tests). By hand:
```bash
uv run python -m core.tools.wsclient --village v_reyes --token $MT_CARMEN &   # repeat for ANA, MARCO
curl -s -H 'Accept: application/json' "localhost:8787/s/$LID_MORNING" | jq '.decision.decision, .deduped'   # "record", false
curl -s -H 'Accept: application/json' "localhost:8787/s/$LID_MORNING" | jq '.deduped'                      # true
curl -s -X POST -H "Authorization: Bearer $CONTROL_TOKEN" localhost:8787/clock/warp -d '{"minutes":38}'
curl -s -H 'Accept: application/json' "localhost:8787/s/$LID_MORNING" | jq '.decision.say_key, .page.tone'  # "dd_report", "report"
```

## 6. V0 acceptance by hand
1. Open the morning lid URL on a phone: green "Anotado, Carmen", read aloud.
2. All three clients print `event{kind: dose}`; elder and coordinator frames carry `facts:dose_event?…` with `morning: taken`.
3. Reload within 10 s: same page, no new frames.
4. Warp +38 min, scan again: amber "Esta tapa ya se anotó a las 8:02. Le avisamos a Marco."; frames `dose_repeat_scan` then `escalation`; Marco's frame carries `alerts:active` "Village is calling you".
5. `GET /villages/v_reyes/decisions?limit=3` (control token) lists three decisions with `rules_fired`.
6. `pytest core/gate -q` green with Wi-Fi off.
7. Restart `surreal`, re-seed: `/health deps.live` goes `down` then `ok` without restarting Core; reconnecting clients get a snapshot.

## 7. V1 and V2 checks
```bash
uv run acceptance/v1.sh   # money_request → prompt to Marco → answer no → denied frames; timeout via warp; duplicate webhook cached
curl -s -X POST -H "Authorization: Bearer $MT_ANA" localhost:8787/villages/v_reyes/messages -d '{"text":"@Village why did you call Marco?"}'   # V2: chat frame on Ana + Marco + control, none on Carmen
```
