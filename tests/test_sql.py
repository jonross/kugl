from typing import Optional

import pytest

from kugl.impl.parser import Query
from kugl.util import KuglError, SqliteDb


@pytest.mark.parametrize("sql,refs,error", [
    ("""select 1; select 1""", None, "query must contain exactly one statement"),
    ("""select 1""", [], None),
    ("""select xyz from pods""", ["pods"], None),
    ("""select xyz from pods left outer join nodes""", ["pods", "nodes"], None),
    ("""select xyz from my.pods a join his.nodes b""", ["my.pods", "his.nodes"], None),
    ("""select xyz from my.own.pods""", None, "invalid schema name in table: my.own.pods"),
])
def test_schema_extraction(sql, refs: list[str], error: Optional[str]):
    """Verify extraction of Kugl schemas from SQL queries."""
    if error is not None:
        with pytest.raises(KuglError, match=error):
            Query(sql)
    else:
        q = Query(sql)
        assert set(refs) == set(str(nt) for nt in q.named_tables)


def test_multiple_sqlite_dbs():
    """Verify we can directly map Kugl schemas to SQLite databases.
    This is huge; it means no transforms on SQL queries are needed."""
    db = SqliteDb()

    db.execute("attach database ':memory:' as 'a'")
    db.execute("create table a.t (x int, name text)")
    db.execute("insert into a.t values (1, 'foo')")

    db.execute("attach database ':memory:' as 'b'")
    db.execute("create table b.t (y int, name text)")
    db.execute("insert into b.t values (2, 'foo')")

    db.execute("create table t (z int, name text)")
    db.execute("insert into t values (3, 'foo')")

    assert (1, 2, 3) == db.query("""
        SELECT a.x, b.y, z
        FROM t 
            JOIN a.t AS a ON a.name = t.name
            JOIN b.t AS b ON b.name = t.name
    """, one_row=True)