# specs/: spec-kit artifacts (everything except implementation)

Constitution: `.specify/memory/constitution.md`. Product definition: `PRODUCT.md`. Each folder has `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/README.md`, `quickstart.md`, `tasks.md`. Lanes execute their `tasks.md` in order; every task names its acceptance and the constitution principle it serves. Contract changes requested by a spec are applied by the orchestrator only (see `RECONCILE.md`; contracts are at 1.1.0).

| Spec | Feature set | Lanes | Versions |
|---|---|---|---|
| `001-core-spine-gate` | Core app, SurrealDB LIVE → WebSocket hub, lid scan, pure gate + state machines, clock, decisions log, `services.py`, chat messages | core, gate | V0, V1, V2 (chat) |
| `002-verification-loop` | ElevenLabs agents as code, tools/init/post-call webhooks, verification (app prompt + outbound call), verbatim say | voice, core, kit touchpoints | V1 |
| `003-founding-generation` | Founder conversation, streamed blueprint, draft → activate → join, per-role render, Ask-Village-why, chat routing, second village | builder, core, kit touchpoints | V2, V3 |
| `004-kit-control-room` | Catalog + renderer + WS client, role views, scan/join/fact pages, VillageChat, PWA, Control Room (A), printables, test selectors | kit | V0 → V4 |
| `005-release-gate` | Daytona bundle build/tests → dist served by Core, Anchor phone-size QA + live view, in-process Arize release evals, receipts, blue/green, caught-and-fixed build, pre-warm | release, evals | V3 |
| `006-memory-evolve` | Agent Memory with provenance (outbox), Fact view, `possible_fraud` session eval, detector → proposal → approve → rebuild → live patch, scam eval number | memory, evals, builder | V4 |
| `007-pitch-kit` | Devpost per version, README, slides, video + 30 s clip, thumbnail, `reset_demo.sh`, `acceptance/run.sh`, T-15 | pitch, core | all day |

Order of merges: 001 → 002/003/004 (parallel) → 005 → 006; 007 alongside.
