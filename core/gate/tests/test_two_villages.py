"""D30: one gate, two villages. The same rules (P-QH-01 quiet hours, R-MONEY-DEFAULT) run against two
village specs; only the spec params differ, and the decisions differ accordingly. No names in code:
everything below is read from contracts/fixtures/*_spec.json through core.village.state_from_spec."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.gate import decide  # noqa: E402
from core.village import state_from_spec  # noqa: E402

SPECS = {name: json.loads((ROOT / "contracts" / "fixtures" / name).read_text()) for name in ("reyes_spec.json", "block_spec.json")}
NOW = "2026-10-16T21:50:00-04:00"  # inside the care village's quiet hours, 50 min after a 21:00 slot


def _state(spec: dict, **kw) -> dict:
    return state_from_spec(spec, now=NOW, **kw)


def _params(spec: dict, rule_id: str) -> dict | None:
    return next((p.get("params") or {} for p in spec["policies"] if p["rule_id"] == rule_id), None)


def _subject(spec: dict) -> str:
    return spec["village"].get("care_recipient_id") or next(p["id"] for p in spec["blueprint"]["people"] if p.get("view") is None)


def _tick(spec: dict) -> dict:
    state = _state(spec)
    window = {
        "village": spec["village"]["id"],
        "subject": _subject(spec),
        "slot": "evening",
        "date": NOW[:10],
        "slot_time": "21:00",
        "state": "window_open",
        "version": 0,
    }
    state["dose_windows"] = [window]
    event = {"village": spec["village"]["id"], "kind": "tick", "payload": {"reason": "dose_window"}, "at": NOW,
             "source": {"kind": "system", "ref": "scheduler"}}
    return decide({"village_state": state, "event": event, "alloc": {"decision_id": "dc_two_1"}})


def test_params_differ_between_the_two_specs():
    care, block = SPECS["reyes_spec.json"], SPECS["block_spec.json"]
    assert _params(care, "P-QH-01")["quiet_hours"] and _params(block, "P-QH-01") is None
    assert _state(care)["quiet_hours"] == _params(care, "P-QH-01")["quiet_hours"]
    assert "quiet_hours" not in _state(block)
    assert _state(care)["coordinator_id"] != _state(block)["coordinator_id"]


def test_P_QH_01_quiet_hours_suppress_the_reminder_only_where_the_spec_sets_them():
    care = _tick(SPECS["reyes_spec.json"])
    block = _tick(SPECS["block_spec.json"])
    # care village: 21:50 is inside its P-QH-01 window -> no reminder call
    assert care["decision"] != "remind"
    assert not any(w["kind"] == "reminder" for w in care["writes"])
    # block village: no P-QH-01 param -> the same tick reminds
    assert block["decision"] == "remind"
    assert block["writes"][0]["kind"] == "reminder"


@pytest.mark.parametrize("answer,say_key", [("no", "money_denied"), ("unsure", "money_timeout")])
def test_R_MONEY_DEFAULT_notifies_and_names_each_villages_own_coordinator(answer: str, say_key: str):
    out = {}
    for name, spec in SPECS.items():
        state = _state(spec)
        coord = state["coordinator_id"]
        claimed = next(m for m in state["members"] if m["id"] != coord and m["id"] != state.get("care_recipient_id"))
        state["open_verifications"] = [{"id": "ver_two", "claimed_member_id": claimed["id"], "state": "pending"}]
        event = {"village": spec["village"]["id"], "kind": "verification_answer",
                 "payload": {"verification_id": "ver_two", "member_id": claimed["id"], "answer": answer},
                 "at": NOW, "source": {"kind": "app", "ref": "prompt"}}
        d = decide({"village_state": state, "event": event, "alloc": {"decision_id": "dc_two_2", "incident_id": "inc_two"}})
        coord_name = next(m["name"] for m in state["members"] if m["id"] == coord)
        assert d["rule_id"] == "R-MONEY-DEFAULT" and d["decision"] == "advise_do_not_send" and d["say_key"] == say_key
        assert d["notify"][0]["member_id"] == coord
        assert coord_name in d["say"]["es"] and coord_name in d["say"]["en"]
        assert claimed["name"] in d["say"]["en"]
        out[name] = d
    care, block = out["reyes_spec.json"], out["block_spec.json"]
    assert care["notify"][0]["member_id"] != block["notify"][0]["member_id"]
    assert care["say"] != block["say"]
