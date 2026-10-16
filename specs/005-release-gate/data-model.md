# Data model: Release gate (FS-5)

Contract types come from `contracts/schemas/release.schema.json` and `common.schema.json`. Internal types below are pydantic models in `core/release/` and `evals/release/`; they are not contracts unless stated.

## 1. Receipt (= `release.schema.json#/$defs/receipt`, persisted)

| Field | Type | Notes |
|---|---|---|
| `id` | `rel_<village>_r<rev>[_a<attempt>]` | `rel_reyes_r3`, `rel_reyes_r4`; a third attempt is `rel_reyes_r4_a3` |
| `village` | village id | `v_reyes`, `v_w147` |
| `rev` | int | spec rev being released |
| `previous_live_rev` / `live_rev` | int \| null | read at start (under the per-village lock) / set at the end |
| `attempt` | 1..3 | per rev lineage |
| `repair_of` | release id | links the repair to the blocked receipt |
| `trigger` | `initial` \| `proposal` \| `repair` \| `manual` | `proposal` carries `proposal_id` |
| `trace_id` | 32 hex | root span of `release.run` |
| `stages[6]` | ordered `spec, daytona_build, tests, anchor_qa, arize_evals, live` | each with `status`, `started`, `ended`, `details`, optional `evidence_url`, `trace_id` |
| `result` | `in_progress` \| `released` \| `blocked` \| `rolled_back` | `rolled_back` reserved for a manual `release.rollback(village)` (sets `published_rev` back; new receipt) |
| `created_at` | datetime (Clock) | |

