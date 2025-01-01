"""
Assorted tests for various edge cases and error conditions.
Some of these are just to achieve 100% coverage.
"""

import os
from pathlib import Path

import pytest

from kugl.builtins.helpers import Limits
from kugl.main import main1
from kugl.util import Age, KuglError, kube_home, kugl_home


def test_no_resources():
    assert Limits.extract(None) == Limits(None, None, None)


def test_kube_home_missing(test_home, tmp_path):
    os.environ["KUGL_HOME"] = str(tmp_path / "doesnt_exist")
    with pytest.raises(KuglError, match="can't determine current context"):
        main1(["select 1"])


def test_no_kube_context(test_home, tmp_path):
    kube_home().joinpath("config").write_text("")
    with pytest.raises(KuglError, match="No current context"):
        main1(["select 1"])


def test_enforce_mockdir(test_home, monkeypatch):
    monkeypatch.delenv("KUGL_MOCKDIR")
    with pytest.raises(SystemExit, match="Unit test state error"):
        main1(["select 1"])


def test_kube_home_without_envar(monkeypatch):
    monkeypatch.setenv("KUGL_HOME", "xxx")  # must exist before deleting
    monkeypatch.delenv("KUGL_HOME")
    assert kube_home() == Path.home() / ".kube"


def test_kugl_home_without_envar(monkeypatch):
    monkeypatch.setenv("KUGL_HOME", "xxx")  # must exist before deleting
    monkeypatch.delenv("KUGL_HOME")
    assert kugl_home() == Path.home() / ".kugl"


def test_reject_world_writeable_config(test_home):
    init_file = kugl_home() / "init.yaml"
    init_file.write_text("foo: bar")
    init_file.chmod(0o777)
    with pytest.raises(KuglError, match="is world writeable"):
        main1(["select 1"])


@pytest.mark.skip  # FIXME re-enable without return_config hack
def test_cli_args_override_settings(test_home):
    init, _ = main1(["select 1"], return_config=True)
    assert init.settings.cache_timeout == Age(120)
    assert init.settings.reckless == False
    init, _ = main1(["-t 5", "-r", "select 1"], return_config=True)
    assert init.settings.cache_timeout == Age(5)
    assert init.settings.reckless == True