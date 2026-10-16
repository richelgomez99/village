import copy
import json
from pathlib import Path

import pytest

from core.release.receipts import ReceiptStore
from core.release.serve import LocalPublisher

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def spec():
    return copy.deepcopy(json.loads((ROOT / "contracts/fixtures/reyes_spec.json").read_text()))


@pytest.fixture
def publisher(tmp_path):
    return LocalPublisher(tmp_path / "releases")


@pytest.fixture
def store(tmp_path):
    return ReceiptStore(tmp_path / "receipts")
