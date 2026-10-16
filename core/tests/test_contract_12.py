from fastapi.testclient import TestClient

from core.app import app
from core.bindings import changed, snapshot_data
from core.fixtures import reset_demo

from core.settings import CONTRACT_VERSION as V


async def test_prescriptions_binding_for_helper_and_coordinator() -> None:
    await reset_demo("v_reyes")
    for role, member in (("helper", "m_marco"), ("coordinator", "m_ana")):
        rx = snapshot_data(role, member)["prescriptions:current"]
        assert rx["refill_day"] == "Fri" and rx["owner_member_id"] == "m_marco"
        first = rx["items"][0]
        assert first["name"] == "lisinopril" and first["dose_text"] == "10 mg" and first["dose_mg"] == 10
        assert first["superseded"] == {"dose_text": "5 mg", "valid_until": "2026-10-03"}
        assert first["changed_by"] == "Dr. Park"
        names = [item["name"] for item in rx["items"]]
        assert names == ["lisinopril", "apixaban", "metformin", "atorvastatin"]
        apixaban = rx["items"][1]
        assert apixaban["dose_text"] == "5 mg" and apixaban["schedule"] == ["morning", "evening"]
    assert "prescriptions:current" not in snapshot_data("elder", "m_carmen")


async def test_prescriptions_in_changed_on_med_change() -> None:
    await reset_demo("v_reyes")
    event = {"kind": "med_change", "payload": {"subject": "m_carmen"}}
    assert "prescriptions:current" in changed(event, "helper", "m_marco")
    assert changed(event, "elder", "m_carmen") == {}


def _hello(ws, token, **extra):
    ws.send_json({"type": "hello", "contract_version": V, "village": "v_reyes", "member_token": token, **extra})
    return ws.receive_json()


def test_snapshot_identity_and_spec() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?village=v_reyes&m=mt_marco_9Qe2vLx7Rk3pZ0aB") as ws:
            snap = _hello(ws, "mt_marco_9Qe2vLx7Rk3pZ0aB")
            assert snap["identity"] == {"member_id": "m_marco", "name": "Marco", "role": "helper", "village_name": "Familia Reyes"} or snap["identity"]["name"] == "Marco"
            assert snap["role"] == "helper" and snap["spec"]["root"]
            assert "now" in snap
        with client.websocket_connect("/ws?village=v_reyes&m=control") as ws:
            snap = _hello(ws, "control")
            assert snap["identity"]["role"] == "control" and snap["identity"]["member_id"] is None
            assert snap["member_id"] is None and snap["spec"]["rev"] == snap["rev"]


def test_view_as_only_for_coordinator_and_control_and_read_only() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?village=v_reyes&m=control") as ws:
            snap = _hello(ws, "control", view_as="m_carmen")
            assert snap["role"] == "elder" and snap["member_id"] == "m_carmen"
            assert snap["identity"]["view_as"] is True
            ws.send_json({"type": "action", "req_id": "r1", "name": "check_in_ok"})
            err = ws.receive_json()
            assert err["type"] == "error" and err["code"] == "not_allowed"
        with client.websocket_connect("/ws?village=v_reyes&m=m_ana") as ws:
            snap = _hello(ws, "mt_ana_0000000000000000", view_as="m_marco")
            assert snap["role"] == "helper" and snap["identity"]["view_as"] is True
        with client.websocket_connect("/ws?village=v_reyes&m=m_marco") as ws:
            err = _hello(ws, "mt_marco_9Qe2vLx7Rk3pZ0aB", view_as="m_ana")
            assert err["type"] == "error" and err["code"] == "not_allowed"
            snap = ws.receive_json()
            assert snap["type"] == "snapshot" and snap["member_id"] == "m_marco" and "view_as" not in snap["identity"]


def _ws_validator():
    import json
    import warnings

    from jsonschema import Draft202012Validator, RefResolver

    from core.settings import ROOT

    schemas = ROOT / "contracts" / "schemas"
    store = {}
    for p in schemas.glob("*.schema.json"):
        doc = json.loads(p.read_text())
        store[p.name] = doc
        if doc.get("$id"):
            store[doc["$id"]] = doc
    root = store["ws_messages.schema.json"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resolver = RefResolver(base_uri=root.get("$id", "ws_messages.schema.json"), referrer=root, store=store)
    return Draft202012Validator({"$ref": "#/$defs/snapshot", "$defs": root["$defs"]}, resolver=resolver)


def test_snapshots_validate_against_contract() -> None:
    validator = _ws_validator()
    with TestClient(app) as client:
        for token in ("mt_marco_9Qe2vLx7Rk3pZ0aB", "mt_ana_0000000000000000", "mt_carmen_000000000000", "control"):
            with client.websocket_connect(f"/ws?village=v_reyes&m={token}") as ws:
                snap = _hello(ws, token)
                errors = sorted(validator.iter_errors(snap), key=lambda e: list(e.path))
                assert not errors, f"{token}: " + "; ".join(f"{list(e.path)}: {e.message[:160]}" for e in errors[:5])


def test_stale_client_gets_contract_mismatch() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws?m=m_marco") as ws:
            ws.send_json({"type": "hello", "contract_version": "1.2.0", "village": "v_reyes", "member_token": "mt_marco_9Qe2vLx7Rk3pZ0aB"})
            err = ws.receive_json()
            assert V != "1.2.0" and err["type"] == "error" and err["code"] == "contract_mismatch"
