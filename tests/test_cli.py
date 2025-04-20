"""
Tests for command-line options.
"""
import re
import sqlite3
from argparse import ArgumentParser

import pytest

from kugl.impl.config import Settings
from kugl.impl.engine import CHECK, ALWAYS_UPDATE, NEVER_UPDATE
from kugl.main import main1, parse_args
from kugl.util import KuglError, Age, kugl_home


def test_enforce_one_cache_option(test_home):
    with pytest.raises(KuglError, match="Cannot use both -c/--cache and -u/--update"):
        main1(["-c", "-u", "select 1"])


def test_enforce_one_namespace_option(test_home):
    with pytest.raises(KuglError, match="Cannot use both -a/--all-namespaces and -n/--namespace"):
        main1(["-a", "-n", "x", "select * from pods"])


def test_no_such_table(test_home):
    with pytest.raises(sqlite3.OperationalError, match=re.escape(f"no such table: foo")):
        main1(["select * from foo"])


def test_unknown_shortcut(test_home):
    with pytest.raises(KuglError, match="No shortcut named 'foo'"):
        main1(["foo"])


def test_missing_query(test_home):
    with pytest.raises(KuglError, match="Missing sql query"):
        main1([])


def test_shortcut_with_invalid_option(test_home, capsys):
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          foo:
          - --badoption
          - "select * from pods"
    """)
    with pytest.raises(SystemExit):
        main1(["-a", "foo"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_unknown_option(test_home, capsys):
    with pytest.raises(SystemExit):
        main1(["--badoption", "select 1"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_enforce_one_cache_option_via_shortcut(test_home, capsys):
    kugl_home().prep().joinpath("init.yaml").write_text("""
        shortcuts:
          - name: foo
            args:
              - -u
              - "select 1"
    """)
    with pytest.raises(KuglError, match="Cannot use both -c/--cache and -u/--update"):
        main1(["-c", "foo"])


def test_no_headers(test_home, capsys):
    main1(["-H", "select 1, 2"])
    out, _ = capsys.readouterr()
    # Not sure why the output format is different with no headers...
    assert out == "1  2\n"


@pytest.mark.parametrize("argv,expected_flag,age,reckless,error", [
    (["-u", "select 1"], ALWAYS_UPDATE, Age(120), False, None),
    (["-t", "5", "select 1"], CHECK, Age(5), False, None),
    (["-c", "-r", "select 1"], NEVER_UPDATE, Age(120), True, None),
    (["-c", "-u", "select 1"], None, None, None, "Cannot use both -c/--cache and -u/--update"),
])
def test_parse_args(test_home, argv, expected_flag, age, reckless, error):
    ap = ArgumentParser()
    settings = Settings()
    if error:
        with pytest.raises(KuglError, match=error):
            parse_args(argv, ap, settings)
    else:
        args, actual_flag = parse_args(argv, ap, settings)
        assert actual_flag == expected_flag
        assert settings.cache_timeout == age
        assert settings.reckless == reckless