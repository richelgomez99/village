from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from typing import Any


class MemoryDB:
    def __init__(self) -> None:
        self.villages: dict[str, dict[str, Any]] = {}
        self.members: dict[str, dict[str, Any]] = {}
        self.views: dict[tuple[str, str], dict[str, Any]] = {}
        self.specs: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.prescriptions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.subscribers: list[asyncio.Queue[tuple[str, dict[str, Any]]]] = []

    async def reset(self) -> None:
        self.__init__()

    async def create_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append(event)
        await self.publish("event", event)
        return event

    async def create_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        self.decisions.append(decision)
        await self.publish("decision", decision)
        return decision

    async def create_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self.messages.append(message)
        await self.publish("message", message)
        return message

    async def publish(self, table: str, row: dict[str, Any]) -> None:
        for queue in list(self.subscribers):
            await queue.put((table, row))

    def subscribe(self) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    async def cas_update(self, table: str, key: str, version: int, values: dict[str, Any]) -> list[dict[str, Any]]:
        del table, key, version, values
        return []


db = MemoryDB()


async def apply_schema() -> str:
    return "schema OK (memory)"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    if args.apply:
        print(await apply_schema())
    elif args.local:
        print("memory fallback is in-process; external surreal start skipped")


if __name__ == "__main__":
    asyncio.run(main())
