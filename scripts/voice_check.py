from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.voice.outbound import ElevenLabsDialer, build_payload, member

FIXTURE = ROOT / "contracts" / "fixtures" / "scam_call_tool_requests.json"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def denied_report_request() -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text())
    return fixture["variants"]["denied"]["exchanges"][0]["request"]


async def post_fixture(core: str) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    secret = os.getenv("VILLAGE_TOOL_SECRET")
    if secret:
        headers["X-Village-Secret"] = secret
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{core.rstrip('/')}/tools/report_money_request",
            headers=headers,
            json=denied_report_request(),
        )
        response.raise_for_status()
        return response.json()


async def place_test_call() -> dict[str, Any]:
    target = os.getenv("TEST_CALL_TO")
    if not target:
        raise SystemExit("TEST_CALL_TO missing")
    marco = member("m_marco")
    if marco is None:
        raise SystemExit("m_marco missing from Reyes fixture")
    payload = build_payload(marco, "ver_1016_01")
    payload["to_number"] = target
    payload["agent_id"] = os.getenv("ELEVENLABS_CALLER_AGENT_ID") or os.getenv("ELEVENLABS_AGENT_CALLER_ID", "")
    payload["agent_phone_number_id"] = os.getenv("ELEVENLABS_PHONE_NUMBER_ID", "")
    payload["telephony_call_config"]["ringing_timeout_secs"] = 30
    return await ElevenLabsDialer().outbound_call(payload)


CARMEN_SIM_PROMPT = (
    "You are Carmen Reyes, 78, calling your family helper line in Spanish. Speak only Spanish, short sentences. "
    "Your first point: your son Marco just called you crying, he says he is in trouble and needs two thousand dollars in gift cards today. "
    "Say that clearly. Then listen. If the helper asks you to wait, say 'Sí, espero.' and wait. "
    "When the helper tells you what to do, say 'Gracias, no mando nada.' and say goodbye."
)
CARMEN_FIRST = "Hola Luz. Me llamó Marco llorando, dice que está en problemas y necesita dos mil dólares en tarjetas de regalo."
SIM_TAG = "[voice2-sim]"


def _api() -> httpx.Client:
    return httpx.Client(base_url="https://api.elevenlabs.io/v1", headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}, timeout=180)


