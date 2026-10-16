"""Validate every contract schema, schema example, fixture and openapi.yaml.

Run from the repo root:
    uv run --with jsonschema --with pyyaml --with openapi-spec-validator python contracts/validate.py
Exit code 0 = all green. Not application code: a contract check for every lane.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
FIX = ROOT / "fixtures"
BASE = "https://village.contracts/v1/"
errors: list[str] = []


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


schemas = {p.name: load(p) for p in sorted(SCHEMAS.glob("*.schema.json"))}
version = (ROOT / "VERSION").read_text().strip()
registry = Registry().with_resources(
    (s["$id"], Resource.from_contents(s)) for s in schemas.values()
)


def validator(name: str, pointer: str = ""):
    schema = {"$ref": BASE + name + (("#" + pointer) if pointer else "")}
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def check(label: str, name: str, inst, pointer: str = "") -> None:
    errs = sorted(validator(name, pointer).iter_errors(inst), key=lambda e: list(e.absolute_path))
    for e in errs[:8]:
        path = "/".join(str(x) for x in e.absolute_path)
        errors.append(f"{label}: {name}{'#' + pointer if pointer else ''} at /{path}: {e.message[:300]}")


# 1. schemas are valid 2020-12 and carry the contract version
for name, s in schemas.items():
    try:
        Draft202012Validator.check_schema(s)
    except Exception as e:  # noqa: BLE001
        errors.append(f"{name}: invalid schema: {e}")
    if s.get("x-contract-version") != version:
        errors.append(f"{name}: x-contract-version {s.get('x-contract-version')} != VERSION {version}")
if schemas["common.schema.json"]["$defs"]["contract_version"]["const"] != version:
    errors.append("common.schema.json: contract_version const != VERSION")

# 2. schema examples
for name, s in schemas.items():
    for i, ex in enumerate(s.get("examples", [])):
        if name == "common.schema.json":
            continue
        check(f"{name} examples[{i}]", name, ex)


# 3. cross-field invariants for VillageSpecs (what JSON Schema cannot say)
def spec_invariants(label: str, spec: dict) -> None:
    bp = spec["blueprint"]
    people = {p["id"]: p for p in bp["people"]}
    need_ids = {n["id"] for n in bp["needs"]} | {"n_safety"}
    text = bp["description"]["text"]
    for n in bp["needs"]:
        sp = n["source_span"]
        if sp and not (0 <= sp["start"] < sp["end"] <= len(text)):
            errors.append(f"{label}: need {n['id']} span out of range")
    if set(spec["channels"]) != set(people):
        errors.append(f"{label}: channels keys {sorted(spec['channels'])} != people {sorted(people)}")
    for pid, p in people.items():
        if p["view"] is not None and p["view"] not in spec["views"]:
            errors.append(f"{label}: {pid}.view {p['view']} not in views")
        for ch in spec["channels"].get(pid, []):
            if ch.startswith("app:") and ch[4:] != p["view"]:
                errors.append(f"{label}: {pid} channel {ch} != view {p['view']}")
        for ref in p["consent"].get("share_with", []) + p["consent"].get("money_safety_share_with", []):
            if ref not in people:
                errors.append(f"{label}: {pid} consent refers to unknown {ref}")
    for role, view in spec["views"].items():
        els = view["elements"]
        if "s" not in els or els["s"]["type"] != "Screen":
            errors.append(f"{label}: view {role} root s missing or not a Screen")
            continue
        seen: dict[str, int] = {}
        for eid, el in els.items():
            for c in el.get("children", []):
                if c not in els:
                    errors.append(f"{label}: view {role} {eid} child {c} missing")
                seen[c] = seen.get(c, 0) + 1
        for eid in els:
            if eid != "s" and seen.get(eid, 0) != 1:
                errors.append(f"{label}: view {role} element {eid} referenced {seen.get(eid, 0)}x (must be 1)")
        for eid, ns in view.get("needs_served", {}).items():
            if eid not in els:
                errors.append(f"{label}: view {role} needs_served key {eid} not an element")
            for n in ns:
                if n not in need_ids:
                    errors.append(f"{label}: view {role} {eid} serves unknown need {n}")
        for eid, el in els.items():
            if el["type"] not in ("Screen", "Stack", "Header", "Text") and eid not in view.get("needs_served", {}):
                errors.append(f"{label}: view {role} {eid} ({el['type']}) missing needs_served")
            for k in ("subject", "member_id"):
                v = el["props"].get(k)
                if isinstance(v, str) and v not in people:
                    errors.append(f"{label}: view {role} {eid}.{k}={v} unknown member")
            for v in el["props"].get("choices_member_ids", []) + el["props"].get("subjects", []):
                if v not in people:
                    errors.append(f"{label}: view {role} {eid} unknown member {v}")
        chats = [eid for eid, e in els.items() if e["type"] == "VillageChat"]
        if len(chats) > 1:
            errors.append(f"{label}: view {role} has {len(chats)} VillageChat elements (max 1)")
        if view["theme"] == "elder":
            if chats:
                errors.append(f"{label}: elder view {role} has a VillageChat ({chats[0]})")
            bb = [e for e in els.values() if e["type"] == "BigButton"]
            if len(bb) > 3:
                errors.append(f"{label}: elder view {role} has {len(bb)} BigButtons")
            if not any(e["type"] == "ContactCard" and e["props"].get("kind") == "emergency" for e in els.values()):
                errors.append(f"{label}: elder view {role} lacks 911 ContactCard")
            for eid, e in els.items():
                if e["props"].get("show_med_names"):
                    errors.append(f"{label}: elder view {role} {eid} shows med names")
                if e["type"] == "RefillCard":  # 1.2.0 invariant 9: med names never on the elder view
                    errors.append(f"{label}: elder view {role} has a RefillCard ({eid})")
    for la in bp["life_areas"]:
        for n in la["need_ids"]:
            if n not in need_ids:
                errors.append(f"{label}: life area {la['id']} unknown need {n}")
        for m in la["modules"]:
            r, _, e = m.partition(":")
            if r in spec["views"] and e not in spec["views"][r]["elements"]:
                errors.append(f"{label}: life area {la['id']} module {m} not found")
        for m in la.get("trusted_contacts", []):
            if m not in people:
                errors.append(f"{label}: life area {la['id']} unknown trusted contact {m}")
    covered = {n for la in bp["life_areas"] for n in la["need_ids"]}
    for n in bp["needs"]:
        if n["id"] not in covered:
            errors.append(f"{label}: need {n['id']} not in any life area")
    for e in bp["edges"]:
        if e["from"] not in people or e["to"] not in people:
            errors.append(f"{label}: edge {e} unknown member")
    for pr in spec["printables"]:
        if pr["member_id"] not in people:
            errors.append(f"{label}: printable {pr['id']} unknown member")


for ex_i, ex in enumerate(schemas["village_spec.schema.json"].get("examples", [])):
    spec_invariants(f"village_spec examples[{ex_i}]", ex)

# 4. fixtures
def fx(name):
    return load(FIX / name)


for f in ("reyes_spec.json", "block_spec.json"):
    spec = fx(f)
    check(f, "village_spec.schema.json", spec)
    if not errors or all(not e.startswith(f) for e in errors):
        spec_invariants(f, spec)

for seed_path in sorted(FIX.glob("events_*_seed.json")):  # every registered village's seed (D30: same checks for every village)
    sname = seed_path.name
    seed = fx(sname)
    ids = set()
    for i, ev in enumerate(seed["events"]):
        check(f"{sname} events[{i}]", "event.schema.json", ev)
        if ev["id"] in ids:
            errors.append(f"{sname}: duplicate id {ev['id']}")
        ids.add(ev["id"])
    ats = [ev["at"] for ev in seed["events"]]
    if ats != sorted(ats):
        errors.append(f"{sname}: events out of chronological order")

for msgs_path in sorted(FIX.glob("messages_*_seed.json")):
    mname = msgs_path.name
    msgs = fx(mname)
    mids: set[str] = set()
    last_at = ""
    for i, m in enumerate(msgs["messages"]):
        check(f"{mname} messages[{i}]", "message.schema.json", m)
        if m["id"] in mids:
            errors.append(f"{mname}: duplicate id {m['id']}")
        mids.add(m["id"])
        if m["at"] < last_at:
            errors.append(f"{mname}: messages[{i}] out of order ({m['at']} < {last_at})")
        last_at = m["at"]
        if m.get("reply_to") and m["reply_to"] not in mids:
            errors.append(f"{mname}: messages[{i}] reply_to {m['reply_to']} not an earlier message")
        if m["author"] == "village" and not m["refs"]:
            errors.append(f"{mname}: messages[{i}] village post without refs")

scam = fx("scam_call_tool_requests.json")
for variant, body in scam["variants"].items():
    for i, ex in enumerate(body["exchanges"]):
        check(f"scam_call_tool_requests.json {variant}[{i}]", "voice_tools.schema.json", ex)
    if "verification_after" in body:
        check(f"scam_call_tool_requests.json {variant}.verification_after", "verification.schema.json", body["verification_after"])
    for i, ans in enumerate(body.get("answers", [])):
        check(f"scam_call_tool_requests.json {variant}.answers[{i}]", "voice_tools.schema.json", ans["body"], "/$defs/verification_answer_request")

C2S = {"hello", "ack", "action", "ping"}
for f in ("ws_sequence_scam.json",):
    seq = fx(f)
    for vname, steps in seq["sequences"].items():
        for i, st in enumerate(steps):
            msg = st["msg"]
            ptr = "/$defs/client_message" if st["dir"] == "c2s" else "/$defs/server_message"
            if (msg.get("type") in C2S) != (st["dir"] == "c2s"):
                errors.append(f"{f} {vname}[{i}]: dir {st['dir']} vs type {msg.get('type')}")
            if st["client"] not in seq["clients"]:
                errors.append(f"{f} {vname}[{i}]: unknown client {st['client']}")
            check(f"{f} {vname}[{i}]", "ws_messages.schema.json", msg, ptr)

lid = fx("lid_scan_sequence.json")
for i, st in enumerate(lid["steps"]):
    if st.get("result") is not None:
        check(f"lid_scan_sequence.json steps[{i}].result", "lid_scan.schema.json", st["result"])
    for j, w in enumerate(st.get("ws", [])):
        check(f"lid_scan_sequence.json steps[{i}].ws[{j}]", "ws_messages.schema.json", w["msg"], "/$defs/server_message")

# 5. openapi.yaml parses, is 3.1, and every external $ref resolves
api = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))
if not str(api.get("openapi", "")).startswith("3.1"):
    errors.append("openapi.yaml: not OpenAPI 3.1")
if api.get("info", {}).get("version") != version:
    errors.append("openapi.yaml: info.version != VERSION")


def walk(node, path="$"):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            target, _, ptr = ref.partition("#")
            if target:
                fp = (ROOT / target).resolve()
                if not fp.exists():
                    errors.append(f"openapi.yaml {path}: missing file {target}")
                else:
                    doc = load(fp)
                    try:
                        for part in [p for p in ptr.split("/") if p]:
                            doc = doc[part.replace("~1", "/").replace("~0", "~")]
                    except (KeyError, TypeError):
                        errors.append(f"openapi.yaml {path}: bad pointer {ref}")
            else:
                d = api
                try:
                    for part in [p for p in ptr.split("/") if p]:
                        d = d[part]
                except (KeyError, TypeError):
                    errors.append(f"openapi.yaml {path}: bad local ref {ref}")
        for k, v in node.items():
            walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")


walk(api)
try:  # full OpenAPI 3.1 structural check when the package is available
    from openapi_spec_validator import validate as validate_openapi
    from openapi_spec_validator.readers import read_from_filename

    _d, _url = read_from_filename(str(ROOT / "openapi.yaml"))
    validate_openapi(_d, base_uri=_url)
except ImportError:
    print("note: openapi-spec-validator not installed; only parsed openapi.yaml and checked $refs")
except Exception as e:  # noqa: BLE001
    errors.append(f"openapi.yaml: {str(e).splitlines()[0][:300]}")

if errors:
    print(f"FAIL ({len(errors)})")
    for e in errors:
        print(" -", e)
    sys.exit(1)
n_ex = sum(len(s.get("examples", [])) for s in schemas.values())
n_fx = len(list(FIX.glob("*.json")))
print(f"OK contract {version}: {len(schemas)} schemas, {n_ex} examples, {n_fx} fixtures, openapi {api['openapi']} with {len(api['paths'])} paths")
