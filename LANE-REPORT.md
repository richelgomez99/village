G001 · done · uv run pytest core/gate -k roundtrip -q · mocked none
G002 · done · uv run pytest core/gate -k say -q · mocked none
G003 · done · uv run pytest core/gate -k "T0 or T1 or T2 or spec_patch or kill_switch" -q · mocked core write/id minting only
G004 · done · uv run pytest core/gate -k "T3 or T4 or T5" -q · mocked core idempotency cache and persisted verification rows
G005 · done · uv run pytest core/gate -k verification -q · mocked core CAS commit only
G006 · done · uv run pytest core/gate -k dose_window -q · mocked dialer/action execution only
G007 · done · uv run pytest core/gate -q · mocked none
LD-1: Gate models stay contract-shaped dict wrappers so Core can pass schema JSON without translation.
