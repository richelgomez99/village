from __future__ import annotations

import asyncio
import json

from core.fixtures import reset_demo


async def main() -> None:
    print(json.dumps(await reset_demo("v_reyes"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
