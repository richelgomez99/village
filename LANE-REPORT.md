PAUSED (uncommitted: none)
LD-1: D22 supersedes older prompt text mentioning lid stickers; builder strips `lid_qr` channels on generated/template specs and keeps refill/check-in capabilities instead.
LD-2: Core lane service needs are captured in `core/builder/ports.py`; builder tests and `scripts/build_village.py` use `core/builder/services_stub.py`.
LD-3: LLM-off is the default lane acceptance path; live model calls can be wired through `core.llm.llm()` later without changing the public builder API.
T001 · done · `uv run pytest core/builder -q` · prompt tools parsed locally; model mocked/off
T002 · done · `uv run pytest core/builder -q` · validation uses contract JSON Schema plus local invariants
T003 · done · `uv run python -m core.builder.prompts --probe --prompt local` · Prompt Hub lazy import falls back to local
T005 · done · `uv run scripts/build_village.py --description-from data/villages/reyes_family.json --llm off` · deterministic blueprint replay, not live LLM stream
T006 · done · `uv run pytest core/builder -q` · fixture mapping plus D22 lid_qr removal
T007 · done · `uv run scripts/build_village.py --description-from data/villages/reyes_family.json --llm off` · render path is template fallback under model-off
T008 · done · `uv run pytest core/builder -q` · fixtures remapped only by village id
T009 · done · `uv run scripts/build_village.py --description-from data/villages/reyes_family.json --llm off` · spans are no-op until evals/core obs merges
T010 · done · `uv run scripts/build_village.py --description-from data/villages/reyes_family.json --llm off --time` · no real timings recorded because model is off
T014 · done · `uv run pytest core/builder -q` · ask uses in-memory decisions/facts/events and deterministic answer
T015 · done · `uv run pytest core/builder -q` · patch interface applies validated copy for supported paths
T021 · done · `uv run pytest core/builder -q` · VillageChat inserted into non-elder views only
T025 · done · `test -f core/agent/capabilities.yaml` · catalog is local YAML, no cloud
T026 · partial · `uv run pytest core/builder -q` · critique pass represented as evaluator/no-op span only
T027 · partial · `uv run pytest core/builder -q` · DailyMed REST lookup implemented; consent call is a Protocol for voice lane
T028 · done · `uv run scripts/build_village.py --description-from data/villages/reyes_family.json --llm off` · quiet-hours decision row cites welcome_call at 108s
