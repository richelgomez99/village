from __future__ import annotations

import argparse
import asyncio
import json

import websockets

from core import village
from core.settings import CONTRACT_VERSION


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8787/ws")
    parser.add_argument("--village", default=None, help="village id (default: DEMO_VILLAGE_ID / registry default)")
    parser.add_argument("--token", default=None, help="member token (default: the village's care recipient or coordinator)")
    args = parser.parse_args()
    args.village = args.village or village.default_village_id()
    args.token = args.token or village.care_recipient_id(args.village) or village.coordinator_id(args.village) or "control"

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
