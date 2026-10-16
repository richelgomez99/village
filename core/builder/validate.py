"""VillageSpec validation: pydantic mirror of the contract + invariants + safety scan.

Three layers, each producing named errors:
1. ``schema`` / ``model``: JSON Schema (the contract oracle) and a pydantic mirror built from
   ``contracts/schemas/village_spec.schema.json``. Elements are a discriminated union on
   ``type``; every catalog type gets its own props model generated from ``props_<Type>``.
   New catalog types (contracts 1.2.0: RefillCard, TonightCard, ...) are picked up from the
   schema's ``catalog_type`` enum automatically; a type the contract does not have yet can be
   added with ONE entry in ``EXTRA_CATALOG``.
2. ``I1``..``I8``: the cross-field invariants of contracts/README.md.
3. ``S1``..``S3``: safety text scan over views (family word, medical advice, money/account asks).
"""
from __future__ import annotations

import json
import keyword
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any, Literal, Optional, Union

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ConfigDict, Discriminator, Field, StrictBool, Tag, ValidationError, create_model
from referencing import Registry, Resource

from .paths import SCHEMAS

LAYOUT_TYPES = {"Screen", "Stack", "Header", "Text"}
CONTAINER_TYPES = {"Screen", "Stack"}
SPEC_FILE = "village_spec.schema.json"

# One entry per catalog type the contract does not carry yet: name -> props JSON Schema.
EXTRA_CATALOG: dict[str, dict[str, Any]] = {}

PUBLIC_NUMBERS = {"911", "988", "18002221222", "1-800-222-1222"}
PHONE_RE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
DOSE_ADVICE_RE = re.compile(
    r"\b(safe to take|it'?s (fine|ok) to take|skip (it|the|your)|take (an )?extra|double (up|the dose)|"
    r"too much|increase (the |your )?dose|decrease (the |your )?dose|\d+\s?mg|tome otra|puede tomar)\b",
    re.I,
)
MONEY_ASK_RE = re.compile(
    r"\b(send money|wire|gift card|account number|routing number|pin\b|social security|medicare number|"
    r"mande dinero|tarjeta de regalo|n[uú]mero de cuenta)\b",
    re.I,
)


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def codes(self) -> set[str]:
        return {e.split(" ", 1)[0] for e in self.errors}


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------
@lru_cache
def _schemas() -> dict[str, dict[str, Any]]:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(SCHEMAS.glob("*.schema.json"))}


@lru_cache
def _registry() -> Registry:
    return Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _schemas().values())


def _json_schema_errors(spec: dict[str, Any]) -> list[str]:
    root = _schemas()[SPEC_FILE]
    validator = Draft202012Validator({"$ref": root["$id"]}, registry=_registry(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path))
    return [f"schema {'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message[:200]}" for e in errors[:12]]


def catalog_types() -> list[str]:
    enum = _schemas()[SPEC_FILE]["$defs"]["catalog_type"]["enum"]
    return list(enum) + [t for t in EXTRA_CATALOG if t not in enum]


# ---------------------------------------------------------------------------
# JSON Schema -> pydantic (the mirror)
# ---------------------------------------------------------------------------
_RESERVED = set(dir(BaseModel))


def _resolve(ref: str, file: str) -> tuple[dict[str, Any], str, str]:
    target, _, pointer = ref.partition("#")
    file = target or file
    node: Any = _schemas()[file]
    name = file.split(".")[0]
    for part in [p for p in pointer.split("/") if p]:
        node = node[part]
        name = part
    return node, file, name


