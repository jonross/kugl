
import os
from pathlib import Path

import pytest

import kugel.time as ktime
from kugel.constants import UNIT_TEST_TIMEBASE
from kugel.utils import kube_home

# Add tests/ folder to $PATH so running 'kubectl ...' invokes our mock, not the real kubectl.
os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"

# Some behaviors have to change in tests, sorry
os.environ["KUGEL_UNIT_TESTING"] = "true"


def pytest_sessionstart(session):
    # Tell Pytest where there are assertions in files that aren't named "test_*"
    pytest.register_assert_rewrite("tests.testing")
    # Use a clock we can control, in place of system time.
    ktime.simulate_time()
    ktime.CLOCK.set(UNIT_TEST_TIMEBASE)


@pytest.fixture(scope="function")
def test_home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUGEL_HOME", tmp_path)
    monkeypatch.setenv("KUGEL_MOCKDIR", str(tmp_path / "cache"))
    kube_home().mkdir()
    kube_home().joinpath("config").write_text("current-context: nocontext")
    yield tmp_path