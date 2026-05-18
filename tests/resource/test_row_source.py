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


@pytest.mark.parametrize(
    "items,expected",
    [
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
    ],
)
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


def test_from_detects_label(test_home):
    """`from: domain/key` auto-detects as a label extractor."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - metadata:
                  labels:
                    test.io/group: team-a
      create:
        - table: things
          resource: things
          columns:
            - name: grp
              from: test.io/group
    """)
    assert_query(
        "SELECT * FROM things",
        """
        grp
        team-a
    """,
    )


def test_from_detects_path(test_home):
    """`from: jmespath.expr` auto-detects as a path extractor."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - metadata:
                  name: my-thing
      create:
        - table: things
          resource: things
          columns:
            - name: thing_name
              from: metadata.name
    """)
    assert_query(
        "SELECT * FROM things",
        """
        thing_name
        my-thing
    """,
    )


def test_from_scoped_path(test_home):
    """`from: expr in scope` resolves a JMESPath on the named scope."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - metadata:
                  name: pod-a
                spec:
                  containers:
                    - name: c1
                    - name: c2
      create:
        - table: things
          resource: things
          row_source:
            - items as pod
            - spec.containers as container
          columns:
            - name: pod_name
              from: metadata.name in pod
            - name: container_name
              from: name in container
    """)
    assert_query(
        "SELECT * FROM things ORDER BY container_name",
        """
        pod_name    container_name
        pod-a       c1
        pod-a       c2
    """,
    )


def test_from_scoped_label(test_home):
    """`from: domain/key in scope` resolves as a label on the named scope object."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items:
              - metadata:
                  labels:
                    test.io/group: team-b
                children:
                  - val: x
      create:
        - table: things
          resource: things
          row_source:
            - items as item
            - children as child
          columns:
            - name: grp
              from: test.io/group in item
            - name: val
              from: val in child
    """)
    assert_query(
        "SELECT * FROM things",
        """
        grp     val
        team-b  x
    """,
    )


def test_from_conflicts_with_path(test_home):
    """Specifying both `from` and `path` raises a validation error."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          data:
            items: [{val: a}]
      create:
        - table: things
          resource: things
          columns:
            - name: val
              from: val
              path: val
    """)
    with pytest.raises(KuglError, match="cannot specify .from. alongside"):
        assert_query("SELECT * FROM things", "")


def test_from_unknown_scope(test_home):
    """`from: expr in unknownscope` raises a clear error at table-build time."""
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
              from: val in ghost
    """)
    with pytest.raises(KuglError, match="Unknown scope 'ghost'"):
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
