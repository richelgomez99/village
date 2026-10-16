# Contracts: Release gate (FS-5)

Repo contracts consumed, unchanged: `release.schema.json` (receipt, the r3/r4 examples are the acceptance fixtures), `village_spec.schema.json` (bundle input), `ws_messages.schema.json` (`control{kind: release|build_log|qa|reasoning}`, `snapshot.rev`), `lid_scan.schema.json` + `fixtures/lid_scan_sequence.json` (Anchor scan flow expectations), `fixtures/ws_sequence_scam.json` (prompt → result frames for the verification flow), `event.schema.json` (`release`, `qa` kinds).

## Internal interfaces (Python, `core/release/__init__.py`; the seam other lanes import)

```python
async def run(village_id: str, rev: int, *, trigger: Literal["initial","proposal","repair","manual"] = "manual",
              proposal_id: str | None = None, repair_of: str | None = None, attempt: int = 1,
              inject_failure: Literal["contrast"] | None = None, publish: bool = True) -> Receipt
    """Six stages. publish=False (used by FS-6 for proposals) stops with stage live=pending, result=in_progress."""

async def publish(release_id: str) -> Receipt
    """Runs the live stage of an in_progress receipt whose first five stages passed. Idempotent."""

async def rollback(village_id: str) -> Receipt
    """Sets published_rev to the previous released rev; new receipt result=rolled_back, trigger=manual."""

async def repair(village_id: str, receipt: Receipt) -> int | None
    """Floor autofix → builder patch_app repair; returns the new rev to release as trigger=repair, or None."""

async def prewarm() -> None ;  def pool_status() -> dict
async def get_receipts(village_id: str, limit: int = 20) -> list[Receipt]
```

`evals/release/__init__.py` (evals lane):
```python
async def run(receipt: Receipt, spec: VillageSpec, artifacts: QAArtifacts, span_ids: dict[str, str]) -> list[EvalRecord]
async def log_to_arize(records: list[EvalRecord]) -> bool      # update_evaluations; False on failure (never raises)
def mirror(records: list[EvalRecord]) -> Path                 # var/evals/releases/<rel>.json + eval_record rows
def thresholds() -> dict[str, float]                          # {"spec_coverage":1.0,"safety_copy":1.0,"translation_backcheck":0.9,"elder_accessibility":0.8}
```

`core/services.py` additions needed from core (orchestrator): `reset_village(village_id, *, spec_rev, seed) -> ShadowTokens`, `start_verification(village_id, claimed_member, amount, source)`, `set_published_rev(village_id, rev) -> bool` (CAS), `snapshot_all(village_id)`.

## WS frames emitted (all existing kinds)
- `control{kind: release, payload.receipt}` on every stage transition and on later evidence updates (video).
- `control{kind: build_log, payload{release_id, rev, stage, line, level}}` per sandbox log line (rate-limited to 20/s, tail kept).
- `control{kind: qa, payload{release_id, rev, stage, status, summary?, evidence_url?, live_view_url?}}` at QA/test/eval stage start and end.
- `control{kind: reasoning, payload{source: release, kind: note|decision, text, trace_id}}` for budget overrun and repair decisions.

## Additions requested from the orchestrator (contract bump 1.0.0 → 1.1.0, additive)

1. **`GET /villages/{id}/releases`** (control token) → `{receipts: Receipt[]}` newest first; needed for Control Room reconnect and for `acceptance/v3.sh`.
2. **`POST /villages/{id}/releases`** (control token) body `{rev, trigger?: manual|repair, repair_of?, inject_failure?: contrast}` → 202 `{release_id}`; the manual/demo trigger (used by `scripts/caught_and_fixed.sh`).
3. **`GET /v/{id}/r/{rev}/{path}`** candidate static path (not in `openapi.yaml`; `/v/{id}/{path}` is documented as the published path). Query `village=<id>_qa` is accepted by the kit to point the WS at the shadow village.
4. **`GET /releases/{rel}/qa/{file}`** evidence files (PNG, report.json, qa.mp4). Could be folded under `/v/{id}/…`; orchestrator's call.
5. `release.schema.json`: no change. If the strip wants per-assertion thumbnails, `details.summary` + `evidence_url` are enough in v1.

Nothing in `core/gate/` or the voice tools changes.
