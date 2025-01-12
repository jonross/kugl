"""
Assorted query tests not covered elsewhere.
"""
import io
import json
import sys
import textwrap

import pytest

from kugl.main import main1
from kugl.util import KuglError, features_debugged
from .testing import kubectl_response, assert_query, assert_by_line


def test_non_sql_types(test_home, capsys):
    (test_home / "kubernetes.yaml").write_text("""
      resources:
        - name: things
          namespaced: false
      create:
        - table: things
          resource: things
          columns:
            - name: size
              type: size
              path: size
            - name: cpu
              type: cpu
              path: cpu
            - name: age
              type: age
              path: age
            - name: date
              type: date
              path: date
    """)
    kubectl_response("things", {
        "items": [
            {"size": "10Ki", "cpu": "2.5", "age": "2d", "date": "2021-01-01"},
            {"size": "2Gi", "cpu": "300m", "age": "4h", "date": "2021-12-31T23:59:59Z"},
        ]
    })
    with features_debugged("extract"):
        assert_query("SELECT to_size(size) AS s, cpu, to_age(age) AS a, to_utc(date) AS d FROM things ORDER BY 1", """
            s        cpu  a    d
            10Ki     2.5  2d   2021-01-01T00:00:00Z
            2.0Gi    0.3  4h   2021-12-31T23:59:59Z
        """)
        out, err = capsys.readouterr()
        assert_by_line(err, """
            extract: get size path=size from {"size": "10Ki", "cpu": "2.5", "age": "2d", "date": "2021-01-01"}
            extract: got 10240
            extract: get cpu path=cpu from {"size": "10Ki", "cpu": "2.5", "age": "2d", "date": "2021-01-01"}
            extract: got 2.5
            extract: get age path=age from {"size": "10Ki", "cpu": "2.5", "age": "2d", "date": "2021-01-01"}
            extract: got 172800
            extract: get date path=date from {"size": "10Ki", "cpu": "2.5", "age": "2d", "date": "2021-01-01"}
            extract: got 1609459200
            extract: get size path=size from {"size": "2Gi", "cpu": "300m", "age": "4h", "date": "2021-12-31T23:59:59Z"}
            extract: got 2147483648
            extract: get cpu path=cpu from {"size": "2Gi", "cpu": "300m", "age": "4h", "date": "2021-12-31T23:59:59Z"}
            extract: got 0.3
            extract: get age path=age from {"size": "2Gi", "cpu": "300m", "age": "4h", "date": "2021-12-31T23:59:59Z"}
            extract: got 14400
            extract: get date path=date from {"size": "2Gi", "cpu": "300m", "age": "4h", "date": "2021-12-31T23:59:59Z"}
            extract: got 1640995199
        """)


def test_too_many_parents(test_home):
    (test_home / "kubernetes.yaml").write_text("""
      resources:
        - name: things
      create:
        - table: things
          resource: things
          columns:
            - name: something
              path: ^^^invalid
    """)
    kubectl_response("things", {
        "items": [
            {"something": "foo"},
            {"something": "foo"},
        ]
    })
    with pytest.raises(KuglError, match="Missing parent or too many . while evaluating ...invalid"):
        assert_query("SELECT * FROM things", "")


def test_config_with_missing_resource(test_home):
    (test_home / "kubernetes.yaml").write_text("""
        create:
          - table: stuff
            resource: stuff
            columns: []
    """)
    with pytest.raises(KuglError, match="Table 'stuff' needs unknown resource 'stuff'"):
        assert_query("SELECT * FROM stuff", "")


def test_select_from_stdin(test_home, monkeypatch, capsys):
    (test_home / "hr.yaml").write_text("""
        resources:
          - name: stdin
            file: stdin
        create:
          - table: people
            resource: stdin
            row_source:
              - people
            columns:
              - name: name
                path: name
              - name: age
                path: age
                type: integer
    """)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"people": [
        {"name": "Jim", "age": 42},
        {"name": "Jill", "age": 43},
    ]})))
    with features_debugged("sqlite"):
        main1(["SELECT name, age FROM hr.people"])
    out, err = capsys.readouterr()
    assert_by_line(out, """
        name      age
        Jim        42
        Jill       43
    """)
    assert_by_line(err, f"""
        sqlite: execute: ATTACH DATABASE ':memory:' AS 'hr'
        sqlite: execute: CREATE TABLE hr.people (name text, age integer)
        sqlite: execute: INSERT INTO hr.people VALUES(?, ?)
        sqlite: query: SELECT name, age FROM hr.people
    """)