class _Builder:
    def __init__(self) -> None:
        self.cache: dict[tuple[str, str], Any] = {}

    def ref(self, ref: str, file: str) -> Any:
        node, nfile, name = _resolve(ref, file)
        key = (nfile, name)
        if key not in self.cache:
            override = _OVERRIDES.get(key)
            self.cache[key] = Any  # break cycles (none expected)
            self.cache[key] = override(self) if override else self.build(node, nfile, name)
        return self.cache[key]

    def build(self, s: dict[str, Any], file: str, name: str) -> Any:
        if "$ref" in s:
            return self.ref(s["$ref"], file)
        if "const" in s:
            return Literal[s["const"]]  # type: ignore[valid-type]
        if "enum" in s:
            return Literal[tuple(s["enum"])]  # type: ignore[valid-type]
        for key in ("anyOf", "oneOf"):
            if key in s and not s.get("properties") and s.get("type") is None:
                opts = [self.build(o, file, f"{name}_{i}") for i, o in enumerate(s[key]) if "required" not in o or len(o) > 1]
                if opts:
                    return Union[tuple(opts)]  # type: ignore[return-value]
        t = s.get("type")
        if isinstance(t, list):
            return Union[tuple(self.build({**s, "type": x}, file, name) for x in t)]  # type: ignore[return-value]
        if t == "object" or "properties" in s:
            return self.obj(s, file, name)
        if t == "array":
            item = self.build(s.get("items", {}), file, f"{name}_item")
            return Annotated[list[item], Field(min_length=s.get("minItems"), max_length=s.get("maxItems"))]  # type: ignore[valid-type]
        if t == "string":
            return Annotated[str, Field(min_length=s.get("minLength"), max_length=s.get("maxLength"), pattern=s.get("pattern"))]
        if t == "integer":
            return Annotated[int, Field(ge=s.get("minimum"), le=s.get("maximum"), strict=True)]
        if t == "number":
            return Annotated[float, Field(ge=s.get("minimum"), le=s.get("maximum"))]
        if t == "boolean":
            return StrictBool
        if t == "null":
            return type(None)
        return Any

    def obj(self, s: dict[str, Any], file: str, name: str) -> Any:
        props = s.get("properties")
        addl = s.get("additionalProperties", True)
        if not props:
            if isinstance(addl, dict):
                return dict[str, self.build(addl, file, f"{name}_value")]  # type: ignore[misc]
            return dict[str, Any]
        required = set(s.get("required", []))
        fields: dict[str, Any] = {}
        for pname, pschema in props.items():
            ann = self.build(pschema, file, f"{name}_{pname}")
            safe = pname if (pname.isidentifier() and not keyword.iskeyword(pname) and pname not in _RESERVED) else f"{pname}_"
            if pname in required:
                fields[safe] = (ann, Field(..., alias=pname))
            else:
                fields[safe] = (Optional[ann], Field(None, alias=pname))
        config = ConfigDict(extra="forbid" if addl is False else "allow", populate_by_name=True)
        return create_model(f"M_{name}", __config__=config, **fields)


