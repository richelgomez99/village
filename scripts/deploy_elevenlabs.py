"""Agents-as-code for the three ElevenLabs agents (mom-line, village-caller, setup) and their webhook tools.

    uv run python scripts/deploy_elevenlabs.py --pull            # live agents -> agents/live/*.json; merge live default dynamic vars
    uv run python scripts/deploy_elevenlabs.py --dry-run         # show what would be pushed (no secrets printed)
    uv run python scripts/deploy_elevenlabs.py                   # push tools + agents + verbatim-say procedures
    uv run python scripts/deploy_elevenlabs.py --only setup      # one agent
    uv run python scripts/deploy_elevenlabs.py --sync-secret     # VILLAGE_TOOL_SECRET: generate into .env if empty, set the workspace secret
    uv run python scripts/deploy_elevenlabs.py --init-webhook on # mom-line fetches dynamic vars from Core's init webhook
    uv run python scripts/deploy_elevenlabs.py --post-call-webhook  # workspace HMAC webhook -> ${TUNNEL_URL}/hooks/elevenlabs/post-call

`${TUNNEL_URL}` in tool/agent configs is replaced from .env at push time; `{"secret_ref": NAME}` / `{"env_var_label": NAME}`
headers become the workspace secret id. Secrets are never printed.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
TOOL_CONFIGS = AGENTS_DIR / "tool_configs"
TOOLS_JSON = AGENTS_DIR / "tools.json"
AGENTS_JSON = AGENTS_DIR / "agents.json"
LIVE_DIR = AGENTS_DIR / "live"
API = "https://api.elevenlabs.io/v1"
SECRET_NAME = "VILLAGE_TOOL_SECRET"
ENV_IDS = {"mom-line": "ELEVENLABS_AGENT_ID", "village-caller": "ELEVENLABS_AGENT_CALLER_ID", "setup": "ELEVENLABS_SETUP_AGENT_ID"}

PROCEDURES: dict[str, list[dict[str, str]]] = {
    "mom-line": [
        {
            "name": "Money check - verbatim say",
            "type": "free_form",
            "trigger": "When the caller says someone asked for money, gift cards, crypto, a transfer, cash pickup, or financial numbers.",
            "content": "\n".join([
                "1. Call the report_money_request tool immediately.",
                "2. Speak the tool response field `say` verbatim, with no extra safety wording.",
                "3. If `data.status` is `pending`, call await_verification with `data.verification_id` (it can take up to 30 seconds; stay silent while it runs).",
                "4. Speak the await_verification response field `say` verbatim.",
                "5. If either tool fails, say exactly: No pude confirmar con su familia. No mande dinero. Le aviso a Ana.",
            ]),
        },
        {
            "name": "Receptionist screen - verbatim say",
            "type": "free_form",
            "trigger": "Only when the dynamic variable receptionist is \"on\" and caller_known is \"false\", and the caller claims to be family or asks for money.",
            "content": "\n".join([
                "1. Call screen_caller with claimed_identity, utterance, asks_money and amount.",
                "2. Speak the returned `say` verbatim and nothing else.",
                "3. If screen_result is `hold` or verification_status is `pending`, call await_verification and speak its `say` verbatim.",
                "4. If screen_result is `refuse`, end the call after the line. If `pass_through`, continue normally.",
            ]),
        },
    ],
}


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value and not os.environ.get(key):
            os.environ[key] = value


def set_env_value(key: str, value: str) -> None:
    path = ROOT / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    out, seen = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n")
    os.environ[key] = value


def client() -> httpx.Client:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY missing")
    return httpx.Client(base_url=API, headers={"xi-api-key": key}, timeout=30)


def call(c: httpx.Client, method: str, path: str, **kw: Any) -> dict[str, Any]:
    r = c.request(method, path, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:600]}")
    return r.json() if r.content else {}


def tunnel() -> str:
    url = os.getenv("TUNNEL_URL", "").rstrip("/")
    if not url:
        raise SystemExit("TUNNEL_URL missing")
    return url


def substitute(value: Any, secret_id: str | None) -> Any:
    if isinstance(value, str):
        return value.replace("${TUNNEL_URL}", tunnel())
    if isinstance(value, list):
        return [substitute(v, secret_id) for v in value]
    if isinstance(value, dict):
        if set(value) in ({"secret_ref"}, {"env_var_label"}):
            return {"secret_id": secret_id} if secret_id else None
        out = {k: substitute(v, secret_id) for k, v in value.items() if not k.startswith("_")}
        return {k: v for k, v in out.items() if v is not None}
    return value


def transform_schema(schema: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"type": schema.get("type", "string")}
    for key in ("description", "dynamic_variable", "constant_value", "is_system_provided", "is_omitted", "enum"):
        if key in schema:
            out[key] = schema[key]
    if "properties" in schema:
        out["properties"] = {name: transform_schema(child) for name, child in schema["properties"].items()}
        out["required"] = schema.get("required", [])
    if "items" in schema:
        out["items"] = transform_schema(schema["items"])
    return out


def workspace_secret_id(c: httpx.Client) -> str | None:
    for s in call(c, "GET", "/convai/secrets").get("secrets", []):
        if s.get("name") == SECRET_NAME:
            return s.get("secret_id")
    return None


def sync_secret(c: httpx.Client) -> str:
    value = os.getenv(SECRET_NAME, "")
    if not value:
        value = secrets.token_urlsafe(32)
        set_env_value(SECRET_NAME, value)
        print(f"{SECRET_NAME}: generated into .env")
    sid = workspace_secret_id(c)
    if sid:
        call(c, "PATCH", f"/convai/secrets/{sid}", json={"type": "update", "name": SECRET_NAME, "value": value})
        print(f"{SECRET_NAME}: workspace secret {sid} updated")
    else:
        sid = call(c, "POST", "/convai/secrets", json={"type": "new", "name": SECRET_NAME, "value": value})["secret_id"]
        print(f"{SECRET_NAME}: workspace secret {sid} created")
    return sid


def tool_payload(path: Path, secret_id: str | None) -> dict[str, Any]:
    config = substitute(json.loads(path.read_text()), secret_id)
    api_schema = dict(config["api_schema"])
    api_schema["request_body_schema"] = transform_schema(api_schema["request_body_schema"])
    api_schema["content_type"] = "application/json"
    return {
        "api_schema": api_schema,
        "assignments": config.get("assignments", []),
        "description": config["description"],
        "disable_interruptions": config.get("disable_interruptions", False),
        "dynamic_variables": config.get("dynamic_variables", {"dynamic_variable_placeholders": {}}),
        "force_pre_tool_speech": config.get("force_pre_tool_speech", False),
        "name": config["name"],
        "response_timeout_secs": config.get("response_timeout_secs", 10),
        "type": "webhook",
    }


def upsert_tools(c: httpx.Client, secret_id: str | None, dry: bool) -> dict[str, str]:
    live = {t["tool_config"]["name"]: t["id"] for t in call(c, "GET", "/convai/tools").get("tools", []) if t.get("tool_config", {}).get("name")}
    ids = dict(live)
    for path in sorted(TOOL_CONFIGS.glob("*.json")):
        body = {"tool_config": tool_payload(path, secret_id)}
        name = body["tool_config"]["name"]
        url = body["tool_config"]["api_schema"]["url"]
        if dry:
            print(f"tool {name}: {'update' if name in live else 'create'} {url} timeout={body['tool_config']['response_timeout_secs']}s")
            continue
        if name in live:
            ids[name] = call(c, "PATCH", f"/convai/tools/{live[name]}", json=body)["id"]
        else:
            ids[name] = call(c, "POST", "/convai/tools", json=body)["id"]
        print(f"tool {name}: {ids[name]} -> {url}")
    if not dry:
        data = json.loads(TOOLS_JSON.read_text())
        for item in data["tools"]:
            item["id"] = ids.get(item["name"], item.get("id", ""))
        TOOLS_JSON.write_text(json.dumps(data, indent=2) + "\n")
    return ids


def agent_payload(path: Path, tool_ids: dict[str, str], secret_id: str | None, init_webhook: str | None, dry: bool = False) -> dict[str, Any]:
    config = substitute(json.loads(path.read_text()), secret_id)
    agent = config.get("conversation_config", {}).get("agent", {})
    agent.pop("language_presets", None)
    prompt = agent.get("prompt", {})
    prompt.pop("built_in_tools", None)  # keep the live built-ins (end_call, language_detection, ...)
    names = [t["name"] for t in prompt.pop("tools", [])]
    if names:
        missing = [n for n in names if n not in tool_ids]
        if missing and not dry:
            raise SystemExit(f"{path.name}: tools not deployed: {missing}")
        prompt["tool_ids"] = [tool_ids.get(n, f"<new:{n}>") for n in names]
    if init_webhook is not None and config.get("platform_settings", {}).get("workspace_overrides", {}).get("conversation_initiation_client_data_webhook"):
        config["platform_settings"].setdefault("overrides", {})["enable_conversation_initiation_client_data_from_webhook"] = init_webhook == "on"
    return config


def publish_procedures(agent_name: str, agent_id: str) -> None:
    procs = PROCEDURES.get(agent_name) or []
    if not procs:
        return

    def el(args: list[str], body: dict[str, Any] | None = None) -> dict[str, Any]:
        cmd = ["elevenlabs", *args, "--format", "json"] + (["--json", "-"] if body is not None else [])
        proc = subprocess.run(cmd, input=json.dumps(body) if body is not None else None, text=True, capture_output=True, cwd=ROOT)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
        return json.loads(proc.stdout or "{}")

    branch = el(["agents", "get", "--agent-id", agent_id])["main_branch_id"]
    existing = {p.get("name"): p for p in el(["agents", "procedures", "list", "--agent-id", agent_id, "--branch-id", branch]).get("procedures", [])}
    for body in procs:
        if body["name"] in existing:
            el(["agents", "procedures", "drafts", "update", "--agent-id", agent_id, "--branch-id", branch, "--procedure-id", existing[body["name"]]["procedure_id"]], body)
        else:
            el(["agents", "procedures", "create", "--agent-id", agent_id, "--branch-id", branch], body)
    el(["agents", "update", "--agent-id", agent_id, "--branch-id", branch, "--version-description", "voice2: verbatim-say procedures"])
    print(f"procedures {agent_name}: {', '.join(p['name'] for p in procs)} published")


def upsert_agents(c: httpx.Client, tool_ids: dict[str, str], secret_id: str | None, only: set[str], dry: bool, init_webhook: str | None) -> dict[str, str]:
    data = json.loads(AGENTS_JSON.read_text())
    ids: dict[str, str] = {}
    for item in data["agents"]:
        if only and item["name"] not in only:
            continue
        body = agent_payload(AGENTS_DIR / item["config"], tool_ids, secret_id, init_webhook, dry)
        agent_id = os.getenv(ENV_IDS.get(item["name"], ""), "") or item.get("id", "")
        if dry:
            agent = body["conversation_config"]["agent"]
            print(f"agent {item['name']} ({agent_id or 'new'}): tools={len(agent['prompt'].get('tool_ids', []))} vars={sorted(agent.get('dynamic_variables', {}).get('dynamic_variable_placeholders', {}))} webhook={body.get('platform_settings', {}).get('workspace_overrides', {}).get('conversation_initiation_client_data_webhook', {}).get('url')} overrides={body.get('platform_settings', {}).get('overrides')}")
            continue
        if agent_id:
            call(c, "PATCH", f"/convai/agents/{agent_id}", json=body)
        else:
            agent_id = call(c, "POST", "/convai/agents/create", json=body)["agent_id"]
        item["id"] = ids[item["name"]] = agent_id
        print(f"agent {item['name']}: {agent_id}")
        publish_procedures(item["name"], agent_id)
    if not dry:
        AGENTS_JSON.write_text(json.dumps(data, indent=2) + "\n")
    return ids


VOLATILE = ("agent_id", "version_id", "branch_id", "main_branch_id", "metadata", "phone_numbers", "whatsapp_accounts", "access_info", "access_permissions", "procedures", "trust_context")


def pull(c: httpx.Client) -> None:
    LIVE_DIR.mkdir(exist_ok=True)
    data = json.loads(AGENTS_JSON.read_text())
    for item in data["agents"]:
        agent_id = os.getenv(ENV_IDS.get(item["name"], ""), "") or item.get("id")
        live = call(c, "GET", f"/convai/agents/{agent_id}")
        snap = {k: v for k, v in live.items() if k not in VOLATILE}
        (LIVE_DIR / f"{item['name']}.json").write_text(json.dumps(snap, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
        path = AGENTS_DIR / item["config"]
        config = json.loads(path.read_text())
        live_vars = live["conversation_config"]["agent"].get("dynamic_variables", {}).get("dynamic_variable_placeholders", {})
        mine = config["conversation_config"]["agent"].setdefault("dynamic_variables", {}).setdefault("dynamic_variable_placeholders", {})
        added = [k for k in live_vars if k not in mine]
        for k in added:
            mine[k] = live_vars[k]
        path.write_text(json.dumps(config, indent=1, ensure_ascii=False) + "\n")
        print(f"pulled {item['name']} ({agent_id}) -> agents/live/{item['name']}.json; merged default vars {added or 'none new'}")


def post_call_webhook(c: httpx.Client) -> None:
    url = f"{tunnel()}/hooks/elevenlabs/post-call"
    settings = call(c, "GET", "/convai/settings")
    if settings.get("webhooks", {}).get("post_call_webhook_id"):
        print(f"post-call webhook already set: {settings['webhooks']['post_call_webhook_id']}")
        return
    made = call(c, "POST", "/workspace/webhooks", json={"settings": {"auth_type": "hmac", "name": "Village post-call", "webhook_url": url}})
    if made.get("webhook_secret"):
        set_env_value("ELEVENLABS_WEBHOOK_SECRET", made["webhook_secret"])
    call(c, "PATCH", "/convai/settings", json={"webhooks": {"post_call_webhook_id": made["webhook_id"], "events": ["transcript"], "send_audio": False}})
    print(f"post-call webhook {made['webhook_id']} -> {url} (HMAC secret written to .env as ELEVENLABS_WEBHOOK_SECRET)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="comma list: mom-line,village-caller,setup")
    ap.add_argument("--sync-secret", action="store_true")
    ap.add_argument("--init-webhook", choices=["on", "off"])
    ap.add_argument("--post-call-webhook", action="store_true")
    ap.add_argument("--no-tools", action="store_true")
    args = ap.parse_args(argv)
    load_env()
    c = client()
    if args.pull:
        pull(c)
        return 0
    if args.post_call_webhook:
        post_call_webhook(c)
        return 0
    secret_id = sync_secret(c) if args.sync_secret and not args.dry_run else workspace_secret_id(c)
    if args.no_tools:
        tool_ids = {t["tool_config"]["name"]: t["id"] for t in call(c, "GET", "/convai/tools").get("tools", [])}
    else:
        tool_ids = upsert_tools(c, secret_id, args.dry_run)
    upsert_agents(c, tool_ids, secret_id, {s for s in args.only.split(",") if s}, args.dry_run, args.init_webhook)
    return 0


if __name__ == "__main__":
    sys.exit(main())
