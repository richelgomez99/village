from core.db import db
from core.fixtures import reset_demo


async def test_reset_demo_loads_reyes_fixture() -> None:
    result = await reset_demo("v_reyes")
    assert result["members"] == 4
    assert result["views"] == 3
    from core.db import db as _db

    assert len([e for e in _db.events if e.get("village") == "v_reyes"]) == 12  # group villages add their own seeded check-ins
    assert db.specs["v_reyes"]["rev"] == 5
    assert ("v_reyes", "elder") in db.views
    assert db.prescriptions["v_reyes"][1]["dose"] == "10 mg"
