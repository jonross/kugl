
import os
from pathlib import Path

import pytest

from kugl.util import UNIT_TEST_TIMEBASE, kube_home, clock, KPath, kube_context

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
    # Suppress memoization
    kube_context.cache_clear()
    # Put all the folders where we find config data under the temp folder.
    monkeypatch.setenv("KUGL_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KUGL_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("KUGL_KUBE_HOME", str(tmp_path / "kube"))
    monkeypatch.setenv("KUGL_MOCKDIR", str(tmp_path / "results"))
    # Write a fake kubeconfig file so we don't have to mock it.
    # A specific unit test will test proper behavior when it's absent.
    # The other folders are Kugl-owned, so we should verify they're auto-created when appropriate.
    kube_home().prep().joinpath("config").write_text("current-context: nocontext")
    yield KPath(tmp_path)