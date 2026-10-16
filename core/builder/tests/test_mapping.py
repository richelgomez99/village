from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.builder.mapping import (  # noqa: E402
    channels_for_person,
    ensure_chat,
    map_memory,
    map_tech_comfort,
    normalize_spec_mapping,
    roles_for,
)
from core.builder.paths import FIXTURES  # noqa: E402
from core.builder.validate import validate_spec  # noqa: E402


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_roles_and_enum_mapping() -> None:
    assert roles_for("care") == ["elder", "coordinator", "helper"]
    assert roles_for("block") == ["coordinator", "resident", "volunteer"]
    assert map_memory("lapses") == "mild_lapses"
    assert map_memory("impaired") == "significant"
    assert map_tech_comfort("none") == "phone"
    assert map_tech_comfort("medium") == "both"
    assert map_tech_comfort("high") == "app"


def test_channels_derive_without_lid_qr() -> None:
    reyes = _fixture("reyes_spec.json")
    people = {p["id"]: p for p in reyes["blueprint"]["people"]}

    assert "lid_qr" not in channels_for_person("care", people["m_carmen"])
    assert channels_for_person("care", people["m_carmen"]) == ["app:elder", "phone_line", "fridge_card"]
    assert channels_for_person("care", people["m_marco"]) == [
        "app:helper",
        "phone_line",
        "outbound_calls",
        "verification:app_prompt",
        "verification:call",
    ]


def test_normalized_fixtures_validate_and_keep_only_fridge_printables() -> None:
    for name in ("reyes_spec.json", "block_spec.json"):
        spec = normalize_spec_mapping(_fixture(name))
        report = validate_spec(spec)

        assert report.ok, report.errors
        assert all("lid_qr" not in channels for channels in spec["channels"].values())
        assert [p["kind"] for p in spec["printables"]] in (["fridge_card"], [])


def test_ensure_chat_is_idempotent_and_skips_elder() -> None:
    spec = normalize_spec_mapping(_fixture("reyes_spec.json"))
    again = ensure_chat(spec)

    for role, view in again["views"].items():
        chats = [eid for eid, element in view["elements"].items() if element["type"] == "VillageChat"]
        if role == "elder":
            assert chats == []
        else:
            assert chats == ["chat"]
            assert view["elements"]["chat"]["props"]["allow_approve"] is (role == "coordinator")
            assert view["needs_served"]["chat"] == ["n_safety"]
