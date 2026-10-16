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
