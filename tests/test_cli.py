"""
Tests for command-line options.
"""

import json
import re
import sqlite3
from argparse import ArgumentParser

import pytest

from kugl.impl.config import Settings
from kugl.impl.engine import CHECK, ALWAYS_UPDATE, NEVER_UPDATE
from kugl.main import main1, parse_args
from kugl.util import KuglError, Age, kugl_home


def test_enforce_cache_option(test_home):
    with pytest.raises(KuglError, match="Cannot use both -s/--stale and -r/--refresh"):
        main1(["-s", "-r", "select 1"])


def test_enforce_cache_option_via_shortcut(test_home, capsys):
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: foo
            args:
              - -r
              - "select 1"
    """)
    with pytest.raises(KuglError, match="Cannot use both -s/--stale and -r/--refresh"):
        main1(["-s", "foo"])


def test_enforce_one_namespace_option(test_home):
    with pytest.raises(KuglError, match="Cannot use both -A/--all and -n/--namespace"):
        main1(["-A", "-n", "x", "select * from pods"])


def test_no_such_table(test_home):
    with pytest.raises(sqlite3.OperationalError, match=re.escape("no such table: foo")):
        main1(["select * from foo"])


def test_unknown_shortcut(test_home):
    with pytest.raises(KuglError, match="No shortcut named 'foo'"):
        main1(["foo"])


def test_missing_query(test_home):
    with pytest.raises(KuglError, match="Missing sql query"):
        main1([])


def test_unknown_option(test_home, capsys):
    with pytest.raises(SystemExit):
        main1(["--badoption", "select 1"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_unknown_option_in_shortcut(test_home, capsys):
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          foo:
          - --badoption
          - "select * from pods"
    """)
    with pytest.raises(SystemExit):
        main1(["-A", "foo"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_no_headers(test_home, capsys):
    main1(["-H", "select 1, 2"])
    out, _ = capsys.readouterr()
    # FIXME: Not sure why the output format is different with no headers...
    assert out == "1  2\n"


def test_output_csv(test_home, capsys):
    main1(["-o", "csv", "select 1 as foo, 2 as bar"])
    out, _ = capsys.readouterr()
    assert out == "foo,bar\n1,2\n"


def test_output_csv_no_headers(test_home, capsys):
    main1(["-o", "csv", "-H", "select 1 as foo, 2 as bar"])
    out, _ = capsys.readouterr()
    assert out == "1,2\n"


def test_output_json(test_home, capsys):
    main1(["-o", "json", "select 1 as foo, 2 as bar"])
    out, _ = capsys.readouterr()
    assert json.loads(out) == [{"foo": 1, "bar": 2}]


def test_output_invalid(test_home, capsys):
    with pytest.raises(SystemExit):
        main1(["-o", "xml", "select 1"])
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv,expected_flag,age,quiet,error",
    [
        (["-r", "select 1"], ALWAYS_UPDATE, Age(120), False, None),
        (["-t", "5", "select 1"], CHECK, Age(5), False, None),
        (["-s", "-q", "select 1"], NEVER_UPDATE, Age(120), True, None),
        (
            ["-s", "-r", "select 1"],
            None,
            None,
            None,
            "Cannot use both -s/--stale and -r/--refresh",
        ),
    ],
)
def test_parse_args(test_home, argv, expected_flag, age, quiet, error):
    """Verify correct values received for -r, -t, -s, -q options"""
    ap = ArgumentParser()
    settings = Settings()
    if error:
        with pytest.raises(KuglError, match=error):
            parse_args(argv, ap, settings)
    else:
        args, actual_flag, _ = parse_args(argv, ap, settings)
        assert actual_flag == expected_flag
        assert settings.cache_timeout == age
        assert settings.quiet == quiet


def test_init_command(test_home, capsys):
    """Verify 'kugl init' creates ~/.kugl/kubernetes.yaml with recommended config"""
    kubernetes_yaml = kugl_home() / "kubernetes.yaml"
    assert not kubernetes_yaml.exists()

    main1(["init"])
    out, _ = capsys.readouterr()

    assert kubernetes_yaml.exists()
    assert f"Created {kubernetes_yaml}" in out

    content = kubernetes_yaml.read_text()
    assert "extend:" in content
    assert "table: nodes" in content
    assert "name: instance_type" in content
    assert "node.kubernetes.io/instance-type" in content
    assert "beta.kubernetes.io/instance-type" in content


def test_init_command_already_exists(test_home):
    """Verify 'kugl init' fails if kubernetes.yaml already exists"""
    kubernetes_yaml = kugl_home() / "kubernetes.yaml"
    kubernetes_yaml.parent.mkdir(exist_ok=True)
    kubernetes_yaml.write_text("existing content")

    with pytest.raises(KuglError, match="already exists"):
        main1(["init"])


def test_shortcuts_command_none(test_home, capsys):
    main1(["shortcuts"])
    assert "No shortcuts defined" in capsys.readouterr().out


def test_shortcuts_command(test_home, capsys):
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: mypods
            comment: list my pods
            args:
              - "select name from pods"
          - name: find-image
            params:
              - img
            args:
              - "select name from pods where image like '%{{img}}%'"
    """)
    main1(["shortcuts"])
    out = capsys.readouterr().out
    assert "mypods" in out
    assert "(list my pods)" in out
    assert "select name from pods" in out
    assert "find-image <img>" in out
    assert "select name from pods where image like" in out
