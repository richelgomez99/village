from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import PROMPTS

TOOL_FENCE_RE = re.compile(r"## Tool: `(?P<name>[a-z_]+)`.*?```json\s*(?P<body>\{.*?\})\s*```", re.S)


def _require_closed_schema(schema: dict[str, Any], label: str) -> None:
    if schema.get("additionalProperties") is not False:
        raise ValueError(f"{label} must set additionalProperties:false")


def prompt_tool_schemas(prompt_path: Path | None = None) -> dict[str, dict[str, Any]]:
    text = (prompt_path or PROMPTS / "builder_system.md").read_text(encoding="utf-8")
    tools: dict[str, dict[str, Any]] = {}
    for match in TOOL_FENCE_RE.finditer(text):
        body = json.loads(match.group("body"))
        name = body["name"]
        if name != match.group("name"):
            raise ValueError(f"tool heading {match.group('name')} != schema {name}")
        _require_closed_schema(body["input_schema"], name)
        tools[name] = body
    missing = {"render_app", "patch_app"} - set(tools)
    if missing:
        raise ValueError(f"missing prompt tools: {sorted(missing)}")
    return tools


def extract_blueprint_schema() -> dict[str, Any]:
    return {
        "name": "extract_blueprint",
        "description": "Extract the village blueprint from a founding description and call exactly once.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "people", "needs", "life_areas", "rules", "questions"],
            "properties": {
                "kind": {"enum": ["care", "block"]},
                "people": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "name", "role", "view", "relation", "reason"],
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "view": {"type": ["string", "null"]},
                            "relation": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                    },
                },
                "needs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "text", "source_span"],
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "source_span": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["start", "end"],
                                "properties": {"start": {"type": "integer"}, "end": {"type": "integer"}},
                            },
                        },
                    },
                },
                "life_areas": {"type": "array", "items": {"type": "string"}},
                "rules": {"type": "array", "items": {"type": "string"}},
                "questions": {"type": "array", "maxItems": 2, "items": {"type": "string"}},
            },
        },
    }


def cite_answer_schema() -> dict[str, Any]:
    return {
        "name": "cite_answer",
        "description": "Answer a why question using only supplied material and cite existing ids.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["answer", "citations"],
            "properties": {
                "answer": {"type": "string", "maxLength": 1200},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "kind"],
                        "properties": {
                            "id": {"type": "string"},
                            "kind": {"enum": ["decision", "fact", "event"]},
                            "label": {"type": "string"},
                        },
                    },
                },
            },
        },
    }


def classify_intent_schema() -> dict[str, Any]:
    return {
        "name": "classify_intent",
        "description": "Classify an @Village message.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["intent", "reason"],
            "properties": {
                "intent": {"enum": ["why", "change", "other"]},
                "reason": {"type": "string", "maxLength": 200},
            },
        },
    }


def all_tools() -> dict[str, dict[str, Any]]:
    tools = prompt_tool_schemas()
    tools["extract_blueprint"] = extract_blueprint_schema()
    tools["cite_answer"] = cite_answer_schema()
    tools["classify_intent"] = classify_intent_schema()
    return deepcopy(tools)
