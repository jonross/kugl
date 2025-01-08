from typing import Optional

import pytest

from kugl.impl.parser import KQuery


@pytest.mark.parametrize("sql,error,ctes,tables", [
    ("""select 1; select 1""", "SQL must contain exactly one statement", [], []),
    ("""select 1""", None, [], []),
    ("""with mypods as (select 1) select 1""", None, ["mypods"], []),
    ("""with mypods as (select 1), myjobs as (()) select 1""", None, ["mypods", "myjobs"], []),
    ("""with my.pods as (select 1) select 1""", "CTE names may not have schema prefixes", [], []),
])
def test_parsing(sql, error: Optional[Exception], ctes: list[str], tables: list[str]):
    if error is not None:
        with pytest.raises(ValueError, match=error):
            KQuery(sql, "kub")
    else:
        q = KQuery(sql, "kub")
        assert q.ctes == set(ctes)
        assert q.tables == set(tables)