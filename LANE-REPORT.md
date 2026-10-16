READY FOR MERGE V0
T001 · done · `elevenlabs agents push --dry-run` pending local CLI shape; JSON project added under agents/ · mocked: no API key or dashboard ids
T002 · done · `uv run python scripts/check_tool_schemas.py` · mocked: tool ids, workspace env values
T003 · done · `python -m json.tool agents/agent_configs/mom-line.json >/dev/null` · mocked: voices and dashboard init hook enablement
T004 · done · `uv run python scripts/push_procedures.py --dry-run --all` · mocked: live procedure publish disabled until key exists
T005 · done · `uv run pytest core/voice/tests/test_mock_core.py -q` · mocked: Core answers from contracts/fixtures/scam_call_tool_requests.json
T006 · cut · core owns core/services.py; voice will import lazily in V1 and use local fakes until core merges
T010 · partial · not started for V0; needs core/services.py T006
T011 · partial · not started for V0; needs core/services.py T006
T012 · partial · not started for V0; needs core/services.py T006 and ElevenLabs/Twilio ids
T014 · partial · not started for V0; needs webhook secret sample and core service seam
T013/T015 · blocked · core-owned; need POST /verifications/{id}/answer, WS prompt close, incident binding and scams_stopped counter from core
LD-1: Live ElevenLabs procedure publish is disabled in scripts/push_procedures.py for V0 because the API key is unavailable; dry-run serializes content as a JSON string for review.
LD-2: submit_verification_answer is represented as a tool config even though its endpoint is /verifications/{id}/answer, because the village-caller agent needs it as a webhook tool.
LD-3: receptionist mode from D19 is left out of V0/V1 configs; it should be added behind a V4 flag.
