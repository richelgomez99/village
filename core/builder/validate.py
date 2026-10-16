from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .paths import SCHEMAS

LAYOUT_TYPES = {"Screen", "Stack", "Header", "Text"}
PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s().]{7,}\d)")
ACCOUNT_RE = re.compile(r"\b(?:account|routing|pin|ssn|social security|medicare)\b", re.I)
DOSE_ADVICE_RE = re.compile(r"\b(?:safe to take|skip|double|take extra|too much|increase dose|decrease dose)\b", re.I)


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_schema_registry() -> Registry:
    schemas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SCHEMAS.glob("*.schema.json"))]
    return Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)


def _schema_errors(spec: dict[str, Any]) -> list[str]:
    schema = {"$ref": "https://village.contracts/v1/village_spec.schema.json"}
    validator = Draft202012Validator(schema, registry=_load_schema_registry(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path))
    return [f"schema {'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in errors[:12]]


def validate_spec(spec: dict[str, Any]) -> ValidationReport:
    errors = _schema_errors(spec)
    warnings: list[str] = []
    if not errors:
        errors.extend(_invariant_errors(spec))
    warnings.extend(_safety_warnings(spec))
    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)


def assert_valid_spec(spec: dict[str, Any]) -> None:
    report = validate_spec(spec)
    if not report.ok:
        raise ValueError(format_errors(report))


def format_errors(report: ValidationReport, limit: int = 12) -> str:
    return "\n".join(f"{idx + 1}. {err}" for idx, err in enumerate(report.errors[:limit]))


def _invariant_errors(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bp = spec["blueprint"]
    people = {p["id"]: p for p in bp["people"]}
    need_ids = {n["id"] for n in bp["needs"]} | {"n_safety"}
    text = bp["description"]["text"]

    for need in bp["needs"]:
        span = need.get("source_span")
        if span and not (0 <= span["start"] < span["end"] <= len(text)):
            errors.append(f"I5 need {need['id']} source_span out of range")

    if set(spec["channels"]) != set(people):
        errors.append("I1 channels keys must equal blueprint people ids")
    for pid, person in people.items():
        view_name = person.get("view")
        if view_name is not None and view_name not in spec["views"]:
            errors.append(f"I1 {pid}.view {view_name} missing from views")
        for channel in spec["channels"].get(pid, []):
            if channel.startswith("app:") and channel[4:] != view_name:
                errors.append(f"I1 {pid} channel {channel} does not match view {view_name}")

    for role, view in spec["views"].items():
        els = view["elements"]
        if view.get("root") != "s" or els.get("s", {}).get("type") != "Screen":
            errors.append(f"I2 view {role} root s must be a Screen")
            continue
        refs: dict[str, int] = {}
        for eid, element in els.items():
            for child in element.get("children", []):
                if child not in els:
                    errors.append(f"I2 view {role} element {eid} references missing child {child}")
                refs[child] = refs.get(child, 0) + 1
        for eid in els:
            if eid != "s" and refs.get(eid, 0) != 1:
                errors.append(f"I2 view {role} element {eid} referenced {refs.get(eid, 0)}x")
        _visit_graph("s", els, set(), set(), role, errors)

        needs_served = view.get("needs_served", {})
        for eid, element in els.items():
            if element["type"] not in LAYOUT_TYPES and eid not in needs_served:
                errors.append(f"I3 view {role} {eid} ({element['type']}) missing needs_served")
            for need in needs_served.get(eid, []):
                if need not in need_ids:
                    errors.append(f"I3 view {role} {eid} serves unknown need {need}")
            props = element.get("props", {})
            for key in ("subject", "member_id"):
                if isinstance(props.get(key), str) and props[key] not in people:
                    errors.append(f"I5 view {role} {eid}.{key} unknown member {props[key]}")
            for mid in props.get("choices_member_ids", []) + props.get("subjects", []):
                if mid not in people:
                    errors.append(f"I5 view {role} {eid} unknown member {mid}")

        chat_ids = [eid for eid, element in els.items() if element["type"] == "VillageChat"]
        if len(chat_ids) > 1:
            errors.append(f"I8 view {role} has more than one VillageChat")
        if view["theme"] == "elder":
            if chat_ids:
                errors.append(f"I8 elder view {role} must not contain VillageChat")
            buttons = [element for element in els.values() if element["type"] == "BigButton"]
            if len(buttons) > 3:
                errors.append(f"I4 elder view {role} has more than 3 BigButtons")
            if not any(e["type"] == "ContactCard" and e["props"].get("kind") == "emergency" for e in els.values()):
                errors.append(f"I4 elder view {role} lacks 911 ContactCard")
            for eid, element in els.items():
                props = element.get("props", {})
                if props.get("show_med_names"):
                    errors.append(f"I4 elder view {role} {eid} shows med names")
                if element["type"] == "BigButton" and props.get("tone") == "danger" and not props.get("confirm"):
                    errors.append(f"I4 elder danger button {eid} must require confirm")

    for area in bp["life_areas"]:
        for need_id in area["need_ids"]:
            if need_id not in need_ids:
                errors.append(f"I5 life area {area['id']} references unknown need {need_id}")
        for module in area.get("modules", []):
            role, _, eid = module.partition(":")
            if role in spec["views"] and eid not in spec["views"][role]["elements"]:
                errors.append(f"I5 life area {area['id']} module {module} not found")
    covered = {need_id for area in bp["life_areas"] for need_id in area["need_ids"]}
    for need in bp["needs"]:
        if need["id"] not in covered:
            errors.append(f"I5 need {need['id']} not covered by a life area")
    return errors


def _visit_graph(eid: str, els: dict[str, Any], visiting: set[str], seen: set[str], role: str, errors: list[str]) -> None:
    if eid in visiting:
        errors.append(f"I2 view {role} contains a cycle at {eid}")
        return
    if eid in seen or eid not in els:
        return
    visiting.add(eid)
    for child in els[eid].get("children", []):
        _visit_graph(child, els, visiting, seen, role, errors)
    visiting.remove(eid)
    seen.add(eid)


def _safety_warnings(spec: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    family_word = ""
    for printable in spec.get("printables", []):
        if printable.get("kind") == "fridge_card":
            family_word = str(printable.get("family_word", ""))
    for role, view in spec.get("views", {}).items():
        for eid, element in view.get("elements", {}).items():
            for value in element.get("props", {}).values():
                if not isinstance(value, str):
                    continue
                if family_word and family_word in value:
                    warnings.append(f"safety view {role} {eid} exposes family word")
                if DOSE_ADVICE_RE.search(value):
                    warnings.append(f"safety view {role} {eid} may contain dose advice")
                if PHONE_RE.search(value) and value not in {"911", "988", "18002221222"}:
                    warnings.append(f"safety view {role} {eid} contains a phone-like string")
                if ACCOUNT_RE.search(value):
                    warnings.append(f"safety view {role} {eid} contains account-sensitive wording")
    return warnings
