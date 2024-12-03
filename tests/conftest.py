
import os
from pathlib import Path

import pytest

# Add tests/ folder to $PATH so 'kubectl ...' invokes our mock
os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"

# Some behaviors have to change in tests, sorry
os.environ["KUGEL_UNIT_TESTING"] = "true"


@pytest.fixture(scope="function")
def test_home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUGEL_HOME", tmp_path)
    monkeypatch.setenv("KUGEL_MOCKDIR", str(tmp_path / "mocks"))
    yield tmp_path