"""
Unit tests for the 'file' resource type
"""

import io
import json
import sys

import pytest

from kugl.util import KuglError
from ..testing import assert_query


def test_file_resources_not_cacheable(hr):
    """As of this writing, file resources can't be cached."""
    config = hr.config()
    # Replace the HR config's "people" resource with a file resource.
    config["resources"][0] = dict(name="people", file="blah", cacheable="true")
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\nresource 'people' cannot be cacheable: true"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_file_resource_not_found(hr):
    """Ensure correct error when a file resource's target is missing."""
    config = hr.config()
    # Replace the HR schema's "people" resource with a missing file resource.
    config["resources"][0] = dict(name="people", file="missing.json")
    hr.save(config)
    with pytest.raises(KuglError, match="failed to fetch resource hr.people: failed to read missing.json"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_file_resource_valid(hr, test_home):
    """Test a valid file-based resource"""
    config = hr.config()
    # Replace the HR schema's "people" resource with a valid file resource.
    path = test_home / "people.json"
    path.write_text(json.dumps(config["resources"][0]["data"]))
    config["resources"][0] = dict(name="people", file=str(path))
    hr.save(config)
    assert_query(hr.PEOPLE_QUERY, hr.PEOPLE_RESULT)


def test_stdin_resource(hr, monkeypatch):
    """Same as test_file_resource_valid, but on stdin."""
    config = hr.config()
    # Replace the HR schema's "people" resource with a file resource that reads standard input.
    data = json.dumps(config["resources"][0]["data"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(data))
    config["resources"][0] = dict(name="people", file="stdin")
    hr.save(config)
    assert_query(hr.PEOPLE_QUERY, hr.PEOPLE_RESULT)

