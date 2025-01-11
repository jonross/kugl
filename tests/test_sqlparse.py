from typing import Optional

import pytest

from kugl.impl.parser import Query
from kugl.util import KuglError


@pytest.mark.parametrize("sql,refs,error", [
    ("""select 1; select 1""", None, "query must contain exactly one statement"),
    ("""select 1""", [], None),
    ("""select xyz from pods""", ["pods"], None),
    ("""select xyz from pods left outer join nodes""", ["pods", "nodes"], None),
    ("""select xyz from my.pods a join his.nodes b""", ["my.pods", "his.nodes"], None),
    ("""select xyz from my.own.pods""", None, "invalid schema name in table: my.own.pods"),
])
def test_parsing(sql, refs: list[str], error: Optional[str]):
    if error is not None:
        with pytest.raises(KuglError, match=error):
            Query(sql)
    else:
        q = Query(sql)
        assert set(refs) == set(str(ref) for ref in q.refs)