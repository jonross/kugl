
from copy import deepcopy
import os
from pathlib import Path
from typing import Union

import pytest
import yaml

from kugl.util import UNIT_TEST_TIMEBASE, kube_home, clock, KPath, kube_context, kugl_home

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


class HRData:
    """A utility class with simple schema configuration and data for unit tests."""

    CONFIG = yaml.safe_load("""
        resources: 
          - name: people
            # Start this out as a data resource; a unit test can turn it into another
            # kind of resource.
            data:
              items:
                - name: Jim
                  age: 42
                - name: Jill
                  age: 43
        create:
          - table: people
            resource: people
            columns:
              - name: name
                path: name
              - name: age
                path: age
                type: integer
    """)

    def config(self):
        """Return a deepcopy of the default HR configuration, for customization in a test."""
        return deepcopy(self.CONFIG)

    def save(self, config: Union[str, dict] = CONFIG):
        """Write a (possibly modified) HR schema configuration to KUGL_HOME."""
        if not isinstance(config, str):
            config = yaml.dump(config)
        kugl_home().prep().joinpath("hr.yaml").write_text(config)


@pytest.fixture(scope="function")
def hr(test_home):
    return HRData()