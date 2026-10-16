from core.db import db
from core.fixtures import reset_demo


async def test_reset_demo_loads_reyes_fixture() -> None:
    result = await reset_demo("v_reyes")
    assert result["members"] == 4
    assert result["views"] == 3
    assert result["events"] == 12
    assert db.specs["v_reyes"]["rev"] == 4
    assert ("v_reyes", "elder") in db.views
    assert db.prescriptions["v_reyes"][1]["dose"] == "10 mg"
