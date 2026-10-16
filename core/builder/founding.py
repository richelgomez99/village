from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .blueprint import stream_blueprint
from .decisions import builder_decision
from .render import RoleResult, render_spec
from .services_stub import MemoryServices
from .validate import assert_valid_spec


@dataclass
class FoundingInput:
    description: str
    language: str = "en"
    channel: str = "text"
    members: list[dict[str, Any]] = field(default_factory=list)
    needs: list[dict[str, Any]] = field(default_factory=list)
    kind: str = "care"


@dataclass
class FoundingOptions:
    mode: str = "fixture"
    prompt: str = "local"
    strict: bool = False
    llm: str = "off"


@dataclass
class BuilderRun:
    village_id: str
    spec: dict[str, Any]
    roles: dict[str, RoleResult]
    blueprint: Any
    total_ms: int
    trace_id: str


async def found(
    input: FoundingInput,
    *,
    village_id: str = "v_reyes",
    services: Any | None = None,
    options: FoundingOptions | None = None,
) -> BuilderRun:
    svc = services or MemoryServices()
    opts = options or FoundingOptions()
    t0 = time.perf_counter()
    kind = input.kind or ("block" if "blackout" in input.description.lower() else "care")
    blueprint = await stream_blueprint(input.description, village_id, svc, kind)
    spec, roles = await render_spec(input.description, kind, village_id, mode=opts.mode)
    assert_valid_spec(spec)
    trace_id = f"trace_{village_id}"
    await svc.record_decision(builder_decision(village_id, "prompt local used for builder run", kind="note"))
    for person in spec["blueprint"]["people"]:
        channels = ", ".join(spec["channels"].get(person["id"], []))
        await svc.record_decision(
            builder_decision(
                village_id,
                f"{person['name']}: {person['view'] or 'phone-only'} through {channels}. {person.get('notes', '')}"[:380],
                refs=[{"kind": "member", "id": person["id"]}],
            )
        )
    quiet = next((p for p in spec["blueprint"]["people"] if p["id"] == "m_carmen"), {}).get("profile", {}).get("quiet_hours")
    if quiet:
        await svc.record_decision(
            builder_decision(
                village_id,
                "Carmen quiet hours: after 9:30 PM, no calls. Source: welcome_call at 108s.",
                refs=[{"kind": "member", "id": "m_carmen"}],
            )
        )
    await svc.store_spec(village_id, spec, status="draft")
    return BuilderRun(village_id=village_id, spec=spec, roles=roles, blueprint=blueprint, total_ms=int((time.perf_counter() - t0) * 1000), trace_id=trace_id)
