"""
Assorted tests for various edge cases and error conditions.
Some of these are just to achieve 100% coverage.
"""

import os
from pathlib import Path

import pytest

from kugel.helpers import Limits
from kugel.impl.utils import KugelError
from kugel.main import main
from kugel.model import Age
from kugel.utils import kube_home, kugel_home


def test_no_resources():
    assert Limits.extract(None) == Limits(None, None, None)


def test_kube_home_missing(test_home, tmp_path):
    os.environ["KUGEL_HOME"] = str(tmp_path / "doesnt_exist")
    with pytest.raises(KugelError, match="can't determine current context"):
        main(["select 1"])


def test_no_kube_context(test_home, tmp_path):
    kube_home().joinpath("config").write_text("")
    with pytest.raises(KugelError, match="No current context"):
        main(["select 1"])


def test_enforce_mockdir(test_home, monkeypatch):
    monkeypatch.delenv("KUGEL_MOCKDIR")
    with pytest.raises(SystemExit, match="Unit test state error"):
        main(["select 1"])


def test_kube_home_without_envar(monkeypatch):
    monkeypatch.setenv("KUGEL_HOME", "xxx")  # must exist before deleting
    monkeypatch.delenv("KUGEL_HOME")
    assert kube_home() == Path.home() / ".kube"


def test_kugel_home_without_envar(monkeypatch):
    monkeypatch.setenv("KUGEL_HOME", "xxx")  # must exist before deleting
    monkeypatch.delenv("KUGEL_HOME")
    assert kugel_home() == Path.home() / ".kugel"


def test_reject_world_writeable_config(test_home):
    init_file = kugel_home() / "init.yaml"
    init_file.write_text("foo: bar")
    init_file.chmod(0o777)
    with pytest.raises(KugelError, match="is world writeable"):
        main(["select 1"])


def test_cli_args_override_settings(test_home):
    settings = main(["select 1"], return_config=True).settings
    assert settings.cache_timeout == Age(120)
    assert settings.reckless == False
    settings = main(["-t 5", "-r", "select 1"], return_config=True).settings
    assert settings.cache_timeout == Age(5)
    assert settings.reckless == True