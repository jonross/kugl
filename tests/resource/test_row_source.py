"""
Unit tests for row_source errors and special cases.
"""

import json

import pytest

from kugl.util import KuglError, kugl_home
from ..testing import assert_query
from ..k8s.k8s_mocks import kubectl_response


def test_caret_rejected(test_home):
    """Ensure ^ parent navigation raises a clear error."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          namespaced: true
      create:
        - table: things
          resource: things
          columns:
            - name: something
              path: ^parent
    """)
    kubectl_response("things", {"items": [{"something": "foo"}]})
    with pytest.raises(KuglError, match=r"\^ parent navigation is no longer supported"):
        assert_query("SELECT * FROM things", "")


_MULTI_STEP_CONFIG = """
  resources:
    - name: things
      data:
        items: {items}
  create:
    - table: things
      resource: things
      row_source:
        - items as item
        - children as child
      columns:
        - name: parent_id
          path: parent in item
        - name: val
          path: val in child
"""

@pytest.mark.parametrize("items,expected", [
    pytest.param(
        [
            {"parent": "p1", "children": [{"val": "a"}, {"val": "b"}]},
            {"parent": "p2", "children": [{"val": "c"}]},
        ],
        """
        parent_id    val
        p1           a
        p1           b
        p2           c
        """,
        id="normal",
    ),
    pytest.param(
        [
            {"parent": "p1", "children": [{"val": "a"}]},
            {"parent": "p2", "children": []},
        ],
        """
        parent_id    val
        p1           a
        """,
        id="empty_sublist",
    ),
])
def test_multi_step_row_source(test_home, items, expected):
    """Multi-step row_source with named scopes; also checks empty sublists produce no rows."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text(
        _MULTI_STEP_CONFIG.format(items=json.dumps(items))
    )
    assert_query("SELECT * FROM things ORDER BY parent_id, val", expected)


def test_kv_with_parent_nav(test_home):
    """'; kv' expansion combined with named scope to reference a field from the parent item."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - service: svc-a
                env:
                  FOO: bar
                  BAZ: glig
              - service: svc-b
                env:
                  QUX: quux
      create:
        - table: things
          resource: things
          row_source:
            - items as item
            - env as kv_pair; kv
          columns:
            - name: service
              path: service in item
            - name: key
              path: key in kv_pair
            - name: value
              path: value in kv_pair
    """)
    assert_query(
        "SELECT * FROM things ORDER BY service, key",
        """
        service    key    value
        svc-a      BAZ    glig
        svc-a      FOO    bar
        svc-b      QUX    quux
        """,
    )


def test_three_level_named_scopes(test_home):
    """Three-step row_source with named scopes; verifies ancestor scopes are reachable."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - section: sec-a
                groups:
                  - grp: grp-1
                    tags:
                      - tag: t1
                      - tag: t2
                  - grp: grp-2
                    tags:
                      - tag: t3
      create:
        - table: things
          resource: things
          row_source:
            - items as section_item
            - groups as group
            - tags as tag_item
          columns:
            - name: section
              path: section in section_item
            - name: grp
              path: grp in group
            - name: tag
              path: tag in tag_item
    """)
    assert_query(
        "SELECT * FROM things ORDER BY section, grp, tag",
        """
        section    grp    tag
        sec-a      grp-1  t1
        sec-a      grp-1  t2
        sec-a      grp-2  t3
        """,
    )


def test_missing_scope_name(test_home):
    """Multi-step row_source without 'as <name>' raises a ConfigError."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - children: [{val: a}]
      create:
        - table: things
          resource: things
          row_source:
            - items as item
            - children
          columns:
            - name: val
              path: val in item
    """)
    with pytest.raises(KuglError, match="must all have 'as <name>'"):
        assert_query("SELECT * FROM things", "")


def test_unscoped_column_in_multi_step(test_home):
    """Multi-step row_source with a bare (un-scoped) column path raises a ConfigError."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - children: [{val: a}]
      create:
        - table: things
          resource: things
          row_source:
            - items as item
            - children as child
          columns:
            - name: val
              path: val
    """)
    with pytest.raises(KuglError, match="must end with 'in <name>'"):
        assert_query("SELECT * FROM things", "")


def test_data_dict_expansion(test_home):
    """Verify the behavior of the '; kv' option in row_source"""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            env:
              foo: bar
              baz: glig
      create:
        - table: things
          resource: things
          row_source:
            - env; kv
          columns:
            - name: key
              path: key
            - name: value
              path: value
    """)
    assert_query(
        "SELECT * FROM things ORDER BY key",
        """
        key    value
        baz    glig
        foo    bar
    """,
    )
