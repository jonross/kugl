"""
Assorted tests for various edge cases and error conditions.
Some of these are just to achieve 100% coverage.
"""

from pathlib import Path
import shutil

import pytest
from kugl.util.clock import RealClock, Clock

from kugl.builtins.helpers import Limits, Containerized
from kugl.main import main1
from kugl.util import Age, KuglError, kube_home, kugl_home, features_debugged, debugging, run, kube_context


def test_limits_misc(capsys):
    """Achieve 100% coverage for Limits class."""
    with features_debugged("extract"):
        assert Limits.extract(None, debugging("extract")) == Limits(None, None, None)
    out, err = capsys.readouterr()
    assert err.strip() == "extract: no object provided to requests / limits extractor"
    empty = Limits.extract(None) + Limits.extract(None)
    assert empty.cpu is None
    assert empty.gpu is None
    assert empty.mem is None
    assert Limits(1, 2, 10) + Limits(2, 3, 100) == Limits(3, 5, 110)


def test_kube_home_missing(test_home):
    shutil.rmtree(str(kube_home()))
    with pytest.raises(KuglError, match="can't determine current context"):
        # Must actually query resource or KubernetesResource won't ask for the context
        main1(["select * from nodes"])


def test_no_kube_context(test_home, tmp_path):
    kube_home().prep().joinpath("config").write_text("")
    with pytest.raises(KuglError, match="No current context"):
        # Must actually query a resource or KubernetesResource won't ask for the context
        main1(["select * from nodes"])


def test_enforce_mockdir(test_home, monkeypatch):
    monkeypatch.delenv("KUGL_MOCKDIR")
    with pytest.raises(SystemExit, match="Unit test state error"):
        main1(["select 1"])


def test_kube_home_without_envar(monkeypatch):
    monkeypatch.setenv("KUGL_KUBE_HOME", "xxx")  # must exist before deleting
    monkeypatch.delenv("KUGL_KUBE_HOME")
    assert kube_home() == Path.home() / ".kube"


def test_kugl_home_without_envar(monkeypatch):
    monkeypatch.setenv("KUGL_HOME", "xxx")  # must exist before deleting
    monkeypatch.delenv("KUGL_HOME")
    assert kugl_home() == Path.home() / ".kugl"


def test_reject_world_writeable_config(test_home):
    init_file = kugl_home().prep() / "init.yaml"
    init_file.write_text("foo: bar")
    init_file.chmod(0o777)
    with pytest.raises(KuglError, match="is world writeable"):
        main1(["select 1"])


def test_containerized():
    "For 100% coverage"
    with pytest.raises(NotImplementedError):
        Containerized().containers()


def test_run_single_string_command():
    rc, out, err = run("echo hello world")
    assert (rc, out, err) == (0, "hello world\n", "")
    rc, out, err = run("echo hello world >&2")
    assert (rc, out, err) == (0, "", "hello world\n")


def test_run_nonzero_returncode(capsys):
    rc, out, err = run("echo foo; false", error_ok=True)
    assert (rc, out, err) == (1, "foo\n", "")
    out, err = capsys.readouterr()
    assert (out, err) == ("", "")
    with pytest.raises(SystemExit):
        rc, out, err = run("echo foo >&2; false", error_ok=False)
    assert (rc, out, err) == (1, "", "")
    out, err = capsys.readouterr()
    assert (out, err) == ("", "failed to run [bash -c echo foo >&2; false]:\nfoo\n")


def test_real_clock():
    """For 100% coverage"""
    import time
    clock = RealClock()
    clock.set(0)
    assert abs(int(time.time()) - clock.now()) < 5
    now = clock.now()
    clock.sleep(1)
    assert (clock.now() - now) > 0
    assert not clock.is_simulated


def test_base_clock():
    """For 100% coverage"""
    clock = Clock()
    with pytest.raises(NotImplementedError):
        clock.set(0)
    with pytest.raises(NotImplementedError):
        clock.now()
    with pytest.raises(NotImplementedError):
        clock.sleep(0)
    with pytest.raises(NotImplementedError):
        clock.is_simulated
