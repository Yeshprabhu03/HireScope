import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def eval_dataset():
    path = Path(__file__).parents[1] / "data" / "evaluation_cases.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))
