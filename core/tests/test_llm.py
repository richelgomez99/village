from core.llm import LLMOff, llm, llm_status


def test_llm_off_stub_raises() -> None:
    client = llm("verifier")
    assert llm_status()["provider"] == "off"
    try:
        client.messages.create()
    except LLMOff:
        pass
    else:
        raise AssertionError("off client should raise")


def test_haiku_roles_get_haiku_model_on_bedrock(monkeypatch) -> None:
    import core.llm as mod
    from core.settings import Settings

    settings = Settings(VILLAGE_LLM="on", BEDROCK_SONNET_MODEL="sonnet-id", BEDROCK_HAIKU_MODEL="haiku-id", ANTHROPIC_API_KEY="k", ANTHROPIC_WORKSPACE_ID="")
    monkeypatch.setattr(mod, "get_settings", lambda: settings)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)

    class FakeBedrock:
        pass

    monkeypatch.setattr(mod.anthropic, "AnthropicBedrockMantle", FakeBedrock)
    assert mod.llm("haiku").village_model == "haiku-id"
    assert mod.llm("watcher").village_model == "haiku-id"
    sonnet = mod.llm("builder")
    assert sonnet.village_provider == "bedrock" and sonnet.village_model == "sonnet-id"  # no workspace id -> skip direct Anthropic
