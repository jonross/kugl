"""
Unit tests for the different built-in resource types.
"""
import io
import json
import sys

import pytest

from kugl.util import KuglError, kugl_home, features_debugged, kugl_cache, fail, KPath
from tests.testing import assert_query, assert_by_line


def test_config_with_missing_resource(test_home):
    """Ensure correct error when an undefined resource is used."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
        create:
          - table: stuff
            resource: stuff
            columns: []
    """)
    with pytest.raises(KuglError, match="Errors in .*kubernetes.yaml:\nTable 'stuff' needs undefined resource 'stuff'"):
        assert_query("SELECT * FROM stuff", "")


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


def test_untypeable_resource(hr):
    """A resource we can't type should fail."""
    config = hr.config()
    # Replace the HR schema's "people" resource with an untypeable one.
    config["resources"][0] = dict(name="people")
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\ncan't infer type of resource 'people'"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_namespaced_resources_are_kubernetes_resources(hr, capsys):
    """A resource with a namespace: attribute is of type Kubernetes."""
    config = hr.config()
    # Replace the HR schema's "people" resource with one that will be inferred as Kubernetes
    config["resources"][0] = dict(name="people", namespaced="true")
    hr.save(config)
    # This will fail because there's no Kubernetes "people" resource, but that's OK.
    with pytest.raises(SystemExit):
        assert_query(hr.PEOPLE_QUERY, None)
    _, err = capsys.readouterr()
    assert "failed to run [kubectl get people" in err


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


def test_folder_missing(hr):
    """Ensure correct error when a folder resource's target is missing."""
    config = hr.config()
    # Replace the HR schema's "people" resource with a missing folder resource.
    config["resources"][0] = dict(name="people", folder="missing", glob="*.json", match=".*")
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\nMissing resource folder"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_bad_folder_regex(hr):
    """Ensure correct error when a folder resource's match expression is an invalid regex."""
    config = hr.config()
    # Replace the HR schema's "people" resource with a botched folder resource.
    config["resources"][0] = dict(name="people", folder="missing", glob="*.json", match="(")
    hr.save(config)
    with pytest.raises(KuglError, match="Errors in .*hr.yaml:\nInvalid regex"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_no_files_match(hr, tmp_path):
    """Ensure correct error when a folder resource doesn't match any files"""
    config = hr.config()
    # Replace the HR schema's "people" resource with a folder resource that doesn't match any files.
    folder = tmp_path / "empty"
    folder.mkdir()
    config["resources"][0] = dict(name="people", folder=str(folder), glob="*.json", match=".*")
    hr.save(config)
    with pytest.raises(KuglError, match="Glob .* in .*/empty produced no files"):
        assert_query(hr.PEOPLE_QUERY, None)


def test_folder_content(hr, tmp_path, capsys):
    """Test a folder resource that matches files."""
    config = hr.config()
    folder = KPath(tmp_path) / "region"
    # Replace the HR schema's "people" resource with a folder resource that matches files.
    # These two files will match the regex, the third won't.
    folder.joinpath("east").prep().joinpath("data.yaml").write_text("""
        - name: Jim
          age: 42
          sex: m
        - name: Jill
          age: 43
          sex: f
    """)
    folder.joinpath("west").prep().joinpath("data.yaml").write_text("""
        - name: Jen
          age: 40
          sex: f
        - name: Joe
          age: 41
          sex: m
    """)
    folder.joinpath("south").prep().joinpath("junk.yaml").write_text("""
        - name: Jon
          age: 50
          sex: m
    """)
    config["resources"][0] = dict(name="people", folder=str(folder),
                                  glob="**/data.yaml", match="(?P<region>[^/]+)/data.yaml")
    # Update the row_source of the people table to match the folder data layout.
    config["create"][0]["row_source"] = ["[]", "content"]
    # Add a column to capture the region.
    config["create"][0]["columns"].append(dict(name="region", path="^match.region"))
    hr.save(config)
    with features_debugged("folder"):
        assert_query("SELECT region, name, age FROM hr.people ORDER BY age", """
            region    name      age
            west      Jen        40
            west      Joe        41
            east      Jim        42
            east      Jill       43
        """)
    _, err = capsys.readouterr()
    assert "Reviewing files for **/data.yaml" in err
    assert "Adding east/data.yaml with match {'region': 'east'}" in err
    assert "Adding west/data.yaml with match {'region': 'west'}" in err
