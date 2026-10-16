from core.ids import RecordID, to_cid, to_rid


def test_village_id_strips_prefix() -> None:
    rid = to_rid("v_reyes")
    assert rid == RecordID("village", "reyes")
    assert to_cid(rid) == "v_reyes"


def test_member_event_decision_ids_round_trip() -> None:
    for cid in ["m_marco", "ev_1016_0811_dose_morning", "dc_0001", "ver_1016_01", "msg_1", "st_reyes_morning"]:
        assert to_cid(to_rid(cid)) == cid
