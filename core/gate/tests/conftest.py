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
    """Model-off guard: importing core.gate in a FRESH interpreter must not pull in httpx/anthropic/surrealdb.
    (Checked in a subprocess so other test suites collected in the same session cannot trip it.)"""
    import subprocess, sys as _sys
    code = (
        "import sys; import core.gate; "
        f"loaded=[n for n in {FORBIDDEN_IMPORTS!r} if n in sys.modules]; "
        "sys.exit(1 if loaded else 0); "
    )
    proc = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("core.gate imported forbidden module(s) in a fresh interpreter: " + (proc.stderr or "").strip()[-300:] + " (one of " + ", ".join(FORBIDDEN_IMPORTS) + ")")


@pytest.fixture(autouse=True)
def block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_socket(*args, **kwargs):
        raise AssertionError("core.gate tests must not open sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)
