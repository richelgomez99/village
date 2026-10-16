# Quickstart: Memory & evolve (FS-6)

For the memory, evals and builder lanes. Worktrees `../village-memory`, `../village-evals`, `../village-builder`; branches `lane/<name>`. FS-5 must be green (V3) before the live proposal path is exercised.

## 0. Prerequisites
```bash
uv run smoke/00_env_check.py                           # SURREAL_MEMORY_*, ARIZE_*, AWS_*/ANTHROPIC_API_KEY set
uv run smoke/06_memory.py --keep                       # scopes, triples supersession, asOf, uncertainty + resolve; note the latency table and the exact shapes
uv run smoke/07_arize.py                               # spans land; (FS-5 T014) update_evaluations visible
git tag | grep V3                                      # FS-5 green
```

## 1. Offline tests (model off, memory faked)
```bash
uv run pytest core/memory evals core/builder -q        # FakeAgentMemory (503 → queued, safety timing), FakeJudge, FakeArize, FakeRelease
uv run pytest core/gate -q                             # untouched; T46/T47 pattern tests still pass
```

## 2. Memory path for real
```bash
uv run uvicorn core.app:app --port 8787                # VILLAGE_LAYERS=core,gate,kit,release,memory
./scripts/reset_demo.sh                                # seeds events_reyes_seed.json → outbox → Agent Memory (watch /health.outbox)
curl -s "localhost:8787/villages/v_reyes/facts?subject=m_carmen" -H "x-member-token: $ANA_TOKEN" | jq '.facts[] | select(.key=="lisinopril_dose") | {value, valid_from, supersedes: .supersedes.value, source}'
curl -s "localhost:8787/villages/v_reyes/facts/person/m_carmen/lisinopril_dose/history" -H "x-member-token: $ANA_TOKEN" | jq .
curl -s "localhost:8787/villages/v_reyes/facts?subject=m_carmen&as_of=2026-10-02T00:00:00-04:00" ... | jq '.facts[] | select(.key=="lisinopril_dose").value'   # "5 mg"
# outage drill: point SURREAL_MEMORY_URL at a dead host, scan a lid → the scan still answers in < 50 ms; /health.outbox.queued grows; restore → drains
```

## 3. Session eval + detector
```bash
uv run python -m evals.session_possible_fraud conv_seed_1009 v_reyes        # Oct 9 seeded session → possible_fraud; mirror var/evals/sessions/
# after a real call (or the fixture replay): the post-call job runs it automatically
uv run python -m evals.detector v_reyes                                       # prints the proposal (status proposed) or "no pattern"
curl -s -X POST localhost:8787/improve -H "x-control-token: $CONTROL_TOKEN" -d '{"village":"v_reyes","mode":"evolve"}' | jq .proposal.id
```

## 4. Approve → rebuild → live patch (with FS-5 warm pool)
```bash
curl -s localhost:8787/health | jq '.prewarm'                                  # both ready
# open Carmen's phone (elder view) and the Control Room first
curl -s -X POST localhost:8787/villages/v_reyes/proposals/prop_reyes_scamcheck/approve -H "x-member-token: $ANA_TOKEN" | jq '{status, target_rev, release_id}'
# watch: strip runs; Carmen's phone grows "¿Es de verdad?"; then
curl -s localhost:8787/villages/v_reyes -H "x-control-token: $CONTROL_TOKEN" | jq '{spec_rev, published_rev}'     # published_rev 5
```
Reject drill: `wscat` → `{"type":"action","req_id":"r1","name":"reject_proposal","payload":{"proposal_id":"prop_reyes_scamcheck"}}` → status `rejected`, nothing built.

## 5. The number
```bash
uv run python -m evals.scam_experiment --concurrency 4          # ~2–4 min; writes var/evals/measured.json; prints "N/30 caught, M/20 false alarms" + experiment URL
jq . var/evals/measured.json
```

## 6. Pre-verified fallback (13:50) and acceptance
```bash
scripts/preverify_proposal.sh v_reyes      # detector → approve with publish=False → proposal ready, rel_reyes_r5 in_progress (5 stages passed); reset_demo keeps both
acceptance/v4.sh                           # see tasks.md T024; green → tag V4
```

## Gotchas
- Field casing: `/facts` takes snake_case (`observed_at`, `session_id`), `/query`/`/context` take camelCase (`asOf`, `lens`); unknown fields are silently ignored.
- Register scopes before writing or you get "unknown scope node"; the outbox does this once.
- Triples cannot carry `source.ref`; provenance lives in labels. Transcripts (`infer: full`) are what give `source.span`.
- Never await Agent Memory in a request handler; enqueue.
- `tool_choice` forced may 400 on 5.5 models: use `auto` + instruction, validate, repair once, template.
- The Reyes village must be built with builder **v1**; promote v2 only after that (the Evolve patch is the stage moment).
- Don't type numbers into Devpost; read `var/evals/measured.json`.
