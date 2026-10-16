from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "contracts" / "schemas"
sys.path.insert(0, str(ROOT))

from core.gate.models import GateInput, gate_input_from_args  # noqa: E402


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


def validator(schema_name: str, ref: str | None = None) -> Draft202012Validator:
    root_schema = load_schema(schema_name)
    schema = root_schema
    if ref:
        schema = {"$ref": f"#{ref}"}
    store = {p.name: load_schema(p.name) for p in SCHEMAS.glob("*.schema.json")}
    resolver = RefResolver(base_uri=f"{schema_name}", referrer=root_schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def test_gate_schema_examples_roundtrip_contract_shape():
    schema = load_schema("gate.schema.json")
    case_validator = validator("gate.schema.json")
    input_validator = validator("gate.schema.json", "/$defs/gate_input")
    decision_validator = validator("gate.schema.json", "/$defs/decision")

    assert len(schema["examples"]) >= 2
    for case in schema["examples"]:
        case_validator.validate(case)
        gate_input = GateInput.from_mapping(case["input"])
        assert gate_input.to_dict() == case["input"]
        input_validator.validate(gate_input.to_dict())
        decision_validator.validate(case["decision"])


def test_gate_input_from_core_call_form_sets_now():
    inp = gate_input_from_args(
        {"village_id": "v_reyes", "now": "2026-10-16T14:02:09-04:00"},
        {
            "village": "v_reyes",
            "kind": "tick",
            "payload": {"reason": "dose_window"},
            "actor": "scheduler",
            "source": {"kind": "system", "ref": "scheduler"},
            "at": "2026-10-16T14:02:09-04:00",
        },
        {"decision_id": "dc_test_001"},
        "2026-10-16T14:03:00-04:00",
    )

    assert inp.village_state["now"] == "2026-10-16T14:03:00-04:00"
    assert inp.event["at"] == "2026-10-16T14:02:09-04:00"
