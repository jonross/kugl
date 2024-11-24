
import os
from pathlib import Path

# Add tests/ folder to $PATH so 'kubectl ...' invokes our mock
import pytest

os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"


@pytest.fixture(scope="function")
def mockdir(tmp_path, monkeypatch):
    """Stores mock responses for use by ./kubectl"""
    monkeypatch.setenv("KUBEQL_MOCKDIR", str(tmp_path))
    yield tmp_path