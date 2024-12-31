
import os
from pathlib import Path

import pytest

from kugl.util import UNIT_TEST_TIMEBASE, kube_home, clock, KPath

# Add tests/ folder to $PATH so running 'kubectl ...' invokes our mock, not the real kubectl.
os.environ["PATH"] = f"{Path(__file__).parent}:{os.environ['PATH']}"

# Some behaviors have to change in tests, sorry
os.environ["KUGL_UNIT_TESTING"] = "true"


def pytest_sessionstart(session):
    # Tell Pytest where there are assertions in files that aren't named "test_*"
    pytest.register_assert_rewrite("tests.testing")
    # Use a clock we can control, in place of system time.
    clock.simulate_time()
    clock.CLOCK.set(UNIT_TEST_TIMEBASE)


@pytest.fixture(scope="function")
def test_home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUGL_HOME", str(tmp_path))
    monkeypatch.setenv("KUGL_MOCKDIR", str(tmp_path / "cache"))
    kube_home().mkdir()
    kube_home().joinpath("config").write_text("current-context: nocontext")
    yield KPath(tmp_path)