from core.ids import RecordID, to_cid, to_rid
from core.db import MemoryDB


def test_village_id_strips_prefix() -> None:
    rid = to_rid("v_reyes")
    assert rid == RecordID("village", "reyes")
    assert to_cid(rid) == "v_reyes"


def test_member_event_decision_ids_round_trip() -> None:
    for cid in ["m_marco", "ev_1016_0811_dose_morning", "dc_0001", "ver_1016_01", "msg_1", "st_reyes_morning"]:
        assert to_cid(to_rid(cid)) == cid


async def test_memory_db_cas_update_matches_version() -> None:
    memory = MemoryDB()
    await memory.upsert_verification({"id": "ver_1", "state": "pending", "version": 0})
    assert await memory.cas_update("verification", "ver_1", 99, {"state": "denied"}) == []
    updated = await memory.cas_update("verification", "ver_1", 0, {"state": "denied"})
    assert updated == [{"id": "ver_1", "state": "denied", "version": 1}]
