"""
Unit tests for inline data resources
"""

from kugl.util import features_debugged
from ..testing import assert_query, assert_by_line


def test_data_resource(hr):
    """Test an inline data resource."""
    # The HR config defines one as-is.
    hr.save()
    assert_query(hr.PEOPLE_QUERY, hr.PEOPLE_RESULT)


def test_debugged_data_resource(hr, capsys):
    """Same as test_data_resource, but with 'sqlite' debug flag on."""
    hr.save()
    with features_debugged("sqlite"):
        assert_query(hr.PEOPLE_QUERY, hr.PEOPLE_RESULT)
    out, err = capsys.readouterr()
    assert_by_line(err, f"""
        sqlite: execute: ATTACH DATABASE ':memory:' AS 'hr'
        sqlite: execute: CREATE TABLE hr.people (name text, age integer)
        sqlite: execute: INSERT INTO hr.people VALUES(?, ?)
        sqlite: query: SELECT name, age FROM hr.people ORDER BY age
    """)