**Stage `details` usage by stage** (all keys from the schema's closed set):

| Stage | Keys written |
|---|---|
| `spec` | `summary` |
| `daytona_build` | `summary`, `sandbox_id`, `duration_ms`, `preview_url`?, `error`? |
| `tests` | `summary`, `tests_passed`, `tests_failed`, `failures[]`, `duration_ms`, `error`? (`no_report`) |
| `anchor_qa` | `summary`, `viewport="390x844"`, `anchor_session_id`, `live_view_url`, `video_url`?, `duration_ms`, `error`? (`app_unreachable:*`, `anchor_unavailable`, `assertion:<name>`); `evidence_url` → `/releases/{rel}/qa/` |
| `arize_evals` | `eval_scores{}`, `eval_thresholds{}`, `failures[]` (keys below threshold, `judge_timeout` notes), `duration_ms`; `trace_id`, `evidence_url` → Arize trace link |
| `live` | `summary="published_rev a → b"`, `roles_patched[]`, `error`? |

Persistence: SurrealDB table `release` (`id` mapped `RecordID("release", "<id>")`, fields as above, `village` as `record<village>`), plus `events` row `kind=release` on completion. Filesystem: `var/releases/<village>/r<rev>/{bundle/, dist/, qa/report.json, qa/*.png, qa.mp4, build.log}`.

## 2. Village revision pointers (operational store, `village` table)

| Field | Meaning |
|---|---|
| `spec_rev` | latest spec rev that validated (may be ahead of what phones see) |
| `published_rev` | the rev `/v/{id}/` serves and `snapshot.rev` reports; moves only on a `released` receipt or a rollback |
| `candidate_rev` | rev currently staged at `/v/{id}/r/{rev}/` (null when none) |
| `last_release_id` | for the strip's default row |

Invariant: `published_rev ≤ spec_rev`; `candidate_rev ∈ {null} ∪ (published_rev, spec_rev]`. The WS hub reads `published_rev` for `snapshot.rev`; a `patch` with `base_rev != client rev` triggers a fresh snapshot (contract invariant 6).

## 3. Bundle (internal, `core/release/bundle.py`)

```
Bundle = {
  "spec.json":            VillageSpec rev (what the kit renders; identical to the runtime spec)
  "theme.json":           {"accent": "#2F6B57", "relationship_words": {...}, "density": {...}, "lang": {...}}   # village layer only
  "i18n/es.json" …:       strings keyed by say_key / ui key; safety lines copied verbatim from policy_cases.md
  "manifest.webmanifest": name = village name, start_url "./", icons from the kit
  "custom/PillOrganizer.tsx": rendered from custom_components[].config (lid colors, slots)
  "tests/floor/contrast.test.ts | sizes.test.ts | safety_colors.test.ts | actions.test.ts | render.test.tsx"
  "tests/floor/floor.constants.ts"
  "build.sh", "vite.config.ts"
}
```
Floor test parameters come from the spec: role keys, elder element ids, `voice_lines[].say_key`, languages; the thresholds come only from `floor.constants.ts` (cannot be themed away).

## 4. QA report (internal, `var/releases/…/qa/report.json`)

```json
{"release_id":"rel_reyes_r4","rev":4,"village":"v_reyes","shadow_village":"v_reyes_qa","viewport":"390x844",
 "anchor_session_id":"sess_…","live_view_url":"https://live.anchorbrowser.io/inspector.html?sessionId=…",
 "assertions":[{"name":"a1_scan_recorded","ok":true,"ms":2140,"png":"a1_scan_recorded.png","seen":"Anotado 8:02"},
               {"name":"a2_scan_report","ok":true,"ms":1630,"png":"a2_scan_report.png","seen":"Esta tapa ya se anotó…"},
               {"name":"a3_prompt_denied","ok":true,"ms":3010,"png":"a3_prompt_denied.png","event_ids":["ev_…"]},
               {"name":"a4_elder_view","ok":true,"ms":900,"png":"a4_elder_view.png"}],
 "video_url":null,"error":null}
```

## 5. EvalRecord (internal, `evals/release/`; mirrored to `eval_record` table and `var/evals/releases/<rel>.json`)

| Field | Type | Notes |
|---|---|---|
| `id` | `evr_<rel>_<name>` | |
| `release_id`, `village`, `rev` | | |
| `name` | `spec_coverage` \| `safety_copy` \| `translation_backcheck` \| `elder_accessibility` | |
| `label` | string | e.g. `covered`, `missing`, `safe`, `unsafe`, `equivalent`, `drift`, `accessible`, `judge_timeout`, `judge_unavailable` |
| `score` | float 0..1 \| null | null only with a timeout/unavailable label |
| `threshold` | float | from `evals/release/thresholds.py` |
| `passed` | bool | `score ≥ threshold` (deterministic component must also pass for `safety_copy`) |
| `explanation` | ≤ 600 chars | judge text or the deterministic diff |
| `span_id` | 16 hex | span the eval was attached to in Arize |
| `judge_model`, `duration_ms`, `attempts` | | |
| `inputs_ref` | path | what was judged (file under `var/releases/...`) |

Arize dataframe columns: `context.span_id`, `eval.<name>.label`, `eval.<name>.score`, `eval.<name>.explanation`.

## 6. Warm pool (in-memory, reported by `/health`)

```
WarmPool = {"sandbox": {"id", "created_at", "last_heartbeat", "state": ready|taken|miss},
            "anchor":  {"session_id", "cdp_url"(never logged), "live_view_url", "created_at", "last_heartbeat", "state"}}
```

## 7. Shadow village `<id>_qa`
A full village record cloned from the candidate rev with its own members (`m_*` ids identical, tokens different), its own slot tokens, and a ledger seeded from `lid_scan_sequence.json` (fresh per run). Excluded from: FS-6 detector, Control Room counters, Ask-Village-why, Agent Memory writes (outbox filter on `village.endswith("_qa")`).

## 8. Ledger events this feature writes
- `release` (payload `{rev, release_id, result, live_rev}`, `source{kind: system, ref: release}`) on completion.
- `qa` (payload `{rev, release_id, stage, status, evidence_url?}`) for `tests`, `anchor_qa`, `arize_evals` stage ends (optional; Control Room gets `control{kind: qa}` anyway).
- Shadow-village only: `dose`, `dose_repeat_scan`, `money_request`, `verification_*`, `incident` from the QA flows, `source.ref=release-qa`.
