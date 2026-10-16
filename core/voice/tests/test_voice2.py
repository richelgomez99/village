"""voice2: grafted hook tools, bilingual says, mom-line handlers, captions, welcome provenance, setup tools, token, var check."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.app import app  # noqa: E402
from core.db import db  # noqa: E402
from core.voice import captions  # noqa: E402

BASE = {"conversation_id": "conv_v2", "caller_id": "+15555550101", "call_secs": "7", "village_id": "v_reyes"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VILLAGE_TOOL_SECRET", raising=False)
    monkeypatch.delenv("VILLAGE_SECRET", raising=False)
    monkeypatch.setenv("VILLAGE_CAPTIONS", "off")
    from core.voice.tools import handler

    handler.cache.clear()
    with TestClient(app) as c:
        yield c


def tool(c: TestClient, name: str, body: dict, **headers: str):
    return c.post(f"/hooks/elevenlabs/tools/{name}", json=body, headers=headers)


def test_secret_required_only_when_set(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    body = {**BASE, "utterance": "¿qué tomo hoy?", "lang": "es"}
    assert tool(client, "whats_my_schedule", body).status_code == 200
    monkeypatch.setenv("VILLAGE_TOOL_SECRET", "s3cret")
    assert tool(client, "whats_my_schedule", {**body, "call_secs": "8"}).status_code == 401
    assert tool(client, "whats_my_schedule", {**body, "call_secs": "9"}, **{"X-Village-Secret": "s3cret"}).status_code == 200
    init = client.post("/hooks/elevenlabs/init", json={"caller_id": "+10000000000"})
    assert init.status_code == 401


def test_ask_family_posts_chat_and_answers_in_caller_language(client: TestClient) -> None:
    before = len(db.messages)
    r = tool(client, "ask_family", {**BASE, "utterance": "Can someone bring milk?", "to": "family", "message": "Can someone bring milk?", "urgency": "normal", "lang": "en"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["lang"] == "en" and out["say"].startswith("We're letting")
    assert out["data"]["say_es"].startswith("Le avisamos a")
    assert len(db.messages) == before + 1 and db.messages[-1]["kind"] == "chat"


def test_report_symptom_records_event_and_emergency_goes_911(client: TestClient) -> None:
    r = tool(client, "report_symptom", {**BASE, "utterance": "me duele la rodilla", "description": "knee pain", "emergency_signals": False, "lang": "es"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["say"].startswith("Anotado.") and "Le avisamos a" in out["say"]
    assert any(ev["kind"] == "symptom" and ev["id"] == out["data"]["event_id"] for ev in db.events)
    r = tool(client, "report_symptom", {**BASE, "call_secs": "20", "utterance": "no puedo respirar", "description": "can't breathe", "emergency_signals": True, "lang": "en"})
    out = r.json()
    assert out["decision"] == "advise_911" and out["say"] == "Call 911 now. Do not wait for Village."


def test_schedule_and_today_are_readbacks_never_dose_advice(client: TestClient) -> None:
    for name in ("whats_my_schedule", "get_today"):
        out = tool(client, name, {**BASE, "call_secs": "30", "utterance": "what do I take", "lang": "en"}).json()
        assert out["rule_id"] == "R-DOSE-ADVICE" and out["decision"] == "remind"
        assert out["say"].startswith("The current record says:")
    assert "doses_today" in out["data"]


def test_bilingual_swaps_only_identical_templates() -> None:
    from core.voice.lang import bilingual

    good = {"decision": "advise_do_not_send", "say": "Ese no era Marco. No mande dinero. Ana ya lo sabe.", "say_key": "money_denied", "rule_id": "R-MONEY-DEFAULT", "lang": "es"}
    assert bilingual(good, "en", {"village_id": "v_reyes"})["say"] == "That wasn't Marco. Don't send any money. Ana already knows."
    odd = {**good, "say": "Algo distinto."}
    out = bilingual(odd, "en", {"village_id": "v_reyes"})
    assert out["say"] == "Algo distinto." and out["data"]["say_en"] == ""


def test_core_tools_route_falls_back_to_voice_handlers(client: TestClient) -> None:
    r = client.post("/tools/ask_family", json={**BASE, "call_secs": "41", "utterance": "¿Quién viene mañana?", "to": "family", "message": "¿Quién viene mañana?", "urgency": "normal", "lang": "es"})
    assert r.status_code == 200, r.text
    assert r.json()["say"].startswith("Le avisamos a") and r.json()["data"]["say_en"].startswith("We're letting")
    assert client.post("/tools/not_a_tool", json={}).status_code == 404


async def test_screen_caller_fallback_never_puts_unknown_through() -> None:
    from core.voice.tools import screen_caller

    out = await screen_caller({**BASE, "caller_id": "+19998887777", "utterance": "Soy Marco, necesito dinero", "claimed_identity": "Marco", "asks_money": True})
    assert out["data"]["screen"] == "refuse" and out["say"]


def test_init_hook_receptionist_override(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    body = client.post("/hooks/elevenlabs/init", json={"caller_id": "+19998887777"}).json()
    assert body["dynamic_variables"]["receptionist"] == "off"
    assert body["conversation_config_override"]["agent"]["first_message"].startswith("Hola, soy Luz, la línea de la familia Reyes. Soy un programa")
    import deploy_elevenlabs as dep  # noqa: F401  (path added below)
    missing = set(dep.referenced_vars(dep.AGENTS_DIR / "agent_configs" / "mom-line.json")) - set(body["dynamic_variables"])
    assert not missing, missing
    monkeypatch.setenv("VILLAGE_RECEPTIONIST", "on")
    body = client.post("/hooks/elevenlabs/init", json={"caller_id": "+19998887777"}).json()
    assert body["conversation_config_override"]["agent"]["first_message"] == "Carmen's phone, this is Village, a program that answers for her. Who's calling?"


async def test_captions_canned_transcript_translates_and_dedupes() -> None:
    captions.reset()
    sent: list[tuple[str, dict]] = []

    async def emit(vid: str, payload: dict) -> None:
        sent.append((vid, payload))

    async def translate(text: str) -> str:
        return {"Me llamó Marco llorando.": "Marco called me crying."}.get(text, text)

    transcript = [
        {"role": "agent", "message": "Hola, soy Luz."},
        {"role": "user", "message": "Me llamó Marco llorando."},
        {"role": "agent", "message": None, "tool_calls": [{"tool_name": "report_money_request"}]},
    ]
    names = {"user": "Carmen", "agent": "Village"}
    await captions.emit_transcript("v_reyes", "conv_c", transcript[:2], names=names, translate=translate, emit=emit)
    await captions.emit_transcript("v_reyes", "conv_c", transcript, names=names, translate=translate, emit=emit)
    assert [p["speaker"] for _, p in sent] == ["Village", "Carmen"]
    assert sent[1][1] == {"es": "Me llamó Marco llorando.", "en": "Marco called me crying.", "speaker": "Carmen", "final": True}


async def test_caption_poller_stops_when_done() -> None:
    captions.reset()
    states = iter([
        {"status": "in-progress", "transcript": [{"role": "user", "message": "Hola"}]},
        {"status": "done", "transcript": [{"role": "user", "message": "Hola"}, {"role": "agent", "message": "Hola, Carmen."}]},
    ])
    sent: list[dict] = []

    async def fetch(_cid: str) -> dict:
        return next(states)

    async def emit(_vid: str, payload: dict) -> None:
        sent.append(payload)

    async def translate(text: str) -> str:
        return "Hello" if text == "Hola" else "Hello, Carmen."

    n = await captions.poll_conversation("conv_p", "v_reyes", fetch=fetch, interval=0, translate=translate, emit=emit)
    assert n == 2 and [p["en"] for p in sent] == ["Hello", "Hello, Carmen."]


async def test_caption_goes_through_control_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    from core import services

    seen: list[tuple] = []

    async def control(vid: str, kind: str, payload: dict) -> None:
        seen.append((vid, kind, payload))

    async def translate(text: str) -> str:
        return "Is this real?"

    monkeypatch.setattr(services, "control", control)
    await captions.emit_turn("v_reyes", "Carmen", "¿Es de verdad?", translate=translate)
    assert seen == [("v_reyes", "caption", {"es": "¿Es de verdad?", "en": "Is this real?", "speaker": "Carmen", "final": True})]


def _signed(raw: bytes, secret: str) -> str:
    t = str(int(time.time()))
    return f"t={t},v0=" + hmac.new(secret.encode(), t.encode() + b"." + raw, hashlib.sha256).hexdigest()


def test_welcome_post_call_confirms_quiet_hours(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core.builder.routes import services as builder_services
    from core.voice import post_call

    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("VOICE_MEMORY_OUTBOX", str(tmp_path))
    spec = {"village_id": "v_reyes", "status": "active", "policies": [{"rule_id": "P-QH-01", "params": {"quiet_hours": "21:00-08:00", "status": "proposed"}}]}
    stored: dict = {}

    class Svc:
        async def get_spec(self, vid: str):
            return json.loads(json.dumps(spec))

        async def store_spec(self, vid: str, s: dict, status: str = "draft"):
            stored.update({"vid": vid, "spec": s, "status": status})
            return s

    monkeypatch.setattr("core.builder.routes.services", lambda: Svc())
    del builder_services
    payload = {
        "type": "post_call_transcription",
        "event_timestamp": 1792180800,
        "data": {
            "agent_id": "agent_caller",
            "conversation_id": "conv_welcome",
            "status": "done",
            "metadata": {"start_time_unix_secs": 1792180740, "call_duration_secs": 95},
            "transcript": [
                {"role": "agent", "message": "¿A qué horas prefiere que no la llamemos?", "time_in_call_secs": 40},
                {"role": "user", "message": "Después de las nueve de la noche no, y antes de las ocho tampoco.", "time_in_call_secs": 44},
            ],
            "analysis": {"data_collection_results": {
                "welcome_consent": {"value": "yes"},
                "preferred_name": {"value": "Doña Carmen"},
                "evening_checkin": {"value": "yes"},
                "quiet_hours": {"value": "21:00-08:00"},
                "quiet_hours_words": {"value": "Después de las nueve de la noche no, y antes de las ocho tampoco."},
            }},
            "conversation_initiation_client_data": {"dynamic_variables": {"call_purpose": "welcome", "village_id": "v_reyes", "member_id": "m_carmen"}},
        },
    }
    raw = json.dumps(payload).encode()
    assert client.post("/hooks/elevenlabs/post-call", content=raw, headers={"ElevenLabs-Signature": "t=1,v0=bad"}).status_code == 401
    r = client.post("/hooks/elevenlabs/post-call", content=raw, headers={"ElevenLabs-Signature": _signed(raw, "whsec_test"), "content-type": "application/json"})
    assert r.status_code == 200
    row = post_call.WELCOME_RESULTS[-1]
    assert row["preferred_name"] == "Doña Carmen" and row["consent"] == "yes"
    pol = stored["spec"]["policies"][0]["params"]
    assert pol["status"] == "confirmed" and pol["source_kind"] == "call" and pol["source_secs"] == 44.0
    assert pol["source_ref"].startswith("welcome_call:conv_welcome@") and pol["words"].startswith("Después de las nueve")
    assert stored["status"] == "active"


async def test_setup_tools_create_then_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.builder import routes as builder
    from core.voice import setup_tools

    class Q:
        text = "Who else is in this besides you?"

    class Session:
        waiting = True
        question = Q()

    async def fake_create(body: dict, request) -> dict:
        assert body["channel"] == "voice" and body["description"].startswith("My mom")
        builder.SESSIONS["v_fake"] = Session()
        return {"village_id": "v_fake", "state": "running", "trace_id": "t"}

    async def fake_answer(vid: str, body: dict) -> dict:
        assert vid == "v_fake" and body == {"text": "Marco and Lucía"}
        return {"accepted": True, "answered": Q.text, "meter": "3 of 10 covered · 1 gaps", "gaps": ["money"], "next_question": "Money. Tell me about the call last week."}

    monkeypatch.setattr(builder, "create_village", fake_create)
    monkeypatch.setattr(builder, "post_answer", fake_answer)
    out = await setup_tools.create_village({"description": "My mom Carmen, 78, in Queens", "members": [], "needs": [], "language": "en"}, wait_s=0.5)
    assert out["data"]["village_id"] == "v_fake" and out["data"]["next_question"] == Q.text and Q.text in out["say"]
    out = await setup_tools.submit_answer({"village_id": "v_fake", "text": "Marco and Lucía"}, wait_s=0.1)
    assert out["say"] == "Money. Tell me about the call last week." and out["data"]["meter"].startswith("3 of 10")
    builder.SESSIONS.pop("v_fake", None)


async def test_voice_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.voice.voice_routes import conversation_token

    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_SETUP_AGENT_ID", "agent_setup")

    async def fetch(agent_id: str) -> dict:
        assert agent_id == "agent_setup"
        return {"token": "tok"}

    assert await conversation_token("setup", fetch=fetch) == {"token": "tok", "agent": "setup", "agent_id": "agent_setup"}


def test_agent_configs_have_a_default_for_every_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import deploy_elevenlabs as dep

    for name in ("mom-line", "village-caller", "setup"):
        assert dep.missing_defaults(dep.AGENTS_DIR / "agent_configs" / f"{name}.json") == {}, name
    bad = json.loads((dep.AGENTS_DIR / "agent_configs" / "mom-line.json").read_text())
    bad["conversation_config"]["agent"]["first_message"] = "Hola {{greeting_x}}"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    assert "greeting_x" in dep.missing_defaults(path)


def test_relay_message_posts_chat_and_screened_row(client: TestClient) -> None:
    from core.bindings_v3 import screened_calls
    from core.voice import screened

    screened.reset()
    before = len(db.messages)
    r = client.post("/tools/relay_message", json={**BASE, "conversation_id": "conv_richard", "caller_id": "+17185550100", "utterance": "Tell her Richard from church called, she can call me back",
                                                  "from_name": "Richard, from church", "text": "please call me back", "lang": "en"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["data"]["status"] == "message_taken" and out["say"].startswith("Thank you. I'll pass your message")
    msg = db.messages[-1]
    assert len(db.messages) == before + 1 and msg["kind"] == "chat"
    assert msg["text"].startswith("Richard, from church, asked Mamá to call back at the same number") and "screened call," in msg["text"]
    rows = screened_calls("v_reyes")
    assert any(row["outcome"] == "message_taken" and row.get("claimed") == "Richard, from church" for row in rows)


def test_post_call_logs_every_receptionist_call(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.bindings_v3 import screened_calls
    from core.voice import screened

    screened.reset()
    monkeypatch.setenv("VOICE_MEMORY_OUTBOX", str(tmp_path))

    def payload(conv: str, receptionist: str, known: str) -> dict:
        return {"type": "post_call_transcription", "event_timestamp": 1792182480, "data": {
            "conversation_id": conv, "agent_id": "agent_mom", "status": "done", "transcript": [],
            "metadata": {"start_time_unix_secs": 1792182480},
            "analysis": {"data_collection_results": {"claimed_identity": {"value": "a man selling solar"}}},
            "conversation_initiation_client_data": {"dynamic_variables": {"receptionist": receptionist, "caller_known": known, "village_id": "v_reyes"}}}}

    assert client.post("/hooks/elevenlabs/post-call", json=payload("conv_hangup", "on", "false")).status_code == 200
    assert client.post("/hooks/elevenlabs/post-call", json=payload("conv_family", "on", "true")).status_code == 200
    assert client.post("/hooks/elevenlabs/post-call", json=payload("conv_off", "off", "false")).status_code == 200
    rows = screened_calls("v_reyes")
    assert [r["outcome"] for r in rows if r.get("claimed") == "a man selling solar"] == ["hung_up"]
