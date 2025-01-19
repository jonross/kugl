"""
Unit tests for the different built-in resource types.
"""
import io
import json
import sys

import pytest

from kugl.util import KuglError, kugl_home, features_debugged
from tests.testing import assert_query, assert_by_line


def test_data_resource(hr):
    """Test an inline data resource."""
    # The HR config defines one as-is.
    hr.save()
    assert_query("SELECT name, age FROM hr.people", hr.PEOPLE_RESULT)


def test_debugged_data_resource(hr, capsys):
    """Same as test_data_resource, but with 'sqlite' debug flag on."""
    hr.save()
    with features_debugged("sqlite"):
        assert_query("SELECT name, age FROM hr.people", hr.PEOPLE_RESULT)
    out, err = capsys.readouterr()
    assert_by_line(err, f"""
        sqlite: execute: ATTACH DATABASE ':memory:' AS 'hr'
        sqlite: execute: CREATE TABLE hr.people (name text, age integer)
        sqlite: execute: INSERT INTO hr.people VALUES(?, ?)
        sqlite: query: SELECT name, age FROM hr.people
    """)


def test_file_resources_not_cacheable(hr):
    """As of this writing, file resources can't be cached."""
    config = hr.config()
    # Replace the HR config's "people" resource with a file resource.
    config["resources"][0] = dict(name="people", file="blah", cacheable="true")
    hr.save(config)
    with pytest.raises(KuglError, match="resource 'people' cannot be cacheable"):
        assert_query("SELECT name, age FROM hr.people", None)


def test_file_resource_not_found(hr):
    """Ensure correct error when a file resource's target is missing."""
    config = hr.config()
    # Replace the HR schema's "people" resource with a missing file resource.
    config["resources"][0] = dict(name="people", file="missing.json")
    hr.save(config)
    with pytest.raises(KuglError, match="failed to fetch resource hr.people: failed to read missing.json"):
        assert_query("SELECT name, age FROM hr.people", None)


def test_file_resource_valid(hr, test_home):
    """Test a valid file-based resource"""
    config = hr.config()
    # Replace the HR schema's "people" resource with a valid file resource.
    path = test_home / "people.json"
    path.write_text(json.dumps(config["resources"][0]["data"]))
    config["resources"][0] = dict(name="people", file=str(path))
    hr.save(config)
    assert_query("SELECT name, age FROM hr.people", hr.PEOPLE_RESULT)


def test_stdin_resource(hr, monkeypatch):
    """Same as test_file_resource_valid, but on stdin."""
    config = hr.config()
    # Replace the HR schema's "people" resource with a file resource that reads standard input.
    data = json.dumps(config["resources"][0]["data"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(data))
    config["resources"][0] = dict(name="people", file="stdin")
    hr.save(config)
    assert_query("SELECT name, age FROM hr.people", hr.PEOPLE_RESULT)


def test_noncacheable_nonkeyed(hr):
    """A non-cacheable exec resource doesn't need a cache key."""
    config = hr.config()
    # Replace the HR schema's people resource with an exec resource that prints the same data
    command = f"echo '{json.dumps(config['resources'][0]['data'])}'"
    config["resources"][0] = dict(name="people", exec=command)
    hr.save(config)
    assert_query("SELECT name, age FROM hr.people", hr.PEOPLE_RESULT)