def _sim_agent(c: httpx.Client, tunnel: str) -> tuple[str, list[str]]:
    """A throwaway copy of the mom line whose tools point at `tunnel` (your own Core), so the live Core never sees the test."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import deploy_elevenlabs as dep  # type: ignore

    os.environ["TUNNEL_URL"] = tunnel
    secret_id = dep.workspace_secret_id(c)
    ids: dict[str, str] = {}
    created: list[str] = []
    for name in ("report_money_request", "await_verification", "get_today", "log_dose", "screen_caller"):
        cfg = dep.tool_payload(dep.TOOL_CONFIGS / f"{name}.json", secret_id)
        cfg["description"] = f"{SIM_TAG} {cfg['description']}"
        tid = dep.call(c, "POST", "/convai/tools", json={"tool_config": cfg})["id"]
        ids[name] = tid
        created.append(tid)
    body = dep.agent_payload(dep.AGENTS_DIR / "agent_configs" / "mom-line.json", {**ids, **{n: ids.get(n, "") for n in ids}}, secret_id, None, dry=True)
    body["name"] = f"Luz {SIM_TAG}"
    body["conversation_config"]["agent"]["prompt"]["tool_ids"] = list(ids.values())
    body.get("platform_settings", {}).pop("workspace_overrides", None)
    agent_id = dep.call(c, "POST", "/convai/agents/create", json=body)["agent_id"]
    return agent_id, created


def _run_sim(c: httpx.Client, agent_id: str, mocks: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    spec: dict[str, Any] = {
        "simulated_user_config": {"first_message": CARMEN_FIRST, "language": "es", "prompt": {"prompt": CARMEN_SIM_PROMPT}},
        "dynamic_variables": {"system__conversation_id": f"sim_{os.getpid()}", "system__caller_id": "+15555550101", "system__call_duration_secs": "12", "village_id": "v_reyes",
                              "member_id": "m_carmen", "member_short_name": "Carmen", "on_duty_name": "Ana",
                              "coordinator_name": "Ana", "language": "es", "receptionist": "off", "caller_known": "true",
                              "greeting": "Hola, Carmen. Soy Luz, de la familia. ¿Cómo está?",
                              "today_summary": "Familia Reyes. Marco is the money verifier for requests claiming to be Marco. Use the gate-owned say text."},
    }
    if mocks:
        spec["tool_mock_config"] = {name: {"default_return_value": json.dumps(value, ensure_ascii=False), "default_is_error": False} for name, value in mocks.items()}
    r = c.post(f"/convai/agents/{agent_id}/simulate-conversation", json={"simulation_specification": spec, "new_turns_limit": 10})
    if r.status_code >= 400:
        raise RuntimeError(f"simulate-conversation {r.status_code}: {r.text[:800]}")
    return r.json().get("simulated_conversation", [])


def _calls(turns: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for t in turns:
        for tc in t.get("tool_calls") or []:
            try:
                params = json.loads(tc.get("params_as_json") or "{}")
            except Exception:
                params = {}
            out.append((tc.get("tool_name"), params))
    return out


def simulate(tunnel: str, core: str, keep: bool = False) -> dict[str, Any]:
    """Two passes, because simulate-conversation does not execute webhook tools (verified: no request reaches Core):
    pass 1: the agent decides which tools to call and with what params; those exact params are POSTed through the public
    tunnel to your Core (secret header included); Marco answers 'no' on his own device; pass 2: Core's real responses are
    the tool results, and we assert the agent speaks `say` verbatim."""
    import threading

    c = _api()
    agent_id, tools = _sim_agent(c, tunnel)
    try:
        first = _run_sim(c, agent_id)
        calls = _calls(first)
        headers = {"content-type": "application/json"}
        if os.getenv("VILLAGE_TOOL_SECRET"):
            headers["X-Village-Secret"] = os.environ["VILLAGE_TOOL_SECRET"]
        core_responses: dict[str, Any] = {}
        answered: dict[str, Any] = {}
        with httpx.Client(timeout=45) as http:
            system = {"conversation_id": f"sim_{os.getpid()}", "caller_id": "+15555550101", "call_secs": "12", "village_id": "v_reyes"}
            for name, params in calls:
                if name in core_responses or not (dep_tool := (ROOT / "agents" / "tool_configs" / f"{name}.json")).exists():
                    continue
                allowed = set(json.loads(dep_tool.read_text())["api_schema"]["request_body_schema"]["properties"])
                params = {k: v for k, v in {**system, **params}.items() if k in allowed}
                if name == "await_verification":
                    vid = (core_responses.get("report_money_request") or {}).get("data", {}).get("verification_id")
                    params = {**params, "verification_id": vid}
                    th = threading.Thread(target=lambda: answered.update(_answer_no(core, vid)), daemon=True)
                    th.start()
                r = http.post(f"{tunnel}/hooks/elevenlabs/tools/{name}", headers=headers, json=params)
                core_responses[name] = r.json() if r.status_code < 400 else {"error": r.status_code, "body": r.text[:200]}
        second = _run_sim(c, agent_id, {k: v for k, v in core_responses.items() if "say" in v})
    finally:
        if not keep:
            c.delete(f"/convai/agents/{agent_id}")
            for tid in tools:
                c.delete(f"/convai/tools/{tid}", params={"force": "true"})
    agent_lines = [t.get("message") or "" for t in second if t.get("role") == "agent"]
    spoken = " ".join(agent_lines)
    says = {k: v.get("say", "") for k, v in core_responses.items() if isinstance(v, dict)}
    import re as _re

    norm = lambda x: "".join(_re.sub(r"\[[^\]]*\]", "", str(x)).split())  # TTS transcripts split words and add [tags]
    verbatim = {k: bool(v) and norm(v) in norm(spoken) for k, v in says.items()}
    decisions = httpx.get(f"{core}/villages/v_reyes/decisions", params={"limit": 50}, timeout=5).json().get("decisions", [])
    return {
        "pass1_tool_calls": [{"tool": n, "params": p} for n, p in calls],
        "core_responses": core_responses,
        "marco_answer": answered,
        "pass2_tool_calls": [n for n, _ in _calls(second)],
        "pass2_agent_lines": agent_lines,
        "verbatim_spoken": verbatim,
        "core_decisions": [{k: d.get(k) for k in ("rule_id", "decision", "say_key", "kind", "tool") if k in d} for d in decisions][-6:],
        "ok": "report_money_request" in core_responses and "say" in core_responses.get("report_money_request", {}) and all(verbatim.values()) and bool(verbatim),
    }


def _answer_no(core: str, verification_id: str | None) -> dict[str, Any]:
    import time

    time.sleep(3)
    if not verification_id:
        return {}
    r = httpx.post(f"{core}/verifications/{verification_id}/answer", json={"verification_answer": "no", "via": "app_prompt"}, timeout=5)
    return {"verification_id": verification_id, "status": r.status_code}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Village voice path without placing calls by default.")
    parser.add_argument("--core", default="http://127.0.0.1:8787")
    parser.add_argument("--call", action="store_true", help="Place a real outbound verification call to TEST_CALL_TO. Do not use until Twilio geo-permissions are fixed.")
    parser.add_argument("--simulate", metavar="TUNNEL", help="ElevenLabs simulate-conversation: scripted Carmen says the Marco $2,000 line to a throwaway copy of the mom line whose tools hit TUNNEL (your own Core); asserts the tool call reached Core and the say was spoken verbatim.")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway sim agent/tools")
    args = parser.parse_args()

    load_env()
    if args.simulate:
        result = await asyncio.to_thread(simulate, args.simulate.rstrip("/"), args.core.rstrip("/"), args.keep)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    if args.call:
        result = await place_test_call()
        print(json.dumps({
            "conversation_id": result.get("conversation_id"),
            "call_sid": result.get("callSid"),
            "success": result.get("success", True),
        }, indent=2))
        return 0

    body = await post_fixture(args.core)
    print(body["say"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
