"""D35/D36 on a group village (no care recipient): Tanya's @Village cooling-center message →
deterministic extraction (model off) → proposal with owned plan items → approve → every role changes in place."""
from __future__ import annotations

import asyncio
import os

MSG = ("@Village the library cooling center closed early. We're moving everyone who needs cool air to the Hamilton Grange "
       "center on 145th at 3: Priya drives the Okafors, Darnell stays with the generator for Mrs. Alvarez, Mr. James needs a ride too.")


def test_block_rebuild_model_off() -> None:
    os.environ["VILLAGE_EVOLVE_RELEASE"] = "fake"
    os.environ.setdefault("VILLAGE_LLM", "off")
    os.environ["SURREAL_DB_URL"] = ""
    from core.settings import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from core.app import app
    from core.builder.chat_intent import plan_data, propose_change
    from core.db import db
    from core.evolve import proposals as ev

    with TestClient(app) as c:
        prop = asyncio.run(propose_change("v_w147", MSG, "b_tanya", llm=None))
        assert prop["title"]["en"] == "Add the cooling-center move to the village"
        assert set(prop["ops"]) >= {"coordinator", "volunteer", "resident"}
        plan = ev.STORE["v_w147"][prop["id"]]["plan"]
        members = {p["id"] for p in db.specs["v_w147"]["blueprint"]["people"]}
        owned = [i for i in plan["items"] if i.get("owner") in members and i.get("kind")]
        assert {(i["text"], i["owner"]) for i in owned} >= {("Priya drives the Okafors at 3", "b_priya"), ("Darnell stays with the generator for Mrs. Alvarez", "b_darnell")}
        assert any(i["text"] == "Ride for Mr. James at 3" and i["status"] == "open" for i in plan["items"])
        assert "family" not in str(ev.STORE["v_w147"][prop["id"]]["stays_the_same"]["en"])
        a = c.post(f"/villages/v_w147/proposals/{prop['id']}/approve?wait=true", headers={"Authorization": "Bearer b_tanya"})
        assert a.status_code == 202, a.text
        views = db.specs["v_w147"]["views"]
        assert views["coordinator"]["elements"]["plan"]["props"]["bind"] == f"plan:{plan['id']}"
        assert len(views["coordinator"]["elements"]["s"]["children"]) <= 12
        assert "Priya drives the Okafors at 3" in views["volunteer"]["elements"]["plan_event"]["props"]["text"]
        assert "Priya picks up the Okafors at 3" in views["resident"]["elements"]["plan_event"]["props"]["text"]
        assert plan_data("v_w147", plan["id"])["items"][1]["owner"] == "b_priya"
