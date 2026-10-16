"""D38: a business/resource member on the block answers an ask as a sender ("we'll send someone with ice"),
a person answers as a person. Pure apart from the spec lookup; the block fixture supplies the roles."""
from core import village as villages
from core.builder import actors


def _block() -> str:
    return next(v for v in villages.village_ids() if any(p.get("role") == "business" for p in villages.people(v)))


def test_business_member_sends_the_resource() -> None:
    vid = _block()
    deli = next(p["id"] for p in villages.people(vid) if p.get("role") == "business")
    line, answer = actors.canned_line(vid, deli, "plan", {"what": "four bags of ice", "day": "today", "type": "plan"})
    assert answer == "yes" and "four bags of ice" in line and "fifteen minutes" in line
    assert actors.persona_kind(vid, deli) == "business"


def test_person_member_keeps_the_people_lines() -> None:
    vid = _block()
    vol = next(p["id"] for p in villages.people(vid) if p.get("role") == "volunteer")
    line, answer = actors.canned_line(vid, vol, "cover", {"day": "Saturday"})
    assert answer == "yes" and "Saturday" in line
    line, answer = actors.canned_line(vid, vol, "on_duty", {"day": "Saturday"})
    assert answer == "no"
