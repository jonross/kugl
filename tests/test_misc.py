# Assorted tests for various edge cases and error conditions.
# Some of these are just to achieve 100% coverage.

import os
from pathlib import Path

import pytest

from kugel.helpers import Resources
from kugel.main import main
from kugel.utils import KugelError, kube_home, kugel_home


def test_no_resources():
    assert Resources.extract(None) == Resources(None, None, None)


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

