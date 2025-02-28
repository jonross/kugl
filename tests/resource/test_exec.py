"""
Unit tests for the 'exec' resource type
"""

import json

import pytest

from kugl.util import KuglError, features_debugged, kugl_cache
from ..testing import assert_query


def test_exec_noncacheable_nonkeyed(hr):
    """A non-cacheable exec resource doesn't need a cache key."""
    config = hr.config()
    # Replace the HR schema's people resource with an exec resource that prints the same data
    command = f"echo '{json.dumps(config['resources'][0]['data'])}'"
    config["resources"][0] = dict(name="people", exec=command)
    hr.save(config)
    assert_query(hr.PEOPLE_QUERY, hr.PEOPLE_RESULT)


def test_exec_cacheable_nonkeyed(hr):
    """A cacheable exec resource must have a cache key."""
    config = hr.config()
    # Like the previous test, but will fail because marked cachable
    config["resources"][0] = dict(name="people", exec="whatever", cacheable="true")
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\nexec resource 'people' must have a cache key"):
        assert_query(hr.PEOPLE_QUERY, None)


@pytest.mark.parametrize("cache_key", ["some_key", "$unset_envar"])
def test_exec_cacheable_constant_key(hr, cache_key):
    """A cacheable exec resource must have a non-constant key."""
    config = hr.config()
    # Like the previous test, but will fail because key doesn't vary with environment.
    config["resources"][0] = dict(name="people", exec="whatever", cacheable="true", cache_key=cache_key)
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\n.*does not contain non-empty environment references"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_exec_cacheable(hr, monkeypatch):
    """Test a cacheable exec resource."""
    config = hr.config()
    # Like the previous test, but this time use a valid cache key.
    people_data = json.dumps(config["resources"][0]["data"])
    command = f"echo '{people_data}'"
    config["resources"][0] = dict(name="people", exec=command, cacheable="true", cache_key="$SOME_VAR/xyz")
    monkeypatch.setenv("SOME_VAR", "abc")
    hr.save(config)
    with features_debugged("cache"):
        assert_query(hr.PEOPLE_QUERY, hr.PEOPLE_RESULT)
    # Verify the cache data was written
    cache_path = kugl_cache() / "hr/abc/xyz/people.exec.json"
    assert cache_path.read_text() == people_data

