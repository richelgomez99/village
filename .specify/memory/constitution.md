# Village Constitution (v1.0.0, 2026-10-16)

Village: software that builds itself around your people. These principles bind every spec, plan and task in `specs/`. A task that violates one is wrong, however convenient.

## I. The agent acts on its own; code draws the lines it can't cross
The agent decides what to build, whom to check with, when to escalate and when to rebuild. But every consequential action passes a **deterministic gate** (`core/gate/`): pure functions, no network, no LLM, no Agent Memory reads. Rules live in `data/datasets/policy_cases.md`; every rule has a test; tests run with the model off. Never-rules: Village never moves money, never shares account details, never gives dosing advice, never calls anyone without recorded consent, never broadcasts an unverified claim. Silence is safe: an unanswered verification means "don't send".

## II. Nothing consequential without the right person's say-so
Money requests are verified with the named member through a second channel. Spec changes need a leader's approval. Anything about Carmen's shared information involves Carmen (P2). Invites and calls happen only after the founder activates the village.

## III. Every fact keeps its source; nothing is overwritten
Events carry `source{kind, ref, secs|url}`. Agent Memory writes carry provenance labels. Changes supersede with history; conflicts surface as uncertainty for a human. The safety path reads only the operational store.

## IV. Nothing reaches a person untested
Every generated version goes through the release gate: built and tested in a Daytona sandbox, used by a real browser (Anchor) at phone size, scored by evals (Arize), then published blue/green. A failing version never replaces the last good one.

## V. Built for the person, not the average user
Generated UI comes only from the fixed, tested catalog; unknown types render nothing. The accessibility floor (DECISIONS D8) is enforced by generated tests and cannot be themed away. Safety wording is pre-written and reviewed, never generated at runtime. Any language, any script; the elder view is always light and high-contrast.

## VI. Contracts first; lanes stay in their lanes
`contracts/` (schemas, OpenAPI, fixtures) is the shared language. Only the orchestrator changes it (bump `VERSION`). Lanes build against fixtures and mock what isn't merged. The seam between lanes is `core/services.py`.

## VII. Always a working version
Layers ship behind flags; each version (V0–V4) is tagged only when its acceptance check passes. If a cutoff is missed, the layer is cut, not the deadline. After 15:00 nobody touches the demo path.

## VIII. Observable and honest
Every agent step, tool call, gate decision and release stage is a span (Arize, OpenInference kinds; `session.id = village-<id>`). The decisions log is user-readable. No invented metrics anywhere: `[MEASURE: …]` until measured.

## IX. Simplicity under the clock
Prefer config over codegen, catalog over custom, in-process over remote, one WebSocket over many channels, Core-served static over proxies. Three sponsors named on stage; the rest on Devpost.

**Governance:** amendments require a note in DECISIONS.md. Specs cite the principle they serve. Tasks cite the acceptance check they satisfy.
