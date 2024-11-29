
import os
from pathlib import Path

import pytest

# Add tests/ folder to $PATH so 'kubectl ...' invokes our mock
os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"

# Don't sys.exit on fatal errors; allows tests to verify exceptions
os.environ["KUBEQL_NEVER_EXIT"] = "true"


@pytest.fixture(scope="function")
def mockdir(tmp_path, monkeypatch):
    """Stores mock responses for use by ./kubectl"""
    monkeypatch.setenv("KUBEQL_MOCKDIR", str(tmp_path))
    yield tmp_path