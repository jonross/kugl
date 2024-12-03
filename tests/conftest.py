
import os
from pathlib import Path

import pytest

# Add tests/ folder to $PATH so 'kubectl ...' invokes our mock
os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"

# Some behaviors have to change in tests, sorry
os.environ["KUGEL_UNIT_TESTING"] = "true"


@pytest.fixture(scope="function")
def mockdir(tmp_path, monkeypatch):
    """Stores mock responses for use by ./kubectl"""
    monkeypatch.setenv("KUGEL_MOCKDIR", str(tmp_path))
    yield tmp_path