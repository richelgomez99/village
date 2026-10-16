"""Seed any registered village: `python -m core.tools.seed --village <id> [--keep]`.

Villages are listed in data/villages/index.json (spec fixture + data file + optional seeds).
`--keep` seeds this village next to the ones already loaded (when reset_demo supports it).
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json

from core import village
from core.fixtures import reset_demo


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--village", default=None, choices=village.village_ids() or None,
                        help="village id (default: DEMO_VILLAGE_ID / registry default)")
    parser.add_argument("--keep", action="store_true", help="keep other villages already seeded")
    args = parser.parse_args()
    village_id = args.village or village.default_village_id()
    kwargs = {}
    if args.keep and "keep_others" in inspect.signature(reset_demo).parameters:
        kwargs["keep_others"] = True
    print(json.dumps(await reset_demo(village_id, **kwargs), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
