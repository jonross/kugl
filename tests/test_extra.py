"""
Assorted query tests not covered elsewhere.
"""

from kugl.util import features_debugged, kugl_home
from .testing import assert_query, assert_by_line
from .k8s.k8s_mocks import kubectl_response


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