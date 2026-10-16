"""Voice routes grafted onto Core through core.voice.init_hook.app (core/app.py grafts its `/hooks/` routes).

- `POST /hooks/elevenlabs/tools/{tool}`: ElevenLabs tool webhooks that Core's `/tools/{name}` does not serve
  (`create_village`, `submit_answer`, `screen_caller`); every other tool name is delegated to Core services.
  `X-Village-Secret` is required when `VILLAGE_TOOL_SECRET` is set.
- `GET /voice/token?agent=setup` (contract path; needs "/voice/" in core/app.py's graft prefixes) and its grafted alias
  `GET /hooks/elevenlabs/token`: a WebRTC conversation token for the web founding mic (`@elevenlabs/react`).
- `POST /hooks/elevenlabs/captions/{conversation_id}`: start live captions for a conversation by hand.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from core.voice.secret import require_secret

router = APIRouter(tags=["voice"])

AGENT_ENV = {
    "setup": ("ELEVENLABS_SETUP_AGENT_ID", "ELEVENLABS_AGENT_SETUP_ID"),
    "mom-line": ("ELEVENLABS_AGENT_ID",),
    "village-caller": ("ELEVENLABS_AGENT_CALLER_ID", "ELEVENLABS_CALLER_AGENT_ID"),
}


def agent_id_for(agent: str) -> str:
    for name in AGENT_ENV.get(agent, ()):
        if os.getenv(name):
            return os.environ[name]
    return ""


@router.post("/hooks/elevenlabs/tools/{tool_name}")
async def hook_tool(
    tool_name: str,
    request: Request,
    x_village_secret: str | None = Header(default=None),
    x_village_variant: str | None = Header(default=None),
) -> dict[str, Any]:
    require_secret(x_village_secret)
    from core.voice.tools import handler

    return await handler.handle(tool_name, await request.json(), variant=x_village_variant)


async def conversation_token(agent: str = "setup", fetch: Any | None = None) -> dict[str, Any]:
    if agent not in AGENT_ENV:
        raise HTTPException(status_code=404, detail="unknown agent")
    agent_id = agent_id_for(agent)
    if not agent_id or not os.getenv("ELEVENLABS_API_KEY"):
        raise HTTPException(status_code=503, detail="voice agent not configured")
    if fetch is None:
        import httpx

        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://api.elevenlabs.io/v1/convai/conversation/token",
                params={"agent_id": agent_id},
                headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            )
            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail="token request failed")
            body = response.json()
    else:
        body = await fetch(agent_id)
    return {"token": body.get("token"), "agent": agent, "agent_id": agent_id}


@router.get("/voice/token")
async def voice_token(agent: str = "setup") -> dict[str, Any]:
    return await conversation_token(agent)


@router.get("/hooks/elevenlabs/token")
async def voice_token_alias(agent: str = "setup") -> dict[str, Any]:
    return await conversation_token(agent)


@router.post("/hooks/elevenlabs/captions/{conversation_id}")
async def start_captions(conversation_id: str, request: Request, x_village_secret: str | None = Header(default=None)) -> dict[str, Any]:
    require_secret(x_village_secret)
    from core import village
    from core.voice import captions

    body = await request.json() if (await request.body()) else {}
    vid = body.get("village_id") or village.default_village_id()
    started = captions.start_poller(conversation_id, vid, {"user": body.get("speaker") or "Caller", "agent": "Village"})
    return {"conversation_id": conversation_id, "village_id": vid, "polling": started}
