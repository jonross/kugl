"""
Unit tests for multiple config files on init_path.
"""

import sqlite3

import pytest

from kugl.main import main1
from kugl.util import KPath, kugl_home, KuglError
from tests.testing import assert_by_line


@pytest.fixture(scope="function")
def extra_home(test_home, tmp_path):
    """Additional home for Kugl init and schema files.

    When used, this fixture creates a second folder similar to test_home, and writes init.yaml
    in test_home pointing to both folders."""
    kugl_home().prep().joinpath("init.yaml").write_text(f"""
        settings:
          init_path:
            - "{kugl_home()}"
            - "{tmp_path}"
    """)
    yield KPath(tmp_path).prep()


def test_bogus_init_paths(hr, test_home):
    """Put only a missing folder in the init path, verify that breaks."""
    hr.save()
    # Don't use the extra_home fixture, because don't want to see both entries in the init path
    bad_home = test_home / "xyz"
    kugl_home().prep().joinpath("init.yaml").write_text(f"""
        settings:
          init_path:
            - {bad_home}
    """)
    with pytest.raises(KuglError, match="no configurations found for schema 'hr'"):
        main1([hr.PEOPLE_QUERY])


def test_reject_dupe_resource(hr, extra_home):
    """Resource must not be defined in more than one schema file"""
    hr.save()
    extra_home.joinpath("hr.yaml").write_text("""
        resources:
        - name: people
          data: []
    """)
    with pytest.raises(KuglError, match="Resource 'people' is already defined in schema 'hr'"):
        main1([hr.PEOPLE_QUERY])


def test_reject_dupe_table(hr, extra_home):
    """Table must not be defined in more than one schema file"""
    hr.save()
    extra_home.joinpath("hr.yaml").write_text("""
        create:
        - table: people
          resource: people
          columns:
            - name: name
              path: name
    """)
    with pytest.raises(KuglError, match="Table 'people' is already defined in schema 'hr'"):
        main1([hr.PEOPLE_QUERY])


def test_reject_dupe_column(hr, extra_home):
    """Column must not be defined in more than one schema file"""
    hr.save()
    extra_home.joinpath("hr.yaml").write_text("""
        extend:
        - table: people
          columns:
            - name: name
              path: name
    """)
    with pytest.raises(KuglError, match="Column 'name' is already defined in table 'people'"):
        main1([hr.PEOPLE_QUERY])


def test_extend_valid_table(hr, extra_home, capsys):
    """Verify result of extending a table from a separate schema file."""
    hr.save()
    extra_home.joinpath("hr.yaml").write_text("""
        extend:
        - table: people
          columns:
            - name: sex
              path: sex
    """)
    main1(["SELECT * FROM hr.people ORDER BY age"])
    out, _ = capsys.readouterr()
    assert_by_line(out, """
        name      age  sex
        Jim        42  m
        Jill       43  f
    """)

