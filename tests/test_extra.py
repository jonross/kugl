"""
Assorted query tests not covered elsewhere.
"""
import io
import json
import os
import sys
from pathlib import Path

import pytest

from kugl.main import main1
from kugl.util import KuglError, features_debugged, kugl_home, KPath
from .testing import kubectl_response, assert_query, assert_by_line


def test_non_sql_types(test_home, capsys):
    """Test the column types that don't correspond exactly to SQLite types.
    Also test the 'extract' debug option."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
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
    """Ensure correct error when a parent field reference is too long."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
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
    """Ensure correct error when an undefined resource is used."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
        create:
          - table: stuff
            resource: stuff
            columns: []
    """)
    with pytest.raises(KuglError, match="Table 'stuff' needs unknown resource 'stuff'"):
        assert_query("SELECT * FROM stuff", "")


def test_no_config_for_schema():
    """Ensure correct error when a schema has no configs."""
    with pytest.raises(KuglError, match="no configurations found for schema 'my'"):
        assert_query("SELECT * from my.stuff", "")


@pytest.mark.parametrize("query,error", [
    ("SELECT * FROM my.stuff", "no configurations found for schema 'my'"),
    ("SELECT * FROM oh@my.stuff", "invalid schema name in 'oh@my.stuff' -- must contain"),
    ("SELECT * FROM my.@stuff", "invalid table name in 'my.@stuff' -- must contain"),
    ("SELECT * FROM main.stuff", "invalid schema name, must not be 'main', 'temp', or 'init'"),
    ("SELECT * FROM temp.stuff", "invalid schema name, must not be 'main', 'temp', or 'init'"),
    ("SELECT * FROM init.stuff", "invalid schema name, must not be 'main', 'temp', or 'init'"),
])
def test_bad_queries(query, error):
    with pytest.raises(KuglError, match=error):
        assert_query(query, "")


@pytest.mark.parametrize("resource", [
    "file: stdin",
    "exec: cat $KUGL_MOCKDIR/people_data.json",
])
def test_stdin_and_exec(test_home, resource, monkeypatch, capsys):
    """Test the stdin and exec resources.  Also test the 'sqlite' debug option."""
    kugl_home().prep().joinpath("hr.yaml").write_text(f"""
        resources:
          - name: people
            {resource}
        create:
          - table: people
            resource: people
            row_source:
              - people
            columns:
              - name: name
                path: name
              - name: age
                path: age
                type: integer
    """)
    people_data = json.dumps({"people": [
        {"name": "Jim", "age": 42},
        {"name": "Jill", "age": 43},
    ]})
    if resource.startswith("file:"):
        # The file: stdin form of the test; mock stdin
        monkeypatch.setattr(sys, "stdin", io.StringIO(people_data))
    else:
        # The exec: form of the test; write the data to a file that will be cat'ed
        KPath(os.getenv("KUGL_MOCKDIR")).prep().joinpath("people_data.json").write_text(people_data)
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


def test_multi_schema_query(test_home, capsys):
    """Test a query that references multiple schemas."""
    kugl_home().prep().joinpath("hr.yaml").write_text("""
        resources:
          - name: people
            file: $KUGL_MOCKDIR/people_data.yaml
        create:
          - table: people
            resource: people
            row_source:
              - people
            columns:
              - name: name
                path: name
              - name: age
                path: age
                type: integer
    """)
    kugl_home().joinpath("sales.yaml").write_text("""
        resources:
          - name: sales_volume
            file: $KUGL_MOCKDIR/sales_data.yaml
        create:
          - table: volume
            resource: sales_volume
            row_source:
              - sales
            columns:
              - name: name
                path: name
              - name: dollars
                type: integer
                path: dollars
    """)
    mockdir = Path(os.getenv("KUGL_MOCKDIR"))
    mockdir.mkdir(parents=True, exist_ok=True)
    (mockdir / "people_data.yaml").write_text("""
        people:
          - name: Jim
            age: 42
          - name: Jill
            age: 43
    """)
    (mockdir / "sales_data.yaml").write_text("""
        sales:
          - name: Jim
            dollars: 10000
          - name: Jill
            dollars: 12000
    """)
    main1(["""
        SELECT person.name, person.age, volume.dollars
        FROM hr.people AS person
        JOIN sales.volume AS volume ON person.name = volume.name
        ORDER BY 2 DESC
    """])
    out, err = capsys.readouterr()
    assert_by_line(out, """
        name      age    dollars
        Jill       43      12000
        Jim        42      10000
    """)

