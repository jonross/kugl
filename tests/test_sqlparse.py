from typing import Optional

import pytest

from kugl.impl.parser import Query


@pytest.mark.parametrize("sql,error,ctes,tables", [
    ("""select 1; select 1""", "SQL must contain exactly one statement", [], []),
    ("""select 1""", None, [], []),
    ("""with mypods blah""", "expected keyword AS after <with mypods> but got <blah>", [], []),
    ("""with mypods as materialized ()""", None, ["mypods"], []),
    ("""with mypods as not materialized ()""", None, ["mypods"], []),
    ("""with mypods as not from ()""", "expected keyword MATERIALIZED after <with mypods as not> but got <from>", [], []),
    ("""with mypods as (select 1) select 1""", None, ["mypods"], []),
    ("""with mypods as (select 1), myjobs as (()) select 1""", None, ["mypods", "myjobs"], []),
    ("""with my.pods as (select 1) select 1""", "CTE names may not have schema prefixes", [], []),
    ("""select xyz from pods join nodes """, None, [], ["kub.pods", "kub.nodes"]),
    ("""select xyz from my.pods join nodes """, None, [], ["my.pods", "kub.nodes"]),
    ("""
        with mypods as (blah), sth as (something else)
        select xyz from mypods join nodes on this = that join spouse for lunch
        left right wing outer join ec2.instances
        where nodes.uid in (((select distinct (blah (blah)) from kub.node_taints)))
    """, None, ["mypods", "sth"], ["kub.nodes", "kub.node_taints", "kub.spouse", "ec2.instances"]),
])
def test_parsing(sql, error: Optional[Exception], ctes: list[str], tables: list[str]):
    if error is not None:
        with pytest.raises(ValueError, match=error):
            Query(sql, "kub")
    else:
        q = Query(sql, "kub")
        assert q.ctes == set(ctes)
        assert {str(t) for t in q.tables} == set(tables)