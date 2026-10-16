import pytest


@pytest.fixture(autouse=True)
def _no_operator_voice_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator's .env may carry VILLAGE_TOOL_SECRET (live enforcement); voice tests set their own secret."""
    monkeypatch.delenv("VILLAGE_TOOL_SECRET", raising=False)
    monkeypatch.delenv("ELEVENLABS_WEBHOOK_SECRET", raising=False)
