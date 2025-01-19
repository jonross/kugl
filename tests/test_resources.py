"""
Unit tests for the different built-in resource types.
"""
import json

import pytest

from kugl.main import main1
from kugl.util import KuglError
from tests.testing import assert_query


def test_data_resource(hr):
    """Test an inline data resource."""
    # The HR config defines one as-is.
    hr.save()
    assert_query("SELECT name, age FROM hr.people", """
        name      age
        Jim        42
        Jill       43
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
    assert_query("SELECT name, age FROM hr.people", """
        name      age
        Jim        42
        Jill       43
    """)
