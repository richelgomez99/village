from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import PROMPTS

TOOL_FENCE_RE = re.compile(r"## Tool: `(?P<name>[a-z_]+)`.*?```json\s*(?P<body>\{.*?\})\s*```", re.S)
TOOL_NAMES = {"extract_blueprint", "render_app", "patch_app", "cite_answer", "classify_intent"}
ROLE_ENUM = [
    "coordinator",
    "care_recipient",
    "caregiver",
    "professional_caregiver",
    "resident",
    "volunteer",
    "business",
    "peer",
]
VIEW_ENUM = ["elder", "coordinator", "helper", "resident", "volunteer"]
NEED_DOMAINS = ["medication", "scheduling", "health_observation", "safety", "money", "information", "resources", "logistics", "social"]
LIFE_AREAS = ["health", "money", "people", "home", "daily_living", "information"]
BLUEPRINT_RULES = [
    "double_dose_guard",
    "no_dose_advice",
    "missed_dose_ladder",
    "emergency_911_first",
    "consent_before_calls",
    "ai_disclosure_family_word",
    "money_verify_with_member",
    "money_never_moves",
    "money_default_dont_send",
    "quiet_hours",
    "rumor_check",
    "medical_priority_matching",
    "address_privacy",
]


def _require_closed_schema(schema: dict[str, Any], label: str, path: str = "input_schema") -> None:
    """Require fixed-shape objects to be closed while allowing map-like objects."""
    if (schema.get("type") == "object" or "properties" in schema) and "properties" in schema:
        if schema.get("additionalProperties") is not False:
            raise ValueError(f"{label} {path} must set additionalProperties:false")
    for key in ("properties", "$defs"):
        for name, child in schema.get(key, {}).items():
            if isinstance(child, dict):
                _require_closed_schema(child, label, f"{path}/{key}/{name}")
    for key in ("items", "additionalProperties"):
        child = schema.get(key)
        if isinstance(child, dict):
            _require_closed_schema(child, label, f"{path}/{key}")
    for key in ("anyOf", "oneOf", "allOf"):
        for idx, child in enumerate(schema.get(key, [])):
            if isinstance(child, dict):
                _require_closed_schema(child, label, f"{path}/{key}/{idx}")


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
    source_span = {
        "type": "object",
        "additionalProperties": False,
        "required": ["start", "end"],
        "properties": {"start": {"type": "integer", "minimum": 0}, "end": {"type": "integer", "minimum": 1}},
    }
    return {
        "name": "extract_blueprint",
        "description": "Extract the fast founding blueprint from a spoken description. Call exactly once before rendering views.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "people", "edges", "needs", "rules", "life_areas", "questions"],
            "properties": {
                "kind": {"enum": ["care", "block"]},
                "people": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 24,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "name", "relation", "role", "view", "profile", "consent", "reason"],
                        "properties": {
                            "id": {"type": "string", "pattern": "^[mb]_[a-z0-9_]+$"},
                            "name": {"type": "string", "minLength": 1, "maxLength": 80},
                            "short_name": {"type": "string", "maxLength": 40},
                            "relation": {"type": "string", "maxLength": 80},
                            "role": {"enum": ROLE_ENUM},
                            "view": {"anyOf": [{"enum": VIEW_ENUM}, {"type": "null"}]},
                            "phone": {"type": "string", "pattern": "^\\+[1-9][0-9]{7,14}$"},
                            "profile": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["lang", "memory", "tech_comfort", "preferred_channels"],
                                "properties": {
                                    "lang": {"type": "string", "pattern": "^[a-z]{2}(-[A-Za-z0-9]{2,8})?$"},
                                    "memory": {"enum": ["typical", "mild_lapses", "significant", "unknown"]},
                                    "tech_comfort": {"enum": ["phone", "app", "both", "unknown"]},
                                    "preferred_channels": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "enum": [
                                                "phone_line",
                                                "outbound_calls",
                                                "app",
                                                "fridge_card",
                                                "sms",
                                                "paper",
                                            ]
                                        },
                                    },
                                    "quiet_hours": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]-[0-2][0-9]:[0-5][0-9]$"},
                                    "evidence": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "required": ["field", "source_span"],
                                            "properties": {
                                                "field": {"type": "string"},
                                                "source_span": source_span,
                                                "quote": {"type": "string", "maxLength": 160},
                                            },
                                        },
                                    },
                                },
                            },
                            "consent": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["ai_calls", "app_prompts"],
                                "properties": {
                                    "ai_calls": {"type": ["boolean", "null"]},
                                    "app_prompts": {"type": ["boolean", "null"]},
                                    "money_verifier": {"type": "boolean"},
                                },
                            },
                            "reason": {"type": "string", "maxLength": 200},
                        },
                    },
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["from", "to", "kind", "label"],
                        "properties": {
                            "from": {"type": "string", "pattern": "^[mb]_[a-z0-9_]+$"},
                            "to": {"type": "string", "pattern": "^[mb]_[a-z0-9_]+$"},
                            "kind": {"enum": ["cares_for", "on_duty", "backup", "trusted_contact", "helps", "neighbor", "coordinates"]},
                            "label": {"type": "string", "maxLength": 60},
                        },
                    },
                },
                "needs": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "text", "priority", "domain", "life_area", "source_span"],
                        "properties": {
                            "id": {"type": "string", "pattern": "^n_[a-z0-9_]+$"},
                            "text": {"type": "string", "maxLength": 160},
                            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                            "domain": {"enum": NEED_DOMAINS},
                            "life_area": {"enum": LIFE_AREAS},
                            "subject_member_ids": {"type": "array", "items": {"type": "string", "pattern": "^[mb]_[a-z0-9_]+$"}},
                            "source_span": {"anyOf": [source_span, {"type": "null"}]},
                        },
                    },
                },
                "rules": {"type": "array", "uniqueItems": True, "items": {"enum": BLUEPRINT_RULES}},
                "life_areas": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "label", "need_ids", "rules"],
                        "properties": {
                            "id": {"enum": LIFE_AREAS},
                            "label": {"type": "string", "maxLength": 40},
                            "need_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^n_[a-z0-9_]+$"}},
                            "rules": {"type": "array", "items": {"type": "string"}},
                            "trusted_contacts": {"type": "array", "items": {"type": "string", "pattern": "^[mb]_[a-z0-9_]+$"}},
                        },
                    },
                },
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
    unknown = set(tools) - TOOL_NAMES
    missing = TOOL_NAMES - set(tools)
    if unknown or missing:
        raise ValueError(f"tool registry mismatch missing={sorted(missing)} unknown={sorted(unknown)}")
    return deepcopy(tools)
