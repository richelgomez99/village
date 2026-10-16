from types import SimpleNamespace


class FakeMessages:
    def __init__(self, fn):
        self.fn, self.calls = fn, []

    def create(self, **kw):
        self.calls.append(kw)
        name, args = self.fn(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=name, input=args)])


class FakeClient:
    """Stands in for core.llm.llm('haiku'): returns a canned tool call."""

    village_provider = "fake"
    village_model = "fake-haiku"

    def __init__(self, fn):
        self.messages = FakeMessages(fn)


class BoomClient:
    village_provider = "fake"

    class messages:  # noqa: N801
        @staticmethod
        def create(**kw):
            raise TimeoutError("model down")
