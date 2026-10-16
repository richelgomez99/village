"""`uv run python -m core.tools.warm`: pre-warm the release lane (Daytona sandbox + Anchor session) when
core.release is merged; otherwise a no-op that says so."""
from __future__ import annotations

import asyncio
import json


async def warm() -> dict:
    try:
        from core.release.service import get_service
    except ImportError:
        return {"release": "absent"}
    try:
        return {"release": await get_service().startup()}
    except Exception as exc:
        return {"release": "failed", "error": type(exc).__name__}


def main() -> None:
    print(json.dumps(asyncio.run(warm()), default=str))


if __name__ == "__main__":
    main()
