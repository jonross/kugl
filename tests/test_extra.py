"""
Assorted query tests not covered elsewhere.
"""
import pytest
import yaml

from kugel.impl.config import UserConfig, parse_model
from kugel.util import fail, to_age, parse_age
from .testing import make_job, kubectl_response, assert_query

@pytest.fixture
def thing_config():
    """A resource type and table with whatever types we want to test."""
    config, errors = parse_model(UserConfig, yaml.safe_load("""
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
            - name: age
              type: age
              path: age
            - name: date
              type: date
              path: date
    """))
    if errors:
        fail("\n".join(errors))
    return config


def test_non_sql_types(test_home, thing_config):
    kubectl_response("things", {
        "items": [
            {"size": "1500m", "age": "2d", "date": "2021-01-01"},
            {"size": "20Gi", "age": "4h", "date": "2021-12-31T23:59:59Z"},
        ]
    })
    assert_query("SELECT to_size(size) AS s, to_age(age) AS a, to_utc(date) AS d FROM things ORDER BY 1", """
        s     a    d
        1.5   2d   2021-01-01T00:00:00Z
        20Gi  4h   2021-12-31T23:59:59Z
    """, user_config=thing_config)