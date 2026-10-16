"""Pre-warm: one Daytona sandbox (template + node_modules installed) and one Anchor session,
kept alive by a heartbeat. `uv run --with daytona --with anchorbrowser python -m core.release.warm`
prints the sandbox id to export as RELEASE_SANDBOX_ID so Core reuses it."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from core.release.anchor_qa import AnchorQA
from core.release.daytona_svc import DaytonaBuilder


class WarmPool:
    def __init__(self, daytona: DaytonaBuilder | None = None, anchor: AnchorQA | None = None) -> None:
        self.daytona = daytona or DaytonaBuilder()
        self.anchor = anchor or AnchorQA(keep_session=True)
        self.status: dict[str, Any] = {"sandbox": "miss", "anchor": "miss"}
        self._task: asyncio.Task[None] | None = None

    async def prewarm(self, anchor: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        sb = await self.daytona.sandbox()
        timings = await self.daytona.prepare()
        self.status.update(sandbox="ready", sandbox_id=sb.id, sandbox_ms=int((time.perf_counter() - t0) * 1000), **timings)
        if anchor:
            try:
                info = await self.anchor.prewarm()
                self.status.update(anchor="ready", anchor_ms=self.anchor.last_timings.get("anchor_create"), anchor_session_id=info["session_id"])
            except Exception as exc:
                self.status.update(anchor="miss", anchor_error=f"{type(exc).__name__}")
        return dict(self.status)

    def start_heartbeat(self, every_s: float = 240) -> None:
        async def beat() -> None:
            while True:
                await asyncio.sleep(every_s)
                await self.daytona.keepalive()

        self._task = asyncio.create_task(beat())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self.anchor.close()
        await self.daytona.close(delete=False)


async def _main() -> None:
    from dotenv import load_dotenv

    load_dotenv(".env")
    pool = WarmPool()
    st = await pool.prewarm(anchor=False)
    print({k: v for k, v in st.items()})
    print(f"export RELEASE_SANDBOX_ID={st['sandbox_id']}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())
