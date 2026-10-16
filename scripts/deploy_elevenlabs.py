from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
TOOL_CONFIGS = AGENTS_DIR / "tool_configs"
TOOLS_JSON = AGENTS_DIR / "tools.json"
AGENTS_JSON = AGENTS_DIR / "agents.json"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def run_json(args: list[str], input_json: dict[str, Any] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        input=json.dumps(input_json) if input_json is not None else None,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return json.loads(proc.stdout)


def el(args: list[str], body: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["elevenlabs", *args, "--format", "json"]
    if body is not None:
        command.extend(["--json", "-"])
    return run_json(command, body)


def transform_schema(schema: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"type": schema.get("type", "string")}
    if "description" in schema:
        out["description"] = schema["description"]
    if "dynamic_variable" in schema:
        out["dynamic_variable"] = schema["dynamic_variable"]
    if "constant_value" in schema:
        out["constant_value"] = schema["constant_value"]
    if "is_system_provided" in schema:
        out["is_system_provided"] = schema["is_system_provided"]
    if "is_omitted" in schema:
        out["is_omitted"] = schema["is_omitted"]
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if "properties" in schema:
        out["properties"] = {
            name: transform_schema(child)
            for name, child in schema["properties"].items()
        }
        out["required"] = schema.get("required", [])
    if "items" in schema:
        out["items"] = transform_schema(schema["items"])
    return out


def secret_id_for(name: str) -> str | None:
    data = el(["agents", "secrets", "list"])
    for secret in data.get("secrets", []):
        if secret.get("name") == name:
            return secret.get("secret_id")
    return None


def api_tool_config(path: Path, village_secret_id: str | None) -> dict[str, Any]:
    config = json.loads(path.read_text())
    api_schema = dict(config["api_schema"])
    api_schema["request_body_schema"] = transform_schema(api_schema["request_body_schema"])
    api_schema["content_type"] = "application/json"
    if village_secret_id:
        api_schema["request_headers"] = {
            **api_schema.get("request_headers", {}),
            "X-Village-Secret": {"secret_id": village_secret_id},
        }
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


def existing_tools_by_name() -> dict[str, str]:
    data = el(["agents", "tools", "list"])
    tools = data.get("tools", [])
    return {
        tool["tool_config"]["name"]: tool["id"]
        for tool in tools
        if tool.get("tool_config", {}).get("name")
    }


def upsert_tools() -> dict[str, str]:
    ids = existing_tools_by_name()
    village_secret_id = secret_id_for("VILLAGE_TOOL_SECRET")
    for path in sorted(TOOL_CONFIGS.glob("*.json")):
        config = api_tool_config(path, village_secret_id)
        body = {"tool_config": config}
        if config["name"] in ids:
            response = el([
                "agents",
                "tools",
                "update",
                "--tool-id",
                ids[config["name"]],
            ], body)
        else:
            response = el(["agents", "tools", "create"], body)
        ids[config["name"]] = response["id"]
        print(f"{config['name']}: {response['id']}")
    return ids


def update_tools_json(ids: dict[str, str]) -> None:
    data = json.loads(TOOLS_JSON.read_text())
    for item in data["tools"]:
        if item["name"] in ids:
            item["id"] = ids[item["name"]]
    TOOLS_JSON.write_text(json.dumps(data, indent=2) + "\n")


def tool_ids_by_name() -> dict[str, str]:
    return {
        item["name"]: item["id"]
        for item in json.loads(TOOLS_JSON.read_text())["tools"]
    }


def api_agent_config(path: Path, village_secret_id: str | None) -> dict[str, Any]:
    config = json.loads(path.read_text())
    ids = tool_ids_by_name()
    agent = config.get("conversation_config", {}).get("agent", {})
    agent.pop("language_presets", None)
    agent.pop("dynamic_variables", None)
    prompt = agent.get("prompt", {})
    # The project config uses CLI shorthand for built-ins; the create/update API
    # expects a richer shape. Omit them here; the prompt still instructs ending.
    prompt.pop("built_in_tools", None)
    tool_names = [tool["name"] for tool in prompt.pop("tools", [])]
    if tool_names:
        prompt["tool_ids"] = [ids[name] for name in tool_names]
    webhook = config.get("platform_settings", {}).get("workspace_overrides", {}).get("conversation_initiation_client_data_webhook")
    if webhook and village_secret_id:
        webhook["request_headers"] = {"X-Village-Secret": {"secret_id": village_secret_id}}
    return config


def existing_agents_by_name() -> dict[str, str]:
    data = el(["agents", "list"])
    return {
        agent["name"]: agent["agent_id"]
        for agent in data.get("agents", [])
        if agent.get("name") and agent.get("agent_id")
    }


def upsert_agents() -> dict[str, str]:
    existing = existing_agents_by_name()
    ids: dict[str, str] = {}
    data = json.loads(AGENTS_JSON.read_text())
    village_secret_id = secret_id_for("VILLAGE_TOOL_SECRET")
    for item in data["agents"]:
        config = api_agent_config(AGENTS_DIR / item["config"], village_secret_id)
        if config["name"] in existing:
            response = el([
                "agents",
                "update",
                "--agent-id",
                existing[config["name"]],
            ], config)
        else:
            response = el(["agents", "create"], config)
        agent_id = response.get("agent_id") or response.get("id") or existing.get(config["name"])
        if not agent_id:
            raise RuntimeError(f"missing agent id for {config['name']}")
        item["id"] = agent_id
        ids[item["name"]] = agent_id
        print(f"{item['name']}: {agent_id}")
    AGENTS_JSON.write_text(json.dumps(data, indent=2) + "\n")
    return ids


def update_env(ids: dict[str, str]) -> None:
    path = ROOT / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    updates = {
        "ELEVENLABS_AGENT_ID": ids.get("mom-line", ""),
        "ELEVENLABS_CALLER_AGENT_ID": ids.get("village-caller", ""),
        "ELEVENLABS_AGENT_SETUP_ID": ids.get("setup", ""),
    }
    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key = line.split("=", 1)[0]
            if key in updates and updates[key]:
                new_lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        new_lines.append(line)
    for key, value in updates.items():
        if value and key not in seen:
            new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines).rstrip() + "\n")


