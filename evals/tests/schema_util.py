import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from evals.reyes import ROOT

BASE = "https://village.contracts/v1/"
_schemas = {p.name: json.loads(p.read_text()) for p in (ROOT / "contracts" / "schemas").glob("*.schema.json")}
_registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _schemas.values())


def errors(name: str, pointer: str, inst) -> list[str]:
    v = Draft202012Validator({"$ref": f"{BASE}{name}#{pointer}"}, registry=_registry)
    return [f"/{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}" for e in v.iter_errors(inst)]
