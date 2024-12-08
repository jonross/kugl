
import os
from pathlib import Path

import pytest

# Add tests/ folder to $PATH so 'kubectl ...' invokes our mock
from kugel.utils import kube_home

os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"

# Some behaviors have to change in tests, sorry
os.environ["KUGEL_UNIT_TESTING"] = "true"


def pytest_sessionstart(session):
    # Tell Pytest where there are assertions in files that aren't named "test_*"
    pytest.register_assert_rewrite("tests.testing")


@pytest.fixture(scope="function")
def test_home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUGEL_HOME", tmp_path)
    monkeypatch.setenv("KUGEL_MOCKDIR", str(tmp_path / "cache"))
    kube_home().mkdir()
    kube_home().joinpath("config").write_text("current-context: nocontext")
    yield tmp_path