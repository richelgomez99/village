import os

import pytest

# Offline by default: model off, tracing no-op, no Arize keys.
os.environ["VILLAGE_LLM"] = "off"
os.environ["VILLAGE_TRACING"] = "off"
for _k in ("ARIZE_SPACE_ID", "ARIZE_API_KEY"):
    os.environ.pop(_k, None)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("VILLAGE_LLM", "off")
    monkeypatch.setenv("VILLAGE_TRACING", "off")
    monkeypatch.delenv("ARIZE_SPACE_ID", raising=False)
    monkeypatch.delenv("ARIZE_API_KEY", raising=False)
    try:
        from core.settings import get_settings

        get_settings.cache_clear()
    except Exception:
        pass
    yield