def _element_union(b: _Builder) -> Any:
    tagged = []
    for t in catalog_types():
        props_schema = EXTRA_CATALOG.get(t) or {"$ref": f"#/$defs/props_{t}"}
        props_t = b.build(props_schema, SPEC_FILE, f"props_{t}")
        fields: dict[str, Any] = {"type": (Literal[t], ...), "props": (props_t, ...)}  # type: ignore[valid-type]
        if t in CONTAINER_TYPES:
            fields["children"] = (Annotated[list[Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")]], Field(max_length=12)], ...)
        model = create_model(f"Element_{t}", __config__=ConfigDict(extra="forbid"), **fields)
        tagged.append(Annotated[model, Tag(t)])
    custom = create_model(
        "Element_Custom",
        __config__=ConfigDict(extra="forbid"),
        type=(Annotated[str, Field(pattern=r"^Custom[A-Z][A-Za-z0-9]{2,28}$")], ...),
        props=(dict[str, Any], ...),
    )
    tagged.append(Annotated[custom, Tag("Custom")])
    known = set(catalog_types())

    def disc(v: Any) -> str | None:
        t = v.get("type") if isinstance(v, dict) else getattr(v, "type", None)
        if t in known:
            return t
        return "Custom" if isinstance(t, str) and t.startswith("Custom") else None

    return Annotated[Union[tuple(tagged)], Discriminator(disc)]  # type: ignore[return-value]


def _printable_union(b: _Builder) -> Any:
    sticker = b.build({"$ref": "#/$defs/printable_lid_sticker"}, SPEC_FILE, "printable_lid_sticker")
    fridge = b.build({"$ref": "#/$defs/printable_fridge_card"}, SPEC_FILE, "printable_fridge_card")
    return Annotated[Union[sticker, fridge], Field(discriminator="kind")]


_OVERRIDES = {(SPEC_FILE, "element"): _element_union, (SPEC_FILE, "printable"): _printable_union}


@lru_cache
def spec_model() -> type[BaseModel]:
    b = _Builder()
    root = _schemas()[SPEC_FILE]
    body = {k: v for k, v in root.items() if k not in {"$defs", "examples"}}
    return b.obj(body, SPEC_FILE, "VillageSpec")


def _model_errors(spec: dict[str, Any]) -> list[str]:
    try:
        spec_model().model_validate(spec)
    except ValidationError as exc:
        out = []
        for err in exc.errors()[:12]:
            loc = "/".join(str(x) for x in err["loc"])
            out.append(f"model {loc}: {err['msg'][:160]}")
        return out
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def validate_spec(spec: dict[str, Any], *, model: bool = True) -> ValidationReport:
    errors = _json_schema_errors(spec)
    if model and not errors:
        errors.extend(_model_errors(spec))
    warnings: list[str] = []
    if not errors:
        errors.extend(invariant_errors(spec))
        safety_errors, safety_warnings = safety_scan(spec)
        errors.extend(safety_errors)
        warnings.extend(safety_warnings)
    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)


def assert_valid_spec(spec: dict[str, Any]) -> None:
    report = validate_spec(spec)
    if not report.ok:
        raise ValueError(format_errors(report))


def format_errors(report: ValidationReport, limit: int = 12) -> str:
    return "\n".join(f"{idx + 1}. {err}" for idx, err in enumerate(report.errors[:limit]))


def _view_graph_errors(role: str, view: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    els = view.get("elements", {})
    if view.get("root") != "s" or els.get("s", {}).get("type") != "Screen":
        return [f"I2 view {role}: root s must be a Screen"]
    refs: dict[str, int] = {}
    for eid, element in els.items():
        for child in element.get("children", []):
            if child not in els:
                errors.append(f"I2 view {role}: {eid} references missing child {child}")
            refs[child] = refs.get(child, 0) + 1
    for eid in els:
        if eid != "s" and refs.get(eid, 0) != 1:
            errors.append(f"I2 view {role}: {eid} referenced {refs.get(eid, 0)}x (must be exactly once)")
    if refs.get("s"):
        errors.append(f"I2 view {role}: root s is referenced as a child (cycle)")
    # cycle detection
    state: dict[str, int] = {}

    def visit(eid: str) -> None:
        if state.get(eid) == 1:
            errors.append(f"I2 view {role}: cycle at {eid}")
            return
        if state.get(eid) == 2 or eid not in els:
            return
        state[eid] = 1
        for child in els[eid].get("children", []):
            visit(child)
        state[eid] = 2

    visit("s")
    return errors


def invariant_errors(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bp = spec["blueprint"]
    people = {p["id"]: p for p in bp["people"]}
    need_ids = {n["id"] for n in bp["needs"]} | {"n_safety"}
    text = bp["description"]["text"]
    views = spec["views"]

    # I1 channels <-> people, app:<role> == view, views exist
    if set(spec["channels"]) != set(people):
        errors.append(f"I1 channels keys {sorted(spec['channels'])} != people {sorted(people)}")
    for pid, person in people.items():
        view_name = person.get("view")
        if view_name is not None and view_name not in views:
            errors.append(f"I1 {pid}.view {view_name} missing from views")
        for channel in spec["channels"].get(pid, []):
            if channel.startswith("app:") and channel[4:] != view_name:
                errors.append(f"I1 {pid} channel {channel} != view {view_name}")

    for role, view in views.items():
        els = view["elements"]
        errors.extend(_view_graph_errors(role, view))
        needs_served = view.get("needs_served", {})
        # I3 needs_served
        for eid, element in els.items():
            if element["type"] not in LAYOUT_TYPES and eid not in needs_served:
                errors.append(f"I3 view {role}: {eid} ({element['type']}) has no needs_served")
            for need in needs_served.get(eid, []):
                if need not in need_ids:
                    errors.append(f"I3 view {role}: {eid} serves unknown need {need}")
            # I5 member refs
            props = element.get("props", {})
            for key in ("subject", "member_id"):
                if isinstance(props.get(key), str) and props[key] not in people:
                    errors.append(f"I5 view {role}: {eid}.{key} unknown member {props[key]}")
            for key in ("choices_member_ids", "subjects"):
                for mid in props.get(key, []) or []:
                    if mid not in people:
                        errors.append(f"I5 view {role}: {eid}.{key} unknown member {mid}")
            if element["type"] in {"BigButton"} and props.get("action") == "call_member":
                if props.get("action_arg") not in people:
                    errors.append(f"I5 view {role}: {eid} calls unknown member {props.get('action_arg')}")
        # I8 VillageChat
        chats = [eid for eid, e in els.items() if e["type"] == "VillageChat"]
        if len(chats) > 1:
            errors.append(f"I8 view {role}: {len(chats)} VillageChat elements (max 1)")
        if view["theme"] == "elder":
            if chats:
                errors.append(f"I8 view {role}: VillageChat in an elder view")
            # I4 elder floor
            buttons = [e for e in els.values() if e["type"] == "BigButton"]
            if len(buttons) > 3:
                errors.append(f"I4 view {role}: {len(buttons)} BigButtons (max 3)")
            if not any(e["type"] == "ContactCard" and e["props"].get("kind") == "emergency" and e["props"].get("phone") == "911" for e in els.values()):
                errors.append(f"I4 view {role}: no 911 ContactCard")
            for eid, e in els.items():
                p = e.get("props", {})
                if p.get("show_med_names"):
                    errors.append(f"I4 view {role}: {eid} shows med names")
                if e["type"] == "BigButton" and p.get("tone") == "danger" and not p.get("confirm"):
                    errors.append(f"I4 view {role}: danger button {eid} lacks confirm")

    # I5 needs / life areas / spans
    for need in bp["needs"]:
        span = need.get("source_span")
        if span and not (0 <= span["start"] < span["end"] <= len(text)):
            errors.append(f"I5 need {need['id']} source_span {span['start']}-{span['end']} outside description ({len(text)} chars)")
        for mid in need.get("subject_member_ids", []) or []:
            if mid not in people:
                errors.append(f"I5 need {need['id']} unknown subject {mid}")
    covered: set[str] = set()
    for area in bp["life_areas"]:
        covered.update(area["need_ids"])
        for nid in area["need_ids"]:
            if nid not in need_ids:
                errors.append(f"I5 life area {area['id']} unknown need {nid}")
        for module in area.get("modules", []):
            role, _, eid = module.partition(":")
            if role in {"voice", "outbound"}:
                continue
            if role not in views or eid not in views[role]["elements"]:
                errors.append(f"I5 life area {area['id']} module {module} not found")
        for mid in area.get("trusted_contacts", []) or []:
            if mid not in people:
                errors.append(f"I5 life area {area['id']} unknown trusted contact {mid}")
    for need in bp["needs"]:
        if need["id"] not in covered:
            errors.append(f"I5 need {need['id']} not in any life area")
    v = spec["village"]
    for key in ("coordinator_id", "care_recipient_id"):
        if v.get(key) and v[key] not in people:
            errors.append(f"I5 village.{key} {v[key]} is not a person")
    if bp["description"]["speaker"] not in people:
        errors.append(f"I5 description speaker {bp['description']['speaker']} is not a person")
    for edge in bp["edges"]:
        if edge["from"] not in people or edge["to"] not in people:
            errors.append(f"I5 edge {edge['from']}->{edge['to']} references an unknown member")
    return errors


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, str)]
    return []


def safety_scan(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    """S1 family word in a view · S2 medical advice / dose numbers · S3 money asks · warnings: phones, D22."""
    errors: list[str] = []
    warnings: list[str] = []
    family_word = ""
    for printable in spec.get("printables", []):
        if printable.get("kind") == "fridge_card":
            family_word = str(printable.get("family_word", "")).strip()
    known_phones = {p.get("phone") for p in spec["blueprint"]["people"] if p.get("phone")}
    for role, view in spec.get("views", {}).items():
        for eid, element in view.get("elements", {}).items():
            for key, value in element.get("props", {}).items():
                if key in {"bind", "binds", "url", "event_kinds", "action", "action_arg"}:
                    continue
                for s in _strings(value):
                    if family_word and family_word in s:
                        errors.append(f"S1 view {role}: {eid}.{key} exposes the family word")
                    if DOSE_ADVICE_RE.search(s):
                        errors.append(f"S2 view {role}: {eid}.{key} reads as medical advice: {s[:60]!r}")
                    if MONEY_ASK_RE.search(s):
                        errors.append(f"S3 view {role}: {eid}.{key} mentions money movement/account data: {s[:60]!r}")
                    if PHONE_RE.search(s) and s not in PUBLIC_NUMBERS and s not in known_phones:
                        warnings.append(f"safety view {role}: {eid}.{key} has a phone-like string")
    for pid, channels in spec.get("channels", {}).items():
        if "lid_qr" in channels:
            warnings.append(f"D22 {pid} has lid_qr (lid stickers are cut)")
    return errors, warnings


# ---------------------------------------------------------------------------
# Invariants 6 and 7 (not spec-level, provided for callers)
# ---------------------------------------------------------------------------
def check_patch_base_rev(patch_base_rev: int, client_rev: int) -> list[str]:
    return [] if patch_base_rev == client_rev else [f"I6 patch base_rev {patch_base_rev} != client rev {client_rev}"]


def check_verification(record: dict[str, Any]) -> list[str]:
    sm = json.loads((SCHEMAS / "verification.schema.json").read_text(encoding="utf-8"))["x-state-machine"]
    state, status = record.get("state"), record.get("status")
    errors = []
    if sm["status_of_state"].get(state) != status:
        errors.append(f"I7 verification state {state} implies status {sm['status_of_state'].get(state)}, got {status}")
    if state in {"confirmed", "late_confirmed", "denied", "late_denied"}:
        if not any(a.get("outcome") == "applied" for a in record.get("answers", [])):
            errors.append(f"I7 verification state {state} has no applied answer")
    return errors


def contract_errors(obj: dict[str, Any], ref: str) -> list[str]:
    """Validate any object against a contract `$ref`, e.g. 'ws_messages.schema.json#/$defs/control'."""
    file, _, pointer = ref.partition("#")
    base = _schemas()[file]["$id"]
    validator = Draft202012Validator({"$ref": f"{base}#{pointer}" if pointer else base}, registry=_registry(), format_checker=FormatChecker())
    return [f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message[:200]}" for e in validator.iter_errors(obj)]
