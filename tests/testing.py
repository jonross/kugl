"""
Common utilities for unit testing.
"""

import json
import re
import textwrap
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Union

import yaml

from kugl.impl.config import Settings
from kugl.impl.engine import Engine, Query, ALWAYS_UPDATE
from kugl.util import KPath


def assert_query(sql: str, expected: Union[str, list], all_ns: bool = False):
    """
    Run a query in the "nocontext" namespace and compare the result with expected output.
    :param sql: SQL query
    :param expected: Output as it would be shown at the CLI.  This will be dedented so the
        caller can indent for neatness.  Or, if a list, each item will be checked in order.
    :param all_ns: FIXME temporary hack until we get namespaces out of engine.py
    """
    args = SimpleNamespace(all_namespaces=all_ns, namespace=None)
    engine = Engine(args, ALWAYS_UPDATE, Settings())
    if isinstance(expected, str):
        actual = engine.query_and_format(Query(sql))
        assert actual.strip() == textwrap.dedent(expected).strip()
    else:
        actual, _ = engine.query(Query(sql))
        assert actual == expected


def assert_by_line(lines: Union[str, list[str]], expected: Union[str, list[Union[str, re.Pattern]]]):
    """
    Compare a list of lines with a list of expected lines or regex patterns.
    :param lines: Actual output, as a list of lines
    :param expected: Expected output, as a list of strings or re.Pattern objects,
        or a single string to be dedented and split.
    """
    if isinstance(lines, str):
        lines = lines.strip().splitlines()
    if isinstance(expected, str):
        # Must be dedented because assertions are written with indent
        expected = textwrap.dedent(expected).strip().splitlines()
    for line, exp, index in zip(lines, expected, range(len(expected))):
        if isinstance(exp, str):
            assert line.strip() == exp.strip(), f"Line {index}: {line.strip()} != {exp.strip()}"
        else:
            assert exp.match(line.strip()), f"Did not find {exp.pattern} in {line.strip()}"


@contextmanager
def augment_file(path: KPath):
    """A context manager that lets the caller easily alter a JSON or YAML file."""
    path.parent.prep()
    is_yaml = str(path).endswith(".yaml")
    content = (path.exists() and path.parse()) or {}
    yield content
    path.write_text(yaml.dump(content) if is_yaml else json.dumps(content))