from __future__ import annotations

from typing import Any


def _span(text: str, needle: str) -> dict[str, int]:
    start = text.lower().find(needle.lower())
    if start < 0:
        return {"start": 0, "end": min(len(text), max(1, len(text)))}
    return {"start": start, "end": start + len(needle)}


def extract_blueprint(description: str, kind: str = "care") -> dict[str, Any]:
    if kind == "block" or "blackout" in description.lower():
        return {
            "kind": "block",
            "people": [
                {"id": "b_tanya", "name": "Tanya", "role": "coordinator", "view": "coordinator", "relation": "block coordinator", "reason": "coordinates the block"},
                {"id": "b_darnell", "name": "Darnell", "role": "volunteer", "view": "volunteer", "relation": "volunteer", "reason": "can knock and report outcomes"},
            ],
            "needs": [
                {"id": "n_power", "text": "Power is out and residents need checks", "source_span": _span(description, "power")},
                {"id": "n_rumors", "text": "The group needs verified information", "source_span": _span(description, "rumor")},
            ],
            "life_areas": ["information", "daily_living"],
            "rules": ["rumor_check", "privacy"],
            "questions": [],
        }
    people = [
        {"id": "m_carmen", "name": "Carmen Reyes", "role": "care_recipient", "view": "elder", "relation": "mother", "reason": "Mom is the vulnerable center"},
        {"id": "m_ana", "name": "Ana Reyes", "role": "coordinator", "view": "coordinator", "relation": "daughter", "reason": "speaker and coordinator"},
    ]
    if "marco" in description.lower():
        people.append({"id": "m_marco", "name": "Marco Reyes", "role": "caregiver", "view": "helper", "relation": "son", "reason": "named in money verification and rota"})
    if "luc" in description.lower():
        people.append({"id": "m_lucia", "name": "Lucía Reyes", "role": "caregiver", "view": "helper", "relation": "daughter", "reason": "family helper"})
    needs = [
        {"id": "n_evening_pills", "text": "Mom mixes up her pills", "source_span": _span(description, "mixes up her pills")},
        {"id": "n_scam_calls", "text": "Someone pretended to be Marco and asked for money", "source_span": _span(description, "pretending to be Marco")},
        {"id": "n_turns", "text": "Family members missed a visit because turns were unclear", "source_span": _span(description, "nobody went")},
    ]
    questions = [] if len(people) >= 3 else ["Who else helps?", "What does she like to be called?"]
    return {
        "kind": "care",
        "people": people,
        "needs": needs,
        "life_areas": ["health", "money", "people"],
        "rules": ["double_dose_guard", "money_verification", "quiet_hours"],
        "questions": questions[:2],
    }


async def stream_blueprint(description: str, village_id: str, services: Any, kind: str = "care") -> dict[str, Any]:
    blueprint = extract_blueprint(description, kind)
    sequence: list[tuple[str, str]] = [("plan", f"Found {blueprint['kind']} village shape from the founding description.")]
    sequence.extend(("note", f"Found {p['name']}: {p['reason']}.") for p in blueprint["people"])
    sequence.extend(("note", f"Need: {n['text']}.") for n in blueprint["needs"])
    sequence.extend(("decision", f"Rule on: {rule}.") for rule in blueprint["rules"])
    for kind_name, text in sequence:
        await services.broadcast_control(
            village_id,
            {
                "type": "control",
                "village": village_id,
                "payload": {"source": "builder", "kind": kind_name, "text": text, "village": village_id},
            },
        )
    await services.broadcast_control(
        village_id,
        {"type": "control", "village": village_id, "payload": {"source": "builder", "kind": "counter", "name": "people_found", "value": len(blueprint["people"])}},
    )
    return blueprint
