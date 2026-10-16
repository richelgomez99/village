READY FOR MERGE V0
G001 · done · uv run pytest core/gate -k roundtrip -q · mocked none
G002 · done · uv run pytest core/gate -k say -q · mocked none
G003 · done · uv run pytest core/gate -k "T0 or T1 or T2 or spec_patch or kill_switch" -q · mocked core write/id minting only
G004 · done · uv run pytest core/gate -k "T3 or T4 or T5" -q · mocked core idempotency cache and persisted verification rows
G005 · done · uv run pytest core/gate -k verification -q · mocked core CAS commit only
G006 · done · uv run pytest core/gate -k dose_window -q · mocked dialer/action execution only
G007 · done · uv run pytest core/gate -q · mocked none
LD-1: Gate models stay contract-shaped dict wrappers so Core can pass schema JSON without translation.

## gate
READY FOR MERGE V1
G008 · done · deadline-during-await closes TIMED_OUT; consent-revoked dial is no-op; T32/T33 and ignored terminal answer covered.
G009 · done · tick{dose_window} returns reminder/escalation decisions with event_draft-valid writes; T04 uncertain prior dose escalates with dose_uncertain.
G010 · done · say_vars is always present; deciding R-id remains rules_fired[0] (T28 asserts R-DOUBLE).
Audit · T01-T51 have gate test status; deferred to later lanes: T21-T26 rumor/resource matching source-verification cases.
Verify · uv run pytest core/gate -q · 110 passed offline.
LD-2: Scheduler-facing dose ticks use R-MISSED as the gate rule and policy IDs P-ME-01/P-ME-02 for reminder/escalation attribution.
LD-3: T21-T26 are tracked but deferred because rumor verification/resource matching are not in G008-G010 and require non-gate source/matching services.
