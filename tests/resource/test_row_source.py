"""
Unit tests for row_source errors and special cases.
"""

import pytest

from kugl.util import KuglError, kugl_home
from ..testing import assert_query
from ..k8s.k8s_mocks import kubectl_response


def test_too_many_parents(test_home):
    """Ensure correct error when a parent field reference is too long."""
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
      resources:
        - name: things
          namespaced: true
      create:
        - table: things
          resource: things
          columns:
            - name: something
              path: ^^^invalid
    """)
    kubectl_response("things", {
        "items": [
            {"something": "foo"},
            {"something": "foo"},
        ]
    })
    with pytest.raises(KuglError, match="Missing parent or too many . while evaluating ...invalid"):
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
    assert_query("SELECT * FROM things ORDER BY key", """
        key    value
        baz    glig
        foo    bar
    """)
