"""The Builder fixes its own failing build (D23 #2).

Input: the failing floor tests + the bundle theme. Output: a patched theme.
Model on: the Builder (LLM) reads the failure and proposes a token patch; the patch is
checked in code (only tone fg/bg tokens, contrast recomputed) before it is accepted.
Model off (or a bad patch): deterministic floor autofix (failing tone fg → floor ink)."""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from core.release import obs
from core.release.contrast import ratio
from core.release.floor_tests import FLOOR

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass
class RepairResult:
    theme: dict[str, Any]
    changed: list[str] = field(default_factory=list)
    mode: str = "deterministic"  # llm | deterministic
    summary: str = ""
    llm_error: str | None = None


def failing_tones(theme: dict[str, Any], need: float = FLOOR["elder_contrast"]) -> list[str]:
    return [name for name, t in theme["tones"].items() if ratio(t["fg"], t["bg"]) < need]


def deterministic(theme: dict[str, Any]) -> RepairResult:
    th = copy.deepcopy(theme)
    changed = []
    for name in failing_tones(th):
        th["tones"][name]["fg"] = th["floor"]["ink"]
        changed.append(f"tones.{name}.fg")
    tones = ", ".join(c.split(".")[1] for c in changed) or "none"
    return RepairResult(th, changed, "deterministic", f"elder {tones} tone mapped to floor ink")


_PROMPT = """You are the Builder of Village. A release of the family app failed its accessibility floor tests in the Daytona sandbox.
Failing tests:
{failures}

Current theme tones (fg = text color, bg = button surface). Floor ink is {ink}; elder text needs contrast >= 7:1.
{tones}

Fix the theme with the smallest change. Do not change safety colors (bar) or bg. Reply with ONLY JSON:
{{"patch": [{{"path": "tones.<tone>.fg", "value": "#RRGGBB"}}], "why": "<one short sentence>"}}"""


def _apply(theme: dict[str, Any], patch: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    th = copy.deepcopy(theme)
    changed = []
    for op in patch:
        path, value = str(op.get("path", "")), str(op.get("value", ""))
        m = re.fullmatch(r"tones\.([a-z]+)\.fg", path)
        if not m or m.group(1) not in th["tones"] or not HEX.match(value):
            raise ValueError(f"patch not allowed: {path}={value}")
        th["tones"][m.group(1)]["fg"] = value.upper()
        changed.append(path)
    return th, changed


def llm_repair(theme: dict[str, Any], failures: list[str], client: Any, *, village: str | None = None) -> RepairResult:
    prompt = _PROMPT.format(failures="\n".join(failures[:5]), ink=theme["floor"]["ink"], tones=json.dumps(theme["tones"]))
    model = getattr(client, "village_model", None) or "claude-haiku-4-5"
    with obs.span("builder.repair_theme", "LLM", village=village, node="llm_repair", parent_node="builder",
                  input=prompt, **{"llm.model_name": model}) as sp:
        msg = client.messages.create(model=model, max_tokens=300, messages=[{"role": "user", "content": prompt}])
        text = "".join(getattr(b, "text", "") for b in msg.content)
        obs.finish(sp, True, output=text)
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0) if m else text)
    th, changed = _apply(theme, data.get("patch") or [])
    if failing_tones(th):
        raise ValueError(f"LLM patch still fails contrast: {failing_tones(th)}")
    why = str(data.get("why", ""))[:120]
    return RepairResult(th, changed, "llm", (why or f"{', '.join(changed)} patched")[:200])


def repair(theme: dict[str, Any], failures: list[str], *, llm: Callable[[str], Any] | None = None,
           village: str | None = None) -> RepairResult:
    if llm is not None:
        try:
            client = llm("builder")
            return llm_repair(theme, failures, client, village=village)
        except Exception as exc:  # model off, Bedrock error, or a bad patch → deterministic floor fix
            res = deterministic(theme)
            res.llm_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            return res
    return deterministic(theme)
