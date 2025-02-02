"""
Unit tests for multiple schema config files on init_path.
"""

import sqlite3

import pytest

from kugl.main import main1
from kugl.util import KPath, kugl_home, KuglError
from tests.testing import assert_by_line


def test_bogus_init_paths(hr, extra_home):
    """Put only a missing folder in the init path, verify that breaks."""
    extra_home.rmdir()
    with pytest.raises(KuglError, match="no configurations found for schema 'hr'"):
        main1([hr.PEOPLE_QUERY])


def test_reject_kugl_home_in_init_path(test_home):
    """Ensure ~/.kugl/init.yaml does not contain ~/.kugl"""
    kugl_home().prep().joinpath("init.yaml").write_text(f"""
        settings:
            init_path:
              - /tmp/somewhere
              - {kugl_home()}
    """)
    with pytest.raises(KuglError, match="~/.kugl should not be listed in init_path"):
        main1(["select 1"])


def test_reject_dupe_resource(hr, extra_home):
    """Resource must not be defined in more than one schema file"""
    hr.save()
    extra_home.joinpath("hr.yaml").write_text("""
        resources:
        - name: people
          data: {}
    """)
    with pytest.raises(KuglError, match="Resource 'people' is already defined in schema 'hr'"):
        main1([hr.PEOPLE_QUERY])


def test_reject_dupe_table(hr, extra_home):
    """Table must not be defined in more than one schema file"""
    hr.save(folder=extra_home)
    kugl_home().joinpath("hr.yaml").write_text("""
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
    hr.save(folder=extra_home)
    kugl_home().joinpath("hr.yaml").write_text("""
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
    hr.save(folder=extra_home)
    kugl_home().joinpath("hr.yaml").write_text("""
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

