from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VOICE_SCHEMA = ROOT / "contracts" / "schemas" / "voice_tools.schema.json"
TOOL_DIR = ROOT / "agents" / "tool_configs"

TOOL_TO_DEF = {
    "submit_verification_answer": "verification_answer_request",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def resolve_local(schema: dict[str, Any], node: Any) -> Any:
    if isinstance(node, dict) and "$ref" in node and node["$ref"].startswith("#/$defs/"):
        return resolve_local(schema, schema["$defs"][ref_name(node["$ref"])])
    return node


def prop_names(contract_schema: dict[str, Any], definition: str) -> set[str]:
    node = resolve_local(contract_schema, contract_schema["$defs"][definition])
    return set(node.get("properties", {}).keys())


def required_names(contract_schema: dict[str, Any], definition: str) -> set[str]:
    node = resolve_local(contract_schema, contract_schema["$defs"][definition])
    return set(node.get("required", []))


def tool_schema(config: dict[str, Any]) -> dict[str, Any]:
    try:
        return config["api_schema"]["request_body_schema"]
    except KeyError as exc:
        raise ValueError("missing api_schema.request_body_schema") from exc


def check_file(path: Path, contract: dict[str, Any]) -> list[str]:
    config = load_json(path)
    name = config["name"]
    definition = TOOL_TO_DEF.get(name, f"req_{name}")
    errors: list[str] = []

    if definition not in contract["$defs"]:
        return [f"{path}: no contract definition {definition}"]

    request_schema = tool_schema(config)
    actual_props = set(request_schema.get("properties", {}).keys())
    contract_props = prop_names(contract, definition)
    extra = actual_props - contract_props
    if extra:
        errors.append(f"{path}: properties not in {definition}: {sorted(extra)}")

    actual_required = set(request_schema.get("required", []))
    missing_required = required_names(contract, definition) - actual_required
    optional_by_assignment = {"conversation_id", "caller_id", "call_secs"}
    missing_required -= optional_by_assignment
    if missing_required:
        errors.append(f"{path}: missing required fields from {definition}: {sorted(missing_required)}")

    if request_schema.get("additionalProperties") is not False:
        errors.append(f"{path}: request_body_schema.additionalProperties must be false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-dir", type=Path, default=TOOL_DIR)
    args = parser.parse_args()

    contract = load_json(VOICE_SCHEMA)
    paths = sorted(args.tool_dir.glob("*.json"))
    errors: list[str] = []
    for path in paths:
        errors.extend(check_file(path, contract))

    if errors:
        for error in errors:
            print(error)
        return 1

    print(f"OK {len(paths)} tool schemas are contract subsets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

