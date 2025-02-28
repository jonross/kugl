"""
Unit tests for the 'folder' resource type
"""

import pytest

from kugl.util import KuglError, KPath, features_debugged
from ..testing import assert_query


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
