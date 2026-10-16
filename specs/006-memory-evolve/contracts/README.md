# Contracts: Memory & evolve (FS-6)

Repo contracts consumed, unchanged: `proposal.schema.json` (the ScamCheck example is the acceptance fixture and the template fallback), `event.schema.json` (`pattern`, `spec_patch_proposed`, `spec_patch_applied`, source/provenance), `village_spec.schema.json` (views, printables, `custom_components`), `ws_messages.schema.json` (`patch` with `proposal_id` + `highlight`, `bv_proposal` under bind `proposals:pending`, `control{kind: reasoning}`), `common.schema.json` (`action_name` already has `approve_proposal`/`reject_proposal`; `view_patch_op`), `openapi.yaml` (`POST /villages/{id}/proposals/{pid}/approve`, `POST /improve`), `voice_tools.schema.json` (for the scam experiment inputs: `$defs/req_report_money_request`).

## Internal interfaces

`core/memory/__init__.py` (memory lane):
```python
async def remember_event(event: Event) -> None                       # enqueue; returns at once; no-op for *_qa and non-memory kinds
async def ingest_transcript(conversation_id: str, village: str, agent: str, turns: list[Turn]) -> None   # enqueue /facts/batch
async def note(village: str, agent: str, text: str, labels: list[str]) -> None                        # enqueue infer:none chunk
async def facts_for(village: str, subject: str | None = None, as_of: datetime | None = None) -> FactsResponse
async def fact_history(village: str, entity: str, key: str) -> list[FactVersion]
async def uncertainties(village: str, subject: str | None = None) -> list[Uncertainty]
async def resolve_uncertainty(village: str, uid: str, accepted_value: str, by: str, note: str) -> FactCard
async def fact_refs(village: str, subject: str, key: str, since: datetime) -> list[str]                 # for proposal evidence
def outbox_status() -> dict                                           # {queued, sent, dead, oldest_queued_age_s} for /health
```

`evals/__init__.py` (evals lane):
```python
async def session_eval(conversation_id: str, village: str) -> EvalRecord          # possible_fraud; logs + mirrors; triggers detector
async def detect_patterns(village: str) -> list[Proposal]                          # status=proposed, ops={} (builder fills)
async def sessions_with_label(village: str, label: str, since_days: int) -> list[SessionLabel]   # Arize (5 s) → mirror
async def run_scam_experiment(*, concurrency: int = 4) -> Measured                 # writes var/evals/measured.json
def latest_measured() -> Measured | None
async def run_builder_prompt_experiment(promote: bool = False) -> dict             # optional
def session_labels(village: str) -> list[SessionLabel]                            # Ask-why source (mirror)
```

`core/builder/patch.py` (builder lane):
```python
async def patch_for_proposal(proposal: Proposal, spec: VillageSpec) -> PatchResult   # {ops: {role: [op]}, needs_served, spec_ops, used_template: bool, trace_id}
```

`core/evolve.py` (core / orchestrator):
```python
async def raise_proposal(p: Proposal) -> Proposal
async def approve(village: str, pid: str, member_id: str) -> Proposal     # 403 / 409 semantics from spec FR-009
async def reject(village: str, pid: str, member_id: str) -> Proposal
async def verify_and_apply(p: Proposal) -> Proposal                      # builder → spec rev → release.run(publish=False) → apply
async def apply(p: Proposal) -> Proposal                                 # release.publish → patch frames → spec_patch_applied
```

FS-5 consumed: `release.run(village, rev, trigger="proposal", proposal_id=…, publish=False)`, `release.publish(release_id)`, `release.get_receipts`.

## WS frames emitted
- To the coordinator's sockets: `event{kind: spec_patch_proposed, data: {"proposals:pending": [bv_proposal]}}`; on status change the same bind is re-sent (`event` with updated `data`).
- To each affected role: `patch{rev, base_rev, role, ops, proposal_id, highlight}` after publish (clients on another rev receive `snapshot`).
- To the Control Room: `control{kind: proposal}` (addition below) and `control{kind: reasoning, payload{source: evolve, kind: decision|plan, text, trace_id}}`.

## Additions requested from the orchestrator (contract bump 1.0.0 → 1.1.0, additive)

1. **`ws_messages.schema.json` `control.kind` += `proposal`** with payload `{proposal: proposal.schema.json}` (full card for the Control Room's Evolve panel). Until merged, FS-6 sends the same object as `control{kind: reasoning, source: evolve, kind: plan, text: <title>}` plus the coordinator `event`; the kit renders the Control Room card from `event.data["proposals:pending"]` on the control socket (control snapshots carry the whole spec, so `bv_proposal` is enough for the card minus evidence quotes).
2. **`openapi.yaml` approve**: allow status `proposed` (starts verification, auto-applies on ready) in addition to `ready`; 409 only for `verifying|applied|rejected|failed`. Add `POST /villages/{id}/proposals/{pid}/reject` as the HTTP twin of the WS action (voice path needs HTTP).
3. **Fact view endpoints**: `GET /villages/{id}/facts?subject=&as_of=` → `FactsResponse`; `GET /villages/{id}/facts/{entity}/{key}/history`; `GET /villages/{id}/facts/uncertainty`; `POST /villages/{id}/facts/uncertainty/{uid}/resolve {accepted_value, note}` (coordinator token). Add `$defs/fact_card`, `$defs/fact_version`, `$defs/uncertainty` to `common.schema.json` or a new `facts.schema.json`.
4. **`voice_tools.schema.json`** `$defs/req_answer_proposal {proposal_id, answer: yes|no, conversation_id, caller_id, call_secs, utterance}` + response (only if `EVOLVE_VOICE=1` ships).
5. **`event.schema.json`**: optional new kind `spec_patch_rejected {proposal_id, by}`; otherwise the `decision` row is the record (acceptable in v1).
6. **`call_session`** (FS-2 internal) gains `root_span_id`, `trace_id` — not a contract, a request to the voice/core lanes.
7. **`openapi.yaml` `/improve`** already covers `mode: evolve|builder_prompt` and `detector`; FS-6 implements it as: `evolve` → `detect_patterns` + `raise_proposal` (returns the proposal); `builder_prompt` → the v1/v2 experiment job.

No change to `core/gate/`; the R-MONEY-PATTERN rule and the `pattern` event are FS-1's and are consumed as-is.
