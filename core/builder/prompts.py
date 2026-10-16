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
    name: str = "village-builder"


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


HUB_NAME = "village-builder"
HUB_LABEL = "production"


def _env(key: str) -> str:
    import os

    if os.getenv(key):
        return os.environ[key]
    env = PROMPTS.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return ""


def _fetch_prompt_hub() -> PromptTemplate:
    """Arize Prompt Hub (`village-builder`, label `production`), arize SDK v8 (lazy import)."""
    from arize import ArizeClient  # type: ignore

    api_key, space = _env("ARIZE_API_KEY"), _env("ARIZE_SPACE_ID")
    if not api_key or not space:
        raise RuntimeError("ARIZE_API_KEY / ARIZE_SPACE_ID missing")
    got = ArizeClient(api_key=api_key).prompts.get(prompt=HUB_NAME, space=space, label=HUB_LABEL)
    version = getattr(got, "version", got)
    msgs = getattr(version, "messages", None) or []
    text = next((getattr(m, "content", None) for m in msgs if str(getattr(m, "role", "")).upper().endswith("SYSTEM")), None) or (getattr(msgs[0], "content", None) if msgs else None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Prompt Hub response did not contain a system message")
    return PromptTemplate(text=text, version_id=str(getattr(version, "id", HUB_LABEL)), source="hub")


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
