from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LLMUnavailable(RuntimeError):
    pass


@dataclass
class FakeLLM:
    responses: list[dict[str, Any]]

    async def messages_create(self, **_: Any) -> dict[str, Any]:
        if not self.responses:
            raise LLMUnavailable("fake LLM has no recorded responses")
        return self.responses.pop(0)


def llm(role: str = "sonnet") -> Any:
    try:
        from core.llm import llm as core_llm  # type: ignore

        return core_llm(role)
    except Exception as exc:
        raise LLMUnavailable(str(exc)) from exc
