import pytest

from core.memory.client import MemoryClient
from core.memory.fake import FakeAgentMemory


@pytest.fixture
def fake():
    return FakeAgentMemory()


@pytest.fixture
def client(fake):
    return MemoryClient("https://am.test", "ctx_test", "sp-test", transport=fake.transport())
