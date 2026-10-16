from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

from .paths import PROMPTS

_CACHE: tuple[float, "PromptTemplate"] | None = None


@dataclass(frozen=True)
class PromptTemplate:
    text: str
    version_id: str
    source: str


def get_builder_prompt(prefer: str = "hub") -> PromptTemplate:
    global _CACHE
    now = time.monotonic()
    if _CACHE and now - _CACHE[0] < 10:
        return _CACHE[1]
    if prefer == "hub":
        try:
            prompt = _fetch_prompt_hub()
        except Exception:
            prompt = _local_prompt()
    else:
        prompt = _local_prompt()
    _CACHE = (now, prompt)
    return prompt


def _fetch_prompt_hub() -> PromptTemplate:
    import arize as ax  # type: ignore

    obj = ax.prompts.get(prompt="village-builder", label="production")
    version = getattr(obj, "version_id", None) or getattr(obj, "id", None) or "production"
    text = getattr(obj, "text", None)
    if text is None and hasattr(obj, "version"):
        text = getattr(obj.version, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Prompt Hub response did not contain string text")
    return PromptTemplate(text=text, version_id=str(version), source="hub")


def _local_prompt() -> PromptTemplate:
    return PromptTemplate(
        text=(PROMPTS / "builder_system.md").read_text(encoding="utf-8"),
        version_id="local",
        source="local",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--prompt", choices=["hub", "local"], default="hub")
    args = parser.parse_args()
    prompt = get_builder_prompt(args.prompt)
    print(f"{prompt.source} {prompt.version_id} {len(prompt.text)}")


if __name__ == "__main__":
    main()
