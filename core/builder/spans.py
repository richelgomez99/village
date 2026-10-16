from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def span(_name: str, **_attrs: object) -> Iterator[None]:
    yield
