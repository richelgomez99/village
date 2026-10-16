from __future__ import annotations

import argparse
import asyncio
import json

import websockets

from core.settings import CONTRACT_VERSION


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8787/ws")
    parser.add_argument("--village", default="v_reyes")
    parser.add_argument("--token", default="m_carmen")
    args = parser.parse_args()

    async with websockets.connect(f"{args.url}?village={args.village}&m={args.token}") as ws:
        await ws.send(json.dumps({
            "type": "hello",
            "contract_version": CONTRACT_VERSION,
            "village": args.village,
            "member_id": args.token,
        }))
        async for message in ws:
            print(message, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
