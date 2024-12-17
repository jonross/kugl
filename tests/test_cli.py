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


def test_no_such_resource(test_home):
    with pytest.raises(sqlite3.OperationalError, match="no such table: foo"):
        main(["select * from foo"])