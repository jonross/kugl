"""
Tests for command-line options.
"""

import sqlite3

import pytest

from kugel.main import main
from kugel.impl.utils import KugelError


def test_enforce_one_cache_option(test_home):
    with pytest.raises(KugelError, match="Cannot use both -c/--cache and -u/--update"):
        main(["-c", "-u", "select 1"])


def test_enforce_one_namespace_option(test_home):
    with pytest.raises(KugelError, match="Cannot use both -a/--all-namespaces and -n/--namespace"):
        main(["-a", "-n", "x", "select 1"])


def test_no_such_table(test_home):
    with pytest.raises(sqlite3.OperationalError, match="no such table: foo"):
        main(["select * from foo"])


def test_unknown_alias(test_home):
    with pytest.raises(KugelError, match="No alias named 'foo'"):
        main(["foo"])


def test_alias_with_invalid_option(test_home, capsys):
    test_home.joinpath("init.yaml").write_text("""
        alias:
          foo:
          - --badoption
          - "select 1"
    """)
    with pytest.raises(SystemExit):
        main(["-a", "foo"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_unknown_option(test_home, capsys):
    with pytest.raises(SystemExit):
        main(["--badoption", "select 1"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_enforce_one_cache_option_via_alias(test_home, capsys):
    test_home.joinpath("init.yaml").write_text("""
        alias:
          foo:
          - -u
          - "select 1"
    """)
    with pytest.raises(KugelError, match="Cannot use both -c/--cache and -u/--update"):
        main(["-c", "foo"])


def test_simple_alias(test_home, capsys):
    test_home.joinpath("init.yaml").write_text("""
        alias:
          foo: ["select 1, 2"]
    """)
    main(["foo"])
    out, _ = capsys.readouterr()
    assert out == "  1    2\n" * 2