def agent_main_branch(agent_id: str) -> str:
    data = el(["agents", "get", "--agent-id", agent_id])
    branch_id = data.get("main_branch_id")
    if not branch_id:
        raise RuntimeError("agent main_branch_id missing")
    return branch_id


def publish_money_procedure(agent_id: str) -> None:
    branch_id = agent_main_branch(agent_id)
    content = "\n".join([
        "1. Call the report_money_request tool immediately.",
        "2. Speak the tool response field `say` verbatim, with no extra safety wording.",
        "3. If `data.status` is `pending`, call await_verification with `data.verification_id`.",
        "4. Speak the await_verification response field `say` verbatim.",
        "5. If either tool fails, say exactly: No pude confirmar con su familia. No mande dinero. Le aviso a Ana.",
    ])
    body = {
        "name": "Money check - verbatim say",
        "type": "free_form",
        "trigger": "When the caller says someone asked for money, gift cards, crypto, a transfer, cash pickup, or financial numbers.",
        "content": content,
    }
    procedures = el(["agents", "procedures", "list", "--agent-id", agent_id, "--branch-id", branch_id])
    existing = next((p for p in procedures.get("procedures", []) if p.get("name") == body["name"]), None)
    if existing:
        el([
            "agents",
            "procedures",
            "drafts",
            "update",
            "--agent-id",
            agent_id,
            "--branch-id",
            branch_id,
            "--procedure-id",
            existing["procedure_id"],
        ], body)
    else:
        el(["agents", "procedures", "create", "--agent-id", agent_id, "--branch-id", branch_id], body)
    el([
        "agents",
        "update",
        "--agent-id",
        agent_id,
        "--branch-id",
        branch_id,
        "--version-description",
        "Publish money check verbatim-say procedure",
    ])
    print("money procedure published")


def attach_phone(agent_id: str) -> None:
    phone_id = os.getenv("ELEVENLABS_PHONE_NUMBER_ID")
    if not phone_id:
        print("ELEVENLABS_PHONE_NUMBER_ID missing; phone not attached")
        return
    el([
        "agents",
        "phone-numbers",
        "update",
        "--phone-number-id",
        phone_id,
    ], {"agent_id": agent_id})
    print("phone number attached")


def main() -> int:
    load_env()
    if not os.getenv("ELEVENLABS_API_KEY"):
        raise SystemExit("ELEVENLABS_API_KEY missing")
    ids = upsert_tools()
    update_tools_json(ids)
    agent_ids = upsert_agents()
    update_env(agent_ids)
    publish_money_procedure(agent_ids["mom-line"])
    attach_phone(agent_ids["mom-line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
