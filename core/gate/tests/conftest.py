from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORBIDDEN_IMPORTS = ("httpx", "anthropic", "surrealdb")


def pytest_configure() -> None:
    import core.gate  # noqa: F401

    loaded = sorted(name for name in FORBIDDEN_IMPORTS if name in sys.modules)
    if loaded:
        raise AssertionError(f"core.gate imported forbidden module(s): {', '.join(loaded)}")


@pytest.fixture(autouse=True)
def block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_socket(*args, **kwargs):
        raise AssertionError("core.gate tests must not open sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)
