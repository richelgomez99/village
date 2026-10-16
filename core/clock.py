from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


@dataclass
class Clock:
    offset: timedelta = timedelta()

    def now(self) -> datetime:
        return datetime.now(ET) + self.offset

    @property
    def offset_minutes(self) -> int:
        return int(self.offset.total_seconds() // 60)

    def warp(self, *, minutes: int | None = None, to: datetime | None = None, reset: bool = False) -> int:
        if reset:
            self.offset = timedelta()
        elif to is not None:
            self.offset = to.astimezone(ET) - datetime.now(ET)
        elif minutes is not None:
            self.offset += timedelta(minutes=minutes)
        return self.offset_minutes


class FakeClock(Clock):
    def __init__(self, at: datetime):
        super().__init__()
        self._now = at

    def now(self) -> datetime:
        return self._now

    def set(self, at: datetime) -> None:
        self._now = at


clock = Clock()
