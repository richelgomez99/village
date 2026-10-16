from __future__ import annotations

from .ask import AskAnswer
from .ask import ask as ask_records


async def ask(village_id: str, question: str, author: str | None = None):  # core's @Village hook
    """Chat entry used by core.services (`builder_ask(village_id, text)`): why → cited answer; change → proposal."""
    from .chat_intent import route_chat
    from .llm_port import get_llm

    return await route_chat(village_id, question, author, llm=get_llm(None, "chat.mention"))
from .founding import BuilderRun, FoundingInput, FoundingOptions, found
from .patch import PatchResult, patch

build_spec = found

__all__ = [
    "AskAnswer",
    "BuilderRun",
    "FoundingInput",
    "FoundingOptions",
    "PatchResult",
    "ask",
    "ask_records",
    "build_spec",
    "found",
    "patch",
]
