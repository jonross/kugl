"""
Assorted query tests not covered elsewhere.
"""

import pytest

from kugl.util import KuglError, features_debugged, kugl_home
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
          namespaced: true
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
    with pytest.raises(KuglError, match="Errors in .*kubernetes.yaml:\nTable 'stuff' needs unknown resource 'stuff'"):
        assert_query("SELECT * FROM stuff", "")


def test_no_config_for_schema():
    """Ensure correct error when a schema has no configs."""
    with pytest.raises(KuglError, match="no configurations found for schema 'my'"):
        assert_query("SELECT * from my.stuff", "")